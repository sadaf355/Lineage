"""Near-duplicate leakage checker. Synthetic images only."""
import csv
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

from app.services import eval_stats as es

BACKEND = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND / "eval" / "check_leakage.py"


def _img(seed: int) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", (96, 96))
    px = img.load()
    cx, cy, r = rnd.randint(20, 76), rnd.randint(20, 76), rnd.randint(10, 30)
    for y in range(96):
        for x in range(96):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            px[x, y] = (200, 40, 40) if d < r else (rnd.randint(0, 40) + x, rnd.randint(0, 40) + y, 90)
    return img


def _write(tmp: Path, items):
    images = tmp / "images"
    images.mkdir()
    rows = []
    for name, label, img in items:
        img.save(images / name)
        rows.append({"filename": name, "label": label, "source": "toy", "condition": "original"})
    m = tmp / "manifest.csv"
    with m.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["filename", "label", "source", "condition"])
        w.writeheader()
        w.writerows(rows)
    return m


def _run(manifest: Path, *extra):
    return subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(manifest), *extra], capture_output=True, text=True, cwd=BACKEND)


def test_near_duplicates_are_clustered_and_share_a_group(tmp_path):
    a = _img(1)
    near = ImageEnhance.Brightness(a.resize((90, 90)).resize((96, 96))).enhance(1.03)   # same picture, re-saved and resized
    m = _write(tmp_path, [("a.png", "real", a), ("a_copy.png", "real", near), ("b.png", "real", _img(2)), ("c.png", "fake", _img(3))])
    done = _run(m, "--apply")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "1 near-duplicate cluster" in done.stdout
    with m.open(newline="") as fh:
        rows = {r["filename"]: r["group"] for r in csv.DictReader(fh)}
    assert rows["a.png"] == rows["a_copy.png"]
    assert len({rows["a.png"], rows["b.png"], rows["c.png"]}) == 3


def test_a_cluster_mixing_real_and_fake_stops_the_run(tmp_path):
    a = _img(5)
    m = _write(tmp_path, [("real_a.png", "real", a), ("fake_a.png", "fake", a.copy()), ("other.png", "fake", _img(6))])
    done = _run(m)
    assert done.returncode == 1 and "mix real and fake" in done.stdout


def test_unrelated_images_are_left_alone(tmp_path):
    m = _write(tmp_path, [(f"i{n}.png", "real" if n % 2 else "fake", _img(100 + n)) for n in range(6)])
    done = _run(m, "--apply")
    assert done.returncode == 0 and "0 near-duplicate cluster" in done.stdout


def test_merged_groups_keeps_derived_copies_with_their_original():
    base = {"a.png": "a", "a__jpeg_q50.jpg": "a", "b.png": "b", "b__crop_80.png": "b", "c.png": "c"}
    merged = es.merged_groups(base, [{"a.png", "b.png"}])
    assert merged["a.png"] == merged["b.png"] == merged["a__jpeg_q50.jpg"] == merged["b__crop_80.png"] == "a"
    assert merged["c.png"] == "c"


def test_near_duplicate_clusters_chain_and_respect_the_distance():
    h = {"x": 0b0, "y": 0b111, "z": 0b111111, "far": (1 << 40) - 1}
    clusters = es.near_duplicate_clusters(h, 3)
    assert {"x", "y", "z"} in clusters and all("far" not in c for c in clusters)   # x~y (3 bits), y~z (3 bits): chained
    assert es.near_duplicate_clusters(h, 2) == []


def test_split_keeps_a_merged_cluster_together():
    rows = [{"group": "a" if i < 2 else f"g{i}", "y": 0 if i < 2 else i % 2, "score": 50, "condition": "original", "source": "s"} for i in range(12)]
    assign, _ = es.assign_split(rows, 0.5, "x")
    assert len({assign[r["group"]] for r in rows if r["group"] == "a"}) == 1
