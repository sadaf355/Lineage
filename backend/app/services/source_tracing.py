from __future__ import annotations

import hashlib
import hmac
import json
import io
import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
import urllib3
import certifi
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.services import feature_match, pixel_analysis

settings = get_settings()
USER_AGENT = "LINEAGE-source-tracer/2.0"
MAX_HTML = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024

@dataclass
class TracedImage:
    url: str
    similarity: float
    method: str
    agreeing_hashes: int

@dataclass
class TraceResult:
    url: str
    platform: str
    captured_at: datetime
    page_sha256: str
    html: bytes
    matches: list[TracedImage]


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) URLs are supported.")
    host = parsed.hostname
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except (socket.gaierror, ValueError) as exc:
        raise ValueError(f"Could not resolve the URL host: {exc}")
    for addr in addresses:
        ip = ipaddress.ip_address(addr)
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or
                ip.is_multicast or ip.is_unspecified):
            raise ValueError("Private or reserved network targets are not allowed.")




def _resolve_public_ip(host: str, port: int) -> str:
    """Resolve once and return the exact public IP that the HTTP connection will use.

    URL validation alone is not enough against DNS rebinding: the hostname can resolve
    to a public address during validation and to a private address when the HTTP client
    connects. The tracer therefore connects to the validated IP directly while keeping
    the original hostname for HTTP Host/SNI and certificate validation.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, ValueError) as exc:
        raise ValueError(f"Could not resolve the URL host: {exc}")
    for info in infos:
        addr = info[4][0]
        ip = ipaddress.ip_address(addr)
        if not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or
                ip.is_multicast or ip.is_unspecified):
            return addr
    raise ValueError("The URL host did not resolve to a public address.")


class _PinnedResponse:
    """Small requests-like wrapper around urllib3 for pinned-IP fetches."""

    def __init__(self, raw, url: str):
        self._raw = raw
        self.status_code = raw.status
        self.headers = raw.headers
        self.url = url
        self.reason = raw.reason

    def iter_content(self, chunk_size=65536):
        yield from self._raw.stream(chunk_size)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code} for {self.url}")

    def close(self):
        self._raw.close()


def _pinned_get(url: str, timeout=(3.0, 5.0), headers: dict[str, str] | None = None):
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no hostname.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    _validate_public_url(url)
    ip = _resolve_public_ip(host, port)
    request_headers = dict(headers or {})
    request_headers["Host"] = parsed.netloc
    pool_timeout = urllib3.Timeout(connect=float(timeout[0]), read=float(timeout[1]))
    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            ip, port=port, cert_reqs="CERT_REQUIRED", ca_certs=certifi.where(),
            assert_hostname=host, server_hostname=host, maxsize=1, block=True,
        )
    else:
        pool = urllib3.HTTPConnectionPool(ip, port=port, maxsize=1, block=True)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    raw = pool.urlopen(
        "GET", path, headers=request_headers, timeout=pool_timeout,
        preload_content=False, redirect=False, retries=False,
    )
    return _PinnedResponse(raw, url), ip

def _platform(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host or "Web source"


def _read_capped(response: requests.Response, cap: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > cap:
            raise ValueError("Remote response exceeds the allowed size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def _hash_score(a: dict[str, str], b: dict[str, str]) -> tuple[float, int, str]:
    scores = []
    for key, weight in (("perceptual_hash", .45), ("difference_hash", .35), ("average_hash", .20)):
        if a.get(key) and b.get(key):
            d = pixel_analysis.hamming_distance(a[key], b[key])
            score = max(0.0, 100 * (1 - d / 64))
            scores.append((score, weight, key))
    if not scores:
        return 0.0, 0, "none"
    strong = [x for x in scores if x[0] >= 85]
    weighted = sum(v * w for v, w, _ in scores) / sum(w for _, w, _ in scores)
    return round(weighted, 2), len(strong), "+".join(k.replace("_hash", "") for _, _, k in scores)


FEATURE_METHOD_PREFIX = "orb+ransac;"
PENDING_TTL_SECONDS = 30 * 60
_SIGNED_FIELDS = ("url", "platform", "observed_at", "method", "agreeing_hashes",
                  "page_sha256", "page_storage_path", "matched_image_url", "issued_at")


def _pending_key() -> bytes:
    return hashlib.sha256(("lineage-pending-trace:" + settings.JWT_SECRET_KEY).encode()).digest()


def _pending_canonical(pending: dict, incident_id: str) -> bytes:
    body = {k: str(pending.get(k, "")) for k in _SIGNED_FIELDS}
    body["similarity_score"] = f"{float(pending.get('similarity_score', 0)):.4f}"
    body["incident_id"] = str(incident_id)
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def sign_pending_match(pending: dict, incident_id: str) -> str:
    """HMAC over the server-produced match so the browser cannot invent or alter one."""
    return hmac.new(_pending_key(), _pending_canonical(pending, incident_id), hashlib.sha256).hexdigest()


def verify_pending_match(pending: dict, incident_id: str, check_expiry: bool = True) -> None:
    signature = str(pending.get("signature") or "")
    if not signature:
        raise ValueError("This match was not produced by a LINEAGE trace (missing signature).")
    expected = sign_pending_match(pending, incident_id)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Match data does not match what the server produced for this case.")
    if check_expiry:
        try:
            issued = int(pending.get("issued_at"))
        except (TypeError, ValueError):
            raise ValueError("Match is missing its issue time.")
        if time.time() - issued > PENDING_TTL_SECONDS:
            raise ValueError("This match expired. Run the trace again.")


def validate_trace_accept_payload(payload: dict) -> dict:
    """Validate the minimum immutable fields required to promote a pending URL match."""
    required = ("url", "platform", "observed_at", "similarity_score", "page_sha256", "page_storage_path")
    missing = [key for key in required if payload.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Incomplete traced-source confirmation payload: {', '.join(missing)}")
    score = float(payload["similarity_score"])
    if not 85 <= score <= 100:
        raise ValueError("Accepted traced-source similarity must be between 85 and 100.")
    if payload.get("agreeing_hashes") is not None and int(payload["agreeing_hashes"]) < 2:
        # The only other accepted evidence is a geometrically verified local-feature match (feature_match.py).
        # `method` is part of the signed payload, so a client cannot relabel a weak hash match to take this path.
        if not str(payload.get("method", "")).startswith(FEATURE_METHOD_PREFIX):
            raise ValueError("Accepted traced-source match must have at least two agreeing hashes.")
    return payload


def _fetch_page(url: str) -> tuple[str, bytes]:
    """Fetch a public page with requests, or optionally render JS with Playwright.

    Browser requests are intercepted and rejected unless every target URL passes the same
    public-network validation used by image fetching. This is a defense-in-depth control,
    not a guarantee against every browser/OS resolver edge case.
    """
    timeout = (3.0, float(settings.TRACE_IMAGE_TIMEOUT_SECONDS))
    if not settings.TRACE_USE_HEADLESS_BROWSER:
        r, _ = _pinned_get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if 300 <= r.status_code < 400 and r.headers.get("location"):
            redirected = urljoin(url, r.headers["location"]); _validate_public_url(redirected)
            r.close()
            r, _ = _pinned_get(redirected, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            url = redirected
        r.raise_for_status()
        try:
            return url, _read_capped(r, MAX_HTML)
        finally:
            r.close()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Headless tracing is enabled but Playwright is not installed.") from exc
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        def route_handler(route):
            target = route.request.url
            try:
                _validate_public_url(target)
                route.continue_()
            except Exception:
                route.abort()
        page = context.new_page()
        page.route("**/*", route_handler)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=int(settings.TRACE_BROWSER_TIMEOUT_SECONDS * 1000))
            html = page.content().encode("utf-8")
            if len(html) > MAX_HTML:
                raise ValueError("Rendered page exceeds the allowed size limit.")
            final_url = page.url
            _validate_public_url(final_url)
            return final_url, html
        finally:
            context.close(); browser.close()


def trace_url(url: str, case_images: list[tuple[str, bytes]]) -> TraceResult:
    if not re.match(r"^https?://", url, re.I):
        raise ValueError("URL must start with http:// or https://")
    _validate_public_url(url)
    url, html = _fetch_page(url)
    page_sha256 = hashlib.sha256(html).hexdigest()
    soup = BeautifulSoup(html, "html.parser")

    image_urls: list[str] = []
    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src")
        if src:
            u = urljoin(url, src)
            if urlparse(u).scheme in {"http", "https"} and u not in image_urls:
                image_urls.append(u)
        if len(image_urls) >= settings.TRACE_MAX_IMAGES:
            break
    for tag in soup.find_all("meta"):
        if tag.get("property", "").lower() in {"og:image", "twitter:image"} and tag.get("content"):
            u = urljoin(url, tag["content"])
            if urlparse(u).scheme in {"http", "https"} and u not in image_urls:
                image_urls.append(u)
        if len(image_urls) >= settings.TRACE_MAX_IMAGES:
            break

    refs = []
    for media_id, raw in case_images:
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            refs.append((media_id, pixel_analysis.robust_hash_variants(im)))
        except (UnidentifiedImageError, OSError):
            continue

    ref_features = []  # extracted lazily, only if a candidate misses on hashes
    matches: list[TracedImage] = []
    timeout = (3.0, float(settings.TRACE_IMAGE_TIMEOUT_SECONDS))
    started = time.monotonic()
    for image_url in image_urls[: settings.TRACE_MAX_IMAGES]:
        if time.monotonic() - started > settings.TRACE_MAX_SECONDS:
            break
        try:
            _validate_public_url(image_url)
            ir, _ = _pinned_get(image_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            try:
                if 300 <= ir.status_code < 400:
                    continue
                ir.raise_for_status()
                data = _read_capped(ir, MAX_IMAGE_BYTES)
            finally:
                ir.close()
            im = Image.open(io.BytesIO(data)).convert("RGB")
            candidate_variants = pixel_analysis.robust_hash_variants(im)
            best = 0.0; best_agree = 0; best_method = "none"
            for _, ref_variants in refs:
                for ref_name, ref in ref_variants:
                    for candidate_name, candidate in candidate_variants:
                        score, agree, method = _hash_score(candidate, ref)
                        if score > best:
                            best, best_agree = score, agree
                            best_method = f"{method}; candidate={candidate_name}; reference={ref_name}"
            if best >= 85 and best_agree >= 2:
                matches.append(TracedImage(image_url, best, best_method, best_agree))
            elif settings.TRACE_FEATURE_MATCH_ENABLED:
                # Whole-image hashes miss cropped copies. Verify with local features + geometry (bounded: one pass
                # per candidate, and the loop's TRACE_MAX_SECONDS budget still applies).
                if not ref_features:
                    ref_features = [feature_match.extract(Image.open(io.BytesIO(raw)).convert("RGB")) for _, raw in case_images[:5]]
                fbest = None
                for rf in ref_features:
                    fm_res = feature_match.best_match(rf, im)
                    if fm_res.matched and (fbest is None or fm_res.inliers > fbest.inliers):
                        fbest = fm_res
                if fbest is not None:
                    matches.append(TracedImage(image_url, fbest.score, fbest.method, 0))
        except Exception:
            continue
    matches.sort(key=lambda x: x.similarity, reverse=True)
    return TraceResult(url=url, platform=_platform(url), captured_at=datetime.utcnow(), page_sha256=page_sha256, html=html, matches=matches[:5])
