"""
Hosting enrichment for traced pages: who runs the SERVER (network name, country, CIDR; domain registrar and dates).

This describes where a page is hosted. It never identifies the person who created or uploaded the content.
Off by default (HOSTING_RDAP_ENABLED=false) because it contacts a third-party RDAP service. All fetching goes through the
same DNS-pinned, public-address-only client the page tracer uses, with a small redirect budget (rdap.org redirects to the
regional registry).
"""
from __future__ import annotations

import ipaddress
import json
from typing import Any, Callable
from urllib.parse import urljoin

MAX_BYTES = 256 * 1024


def _is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified)


def parse_ip_rdap(doc: dict[str, Any]) -> dict[str, Any]:
    cidrs = []
    for c in doc.get("cidr0_cidrs") or []:
        base = c.get("v4prefix") or c.get("v6prefix")
        if base and "length" in c:
            cidrs.append(f"{base}/{c['length']}")
    orgs = []
    for ent in doc.get("entities") or []:
        vcard = (ent.get("vcardArray") or [None, []])[1]
        for item in vcard:
            if item and item[0] == "fn":
                orgs.append(str(item[3])[:120])
    return {"network_name": doc.get("name"), "handle": doc.get("handle"), "country": doc.get("country"),
            "range": f"{doc.get('startAddress')} - {doc.get('endAddress')}" if doc.get("startAddress") else None,
            "cidrs": cidrs[:5], "organisations": orgs[:3], "type": doc.get("type")}


def parse_domain_rdap(doc: dict[str, Any]) -> dict[str, Any]:
    events = {e.get("eventAction"): e.get("eventDate") for e in doc.get("events") or [] if e.get("eventAction")}
    registrar = None
    for ent in doc.get("entities") or []:
        if "registrar" in (ent.get("roles") or []):
            for item in (ent.get("vcardArray") or [None, []])[1]:
                if item and item[0] == "fn":
                    registrar = str(item[3])[:120]
    return {"registered": events.get("registration"), "last_changed": events.get("last changed"), "expires": events.get("expiration"),
            "registrar": registrar, "status": (doc.get("status") or [])[:5],
            "nameservers": [n.get("ldhName") for n in doc.get("nameservers") or [] if n.get("ldhName")][:4]}


def _default_fetch(url: str, timeout: float) -> dict[str, Any]:
    from app.services import source_tracing           # pinned-IP, public-address-only, no automatic redirects
    current = url
    for _ in range(4):
        resp, _ip = source_tracing._pinned_get(current, timeout=(timeout, timeout), headers={"Accept": "application/rdap+json, application/json"})
        try:
            if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                current = urljoin(current, resp.headers["location"])
                if not current.startswith("https://"):
                    raise ValueError("RDAP redirect to a non-HTTPS URL was refused.")
                continue
            resp.raise_for_status()
            body = b""
            for chunk in resp.iter_content(16384):
                body += chunk
                if len(body) > MAX_BYTES:
                    raise ValueError("RDAP response too large.")
            return json.loads(body.decode("utf-8", "replace"))
        finally:
            resp.close()
    raise ValueError("Too many RDAP redirects.")


def enrich(footprint: dict[str, Any], *, enabled: bool, base: str = "https://rdap.org", timeout: float = 5.0,
           fetch: Callable[[str, float], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return the footprint with an `enrichment` block. Never raises: failures are recorded as notes."""
    out = dict(footprint)
    if not enabled:
        out["enrichment"] = {"status": "disabled", "note": "RDAP lookups are off (HOSTING_RDAP_ENABLED=false)."}
        return out
    fetch = fetch or _default_fetch
    info: dict[str, Any] = {"status": "ok", "networks": [], "domain": None, "notes": []}
    for ip in (footprint.get("server_ips") or [])[:3]:
        if not _is_public(ip):
            continue
        try:
            info["networks"].append({"ip": ip, **parse_ip_rdap(fetch(f"{base.rstrip('/')}/ip/{ip}", timeout))})
        except Exception as exc:
            info["notes"].append(f"IP lookup failed for {ip}: {type(exc).__name__}")
    dom = footprint.get("domain")
    if dom and not _looks_like_ip(dom):
        try:
            info["domain"] = parse_domain_rdap(fetch(f"{base.rstrip('/')}/domain/{dom}", timeout))
        except Exception as exc:
            info["notes"].append(f"Domain lookup failed for {dom}: {type(exc).__name__}")
    if not info["networks"] and not info["domain"]:
        info["status"] = "unavailable"
    nets = info["networks"]
    if nets and nets[0].get("country"):
        out["country"] = f"{nets[0]['country']} (registry record for the network, not a precise location)"
    out["enrichment"] = info
    return out


def _looks_like_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False
