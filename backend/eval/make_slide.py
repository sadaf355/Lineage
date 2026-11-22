"""Build the 'Measured detection' deck slide from results/latest.json (python-pptx; pip install -r requirements-dev.txt).

    python eval/make_slide.py                 # writes results/detector_slide.pptx and results/detector_slide.md

The slide shows only numbers from your run: overall and per-condition accuracy / recall / ROC-AUC for the models
you evaluated, the image count, the threshold, and a plain statement of what the score is not. If the set has fewer
than 300 images the slide is stamped SMOKE TEST so it cannot be mistaken for a result.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.eval_stats import is_smoke_test  # noqa: E402

PICK = ("all", "original", "jpeg_q50", "resize_50", "crop_80", "screenshot")


def rows_for(report: dict) -> list[list[str]]:
    out = [["Model", "Condition", "n", "Accuracy", "Recall", "ROC-AUC"]]
    for name, m in report["models"].items():
        if "accuracy" not in m:
            out.append([name[:48], "no image scored", "0", "-", "-", "-"]); continue
        short = name if len(name) <= 48 else name[:45] + "..."
        cells = {"all": m, **(m.get("by_condition") or {})}
        for cond in PICK:
            x = cells.get(cond)
            if x:
                auc = "n/a" if x.get("roc_auc") is None else f"{x['roc_auc']:.2f}"
                out.append([short if cond == "all" else "", cond, str(x["samples"]), f"{x['accuracy']:.1f}%", f"{x['recall']:.1f}%", auc])
    return out


def to_markdown(report: dict) -> str:
    smoke = is_smoke_test(report)
    rows = rows_for(report)
    md = ["## Slide: Measured detection", ""]
    if smoke:
        md += ["> SMOKE TEST: too few original images (need about 300). Not a result.", ""]
    md += ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    md += ["", f"{report.get('images_test', report['images'])} images, decision threshold {report['threshold']:g}%. A manipulation likelihood for triage, "
               "not proof; weaker on screenshots, crops and new generators (see model card)."]
    return "\n".join(md)


def build(report: dict, path: Path) -> None:
    prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(0.9)).text_frame
    tb.text = "Measured detection: what the detector gets right, and where it does not"
    tb.paragraphs[0].runs[0].font.size = Pt(28); tb.paragraphs[0].runs[0].font.bold = True
    rows = rows_for(report)
    shape = s.shapes.add_table(len(rows), len(rows[0]), Inches(0.6), Inches(1.4), Inches(12.1), Inches(0.32) * len(rows))
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            cell = shape.table.cell(i, j); cell.text = v
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(12); run.font.bold = (i == 0)
    foot = s.shapes.add_textbox(Inches(0.6), Inches(6.55), Inches(12), Inches(0.8)).text_frame
    foot.word_wrap = True
    foot.text = (f"{report.get('images_test', report['images'])} images | threshold {report['threshold']:g}% | a manipulation likelihood for triage, not proof. "
                 "Metrics describe this set only; weaker on screenshots, crops and newer generators.")
    foot.paragraphs[0].runs[0].font.size = Pt(12)
    if is_smoke_test(report):
        stamp = s.shapes.add_textbox(Inches(8.9), Inches(0.1), Inches(4.2), Inches(0.5)).text_frame
        stamp.text = "SMOKE TEST - NOT A RESULT"
        stamp.paragraphs[0].runs[0].font.size = Pt(16); stamp.paragraphs[0].runs[0].font.bold = True
        stamp.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xB0, 0x20, 0x20)
    prs.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="eval/results/latest.json")
    ap.add_argument("--out", default="eval/results/detector_slide.pptx")
    a = ap.parse_args()
    p = Path(a.results)
    if not p.is_file():
        print(f"ERROR: {p} not found. There is nothing measured to put on a slide yet.")
        return 2
    report = json.loads(p.read_text(encoding="utf-8"))
    out = Path(a.out)
    build(report, out)
    out.with_suffix(".md").write_text(to_markdown(report), encoding="utf-8")
    print(f"Wrote {out} and {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
