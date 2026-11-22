"""Fill the machine-generated parts of docs/DETECTOR_MODEL_CARD.md from your measured files.

    python eval/fill_model_card.py

Replaces only the blocks between  <!-- BEGIN:auto:NAME -->  and  <!-- END:auto:NAME -->  with:
  status        measured date, image count, smoke-test warning when under 300 images
  model-info    licence / declared training data per model (results/model_info.json, from model_info.py)
  data          image counts, sources with licences and fake kinds (manifest.csv + sources.csv)
  results       results/latest.md
  failure-modes results/failure_modes.md
Everything outside the markers (intended use, your own reading of the limitations) is left untouched.
Blocks whose input file is missing are left as they were, never filled with invented text.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.eval_stats import is_smoke_test  # noqa: E402



def replace_block(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(<!-- BEGIN:auto:{re.escape(name)} -->)(.*?)(<!-- END:auto:{re.escape(name)} -->)", re.S)
    if not pat.search(text):
        raise ValueError(f"marker block '{name}' not found in the model card")
    return pat.sub(lambda m: f"{m.group(1)}\n{body.strip()}\n{m.group(3)}", text, count=1)


def data_block(manifest: Path, sources_csv: Path, threshold: float) -> str:
    with manifest.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    orig = [r for r in rows if r["condition"] == "original"]
    lab = Counter(r["label"].strip().lower() for r in orig)
    real = sum(v for k, v in lab.items() if k in {"real", "0", "false", "genuine", "authentic"})
    fake = len(orig) - real
    lines = [f"- Images: {real} real, {fake} fake originals ({len(rows)} rows including degraded copies)"]
    srcs = {}
    if sources_csv.is_file():
        with sources_csv.open(newline="", encoding="utf-8") as fh:
            srcs = {r["source"]: r for r in csv.DictReader(fh)}
    used = sorted({r["source"] for r in rows})
    lines.append("- Sources and their licences:")
    for s in used:
        info = srcs.get(s, {})
        lines.append(f"  - {s}: {info.get('url') or 'URL NOT RECORDED'} ; licence: {info.get('licence') or 'NOT RECORDED'}")
    kinds = sorted({srcs.get(s, {}).get("fake_kind", "") for s in used} - {""})
    lines.append(f"- Kinds of fake covered: {', '.join(kinds) if kinds else 'NOT RECORDED in sources.csv'}")
    conds = sorted({r["condition"] for r in rows})
    lines.append(f"- Conditions: {', '.join(conds)}")
    lines.append(f"- Decision threshold: {threshold:g}% (not tuned on this set unless stated here)")
    return "\n".join(lines)


def model_info_block(path: Path) -> str:
    infos = json.loads(path.read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import model_info
    return model_info.to_markdown(infos)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", default="../docs/DETECTOR_MODEL_CARD.md")
    ap.add_argument("--results", default="eval/results")
    ap.add_argument("--manifest", default="eval/manifest.csv")
    ap.add_argument("--sources", default="eval/sources.csv")
    a = ap.parse_args()
    card = Path(a.card); res = Path(a.results)
    text = card.read_text(encoding="utf-8")
    latest_json = res / "latest.json"
    if not latest_json.is_file():
        print("ERROR: no results/latest.json yet. Run eval/run_eval.py first; the card stays 'not yet measured'.")
        return 2
    report = json.loads(latest_json.read_text(encoding="utf-8"))
    n = report.get("images_test", report["images"])
    smoke = is_smoke_test(report)
    status = (f"Status: **measured {report['generated_at'][:10]} on {n} images"
              + (" - SMOKE TEST ONLY (too few original images; about 300 needed); do not quote these numbers as a result.**" if smoke else ".**")
              + " Numbers describe this set and these degradations only.")
    text = replace_block(text, "status", status)
    if (res / "latest.md").is_file():
        text = replace_block(text, "results", (res / "latest.md").read_text(encoding="utf-8"))
    if (res / "failure_modes.md").is_file():
        text = replace_block(text, "failure-modes", (res / "failure_modes.md").read_text(encoding="utf-8"))
    if (res / "model_info.json").is_file():
        text = replace_block(text, "model-info", model_info_block(res / "model_info.json"))
    if Path(a.manifest).is_file():
        text = replace_block(text, "data", data_block(Path(a.manifest), Path(a.sources), report["threshold"]))
    card.write_text(text, encoding="utf-8")
    print(f"Updated {card}" + (" (smoke test: too few original images)" if smoke else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
