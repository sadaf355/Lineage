"""Turn a folder of downloaded datasets into eval/images + manifest.csv, refusing sources without a recorded licence.

Layout you create (git-ignored):

    eval/incoming/<source-name>/real/*.jpg|png|webp
    eval/incoming/<source-name>/fake/*.jpg|png|webp

and one row per <source-name> in eval/sources.csv (copy sources.example.csv):

    source,url,licence,fake_kind
    my-dataset,https://example.org/dataset,CC-BY-4.0,face swap

Then:   python eval/build_manifest.py

What it enforces, because a wrong test set is worse than a small one:
  * every source has a URL and a licence you wrote down (no TODO/unknown),
  * every file opens as an image,
  * exact duplicate files are kept once, and a file that appears under BOTH labels is dropped and reported,
  * filenames are made unique per source and label.
It never downloads anything and never edits the originals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
LABELS = ("real", "fake")
PLACEHOLDER_LICENCES = {"", "todo", "tbd", "unknown", "?", "n/a", "na", "none", "example", "___"}


class BuildError(ValueError):
    pass


def load_sources(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise BuildError(f"{path} not found. Copy sources.example.csv to sources.csv and describe each dataset (url, licence).")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {r["source"].strip(): {k: (v or "").strip() for k, v in r.items()} for r in rows if (r.get("source") or "").strip()}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "x"


def build(incoming: Path, images: Path, sources_csv: Path, manifest: Path) -> dict:
    sources = load_sources(sources_csv)
    folders = sorted(p for p in incoming.iterdir() if p.is_dir()) if incoming.is_dir() else []
    if not folders:
        raise BuildError(f"No dataset folders in {incoming}. Put files in {incoming}/<source>/real and {incoming}/<source>/fake.")
    problems = []
    for f in folders:
        s = sources.get(f.name)
        if not s:
            problems.append(f"'{f.name}' has no row in {sources_csv.name}")
        else:
            if not s.get("url"):
                problems.append(f"'{f.name}': url is empty")
            if s.get("licence", "").strip().lower() in PLACEHOLDER_LICENCES:
                problems.append(f"'{f.name}': licence is empty or a placeholder. Read the dataset's licence/terms and write it down.")
    if problems:
        raise BuildError("Cannot build the manifest:\n  - " + "\n  - ".join(problems))

    images.mkdir(parents=True, exist_ok=True)
    seen: dict[str, tuple[str, str]] = {}          # sha256 -> (label, out filename)
    conflicts: set[str] = set()
    rows: list[dict[str, str]] = []
    skipped = Counter()
    for folder in folders:
        for label in LABELS:
            d = folder / label
            if not d.is_dir():
                continue
            for src in sorted(p for p in d.rglob("*") if p.is_file()):
                if src.suffix.lower() not in IMAGE_EXTS:
                    skipped["unsupported extension"] += 1
                    continue
                try:
                    with Image.open(src) as im:
                        im.verify()
                except Exception:  # noqa: BLE001
                    skipped["not a readable image"] += 1
                    continue
                digest = hashlib.sha256(src.read_bytes()).hexdigest()
                if digest in seen:
                    if seen[digest][0] != label:
                        conflicts.add(digest)
                    skipped["duplicate"] += 1
                    continue
                name = f"{_slug(folder.name)}__{label}__{_slug(src.stem)}{src.suffix.lower()}"
                n = 1
                while (images / name).exists() and digest not in {hashlib.sha256((images / name).read_bytes()).hexdigest()}:
                    n += 1
                    name = f"{_slug(folder.name)}__{label}__{_slug(src.stem)}-{n}{src.suffix.lower()}"
                shutil.copyfile(src, images / name)
                seen[digest] = (label, name)
                rows.append({"filename": name, "label": label, "source": folder.name, "condition": "original"})
    if conflicts:   # the same pixels labelled both real and fake: unusable, drop both
        bad = {seen[d][1] for d in conflicts}
        for name in bad:
            (images / name).unlink(missing_ok=True)
        rows = [r for r in rows if r["filename"] not in bad]
        skipped["same file under both labels (dropped)"] += len(bad)
    if not rows:
        raise BuildError("No usable images found.")
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["filename", "label", "source", "condition"])
        w.writeheader(); w.writerows(rows)

    by_label = Counter(r["label"] for r in rows)
    per_source: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        per_source[r["source"]][r["label"]] += 1
    warnings = []
    if len(rows) < 300:
        warnings.append(f"Only {len(rows)} images: metrics will be a smoke test, not a result (aim for 300 or more).")
    if min(by_label.values(), default=0) == 0 or max(by_label.values()) / max(1, sum(by_label.values())) > 0.65:
        warnings.append(f"Labels are unbalanced: {dict(by_label)}. Aim for roughly half real, half fake.")
    if len(per_source) < 2:
        warnings.append("Only one source: you would mostly measure that one dataset or generator. Add at least one more.")
    fake_kinds = {sources[s].get("fake_kind", "") for s in per_source if per_source[s]["fake"]} - {""}
    if len(fake_kinds) < 2:
        warnings.append("Fewer than two kinds of fake recorded in sources.csv (face swap / generated face / generated scene).")
    return {"images": len(rows), "by_label": dict(by_label), "per_source": {k: dict(v) for k, v in per_source.items()},
            "skipped": dict(skipped), "warnings": warnings}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incoming", default="eval/incoming")
    ap.add_argument("--images", default="eval/images")
    ap.add_argument("--sources", default="eval/sources.csv")
    ap.add_argument("--manifest", default="eval/manifest.csv")
    a = ap.parse_args()
    try:
        s = build(Path(a.incoming), Path(a.images), Path(a.sources), Path(a.manifest))
    except BuildError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Wrote {a.manifest}: {s['images']} images {s['by_label']}")
    for src, c in s["per_source"].items():
        print(f"  {src}: {c}")
    if s["skipped"]:
        print("Skipped:", s["skipped"])
    for w in s["warnings"]:
        print("WARNING:", w)
    print("Next: python eval/build_degraded.py --manifest eval/manifest.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
