"""summarize_protocol keeps the report shape the app, model card and slide already read. Synthetic data only."""
import random

from app.services import eval_harness


def _preds(n=60, models=("m1", "m2"), seed=3):
    rnd = random.Random(seed)
    out = {m: [] for m in models}
    for i in range(n):
        label = "fake" if i % 2 else "real"
        for cond in ("original", "jpeg_q50"):
            fname = f"img{i:03d}.png" if cond == "original" else f"img{i:03d}__{cond}.jpg"
            for m in models:
                base = (68 if label == "fake" else 32) + (3 if m == "m2" else 0)
                out[m].append({"filename": fname, "label": label, "source": f"s{i % 2}", "condition": cond,
                               "score": min(100, max(0, rnd.gauss(base, 14)))})
    return out


def test_protocol_report_keeps_legacy_shape_and_adds_protocol_fields():
    rep = eval_harness.summarize_protocol(_preds(), 0.3, "t", None, 100)
    assert rep["images"] == 120 and rep["images_test"] < rep["images"]
    assert rep["originals_test"] + rep["originals_calib"] == 60
    for name, m in rep["models"].items():
        for key in ("accuracy", "precision", "recall", "f1", "confusion_matrix", "by_condition", "samples"):
            assert key in m, (name, key)
        assert "threshold" in m and "ci" in m and "protocol" in m
        assert m["samples"] == rep["images_test"]                 # reported on the held-out split only
    assert set(rep["thresholds"]) == {"m1", "m2"}
    assert rep["split"] and all(v in ("calib", "test") for v in rep["split"].values())


def test_every_model_is_evaluated_on_the_same_split():
    p = _preds()
    rep = eval_harness.summarize_protocol(p, 0.3, "t", None, 50)
    assert rep["models"]["m1"]["samples"] == rep["models"]["m2"]["samples"]


def test_markdown_states_the_protocol_and_intervals():
    rep = eval_harness.summarize_protocol(_preds(), 0.3, "t", None, 100)
    md = eval_harness.to_markdown(rep)
    assert "Held-out test split" in md and "95% CI" in md and "bootstrap" in md


def test_predictions_csv_round_trips_the_split_column(tmp_path):
    p = _preds(10, ("m1",))
    rep = eval_harness.summarize_protocol(p, 0.3, "t", None, 20)
    f = tmp_path / "predictions.csv"
    eval_harness.save_predictions(p, f, rep["split"])
    back = eval_harness.load_predictions(f)
    assert {r["split"] for r in back["m1"]} == {"calib", "test"}
    # a legacy file without the column still loads
    legacy = tmp_path / "legacy.csv"
    eval_harness.save_predictions(p, legacy, None)
    assert {r["split"] for r in eval_harness.load_predictions(legacy)["m1"]} == {""}


def test_legacy_fixed_summary_still_works():
    rep = eval_harness.summarize(_preds(10, ("m1",)), 50.0)
    assert rep["threshold"] == 50.0 and "protocol" not in rep
