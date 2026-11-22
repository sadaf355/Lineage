"""Record what each detector model's Hugging Face page says about licence and training data.

    python eval/model_info.py                       # models from DETECTOR_MODEL_ID / DETECTOR_SECOND_MODEL_ID
    python eval/model_info.py --models org/name ... # explicit ids

Writes eval/results/model_info.json and model_info.md. Reads only the structured metadata the model author
published (licence, declared datasets, base model, tags, exact revision). If a field is missing it says
"not stated on the model card" -- it never guesses. Limitations and bias statements are free text on the card,
so the output links to the card and you must read it and summarise it yourself in docs/DETECTOR_MODEL_CARD.md.
Needs internet access to huggingface.co.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

NOT_STATED = "not stated on the model card"


def summarize_model(model_id: str, api: dict[str, Any]) -> dict[str, Any]:
    card = api.get("cardData") or {}
    licence = card.get("license") or next((t.split(":", 1)[1] for t in api.get("tags", []) if t.startswith("license:")), None)
    datasets = card.get("datasets") or [t.split(":", 1)[1] for t in api.get("tags", []) if t.startswith("dataset:")]
    if isinstance(datasets, str):
        datasets = [datasets]
    base = card.get("base_model")
    return {
        "model_id": model_id,
        "url": f"https://huggingface.co/{model_id}",
        "licence": licence or NOT_STATED,
        "training_datasets": datasets or [NOT_STATED],
        "base_model": base if base else NOT_STATED,
        "pipeline_tag": api.get("pipeline_tag") or NOT_STATED,
        "revision": api.get("sha") or NOT_STATED,
        "last_modified": api.get("lastModified") or NOT_STATED,
        "gated": bool(api.get("gated")),
        "has_model_index_metrics": bool(card.get("model-index")),
    }


def fetch(model_id: str, timeout: float = 20.0) -> dict[str, Any]:
    r = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=timeout)
    r.raise_for_status()
    return summarize_model(model_id, r.json())


def to_markdown(infos: list[dict[str, Any]]) -> str:
    lines = ["| Model | Licence | Training data (as declared) | Base model | Revision evaluated |", "|---|---|---|---|---|"]
    for i in infos:
        ds = "; ".join(i["training_datasets"])
        lines.append(f"| [{i['model_id']}]({i['url']}) | {i['licence']} | {ds} | {i['base_model']} | `{str(i['revision'])[:12]}` |")
    lines += ["", "Read each model card for its stated limitations and intended use before relying on it; "
              "fields marked \"not stated on the model card\" are unknown, not safe."]
    return "\n".join(lines)


def main() -> int:
    from app.core.config import get_settings
    s = get_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=[m for m in (s.DETECTOR_MODEL_ID, s.DETECTOR_SECOND_MODEL_ID) if m])
    ap.add_argument("--out", default="eval/results/model_info.json")
    a = ap.parse_args()
    infos = []
    for m in a.models:
        try:
            infos.append(fetch(m))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: could not read {m} from huggingface.co: {exc}")
            return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(infos, indent=2), encoding="utf-8")
    md = to_markdown(infos)
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
