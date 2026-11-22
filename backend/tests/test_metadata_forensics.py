"""Metadata forensics: every check with real, crafted images. No network, no database."""
from datetime import datetime
from io import BytesIO

from PIL import Image

from app.services import metadata_forensics as mf
from tests import exif_builder as eb

NOW = datetime(2026, 10, 6, 12, 0, 0)


def _camera_jpeg(**over):
    ifd0 = {0x010F: (eb.ASCII, "Canon"), 0x0110: (eb.ASCII, "Canon EOS 80D"), 0x0131: (eb.ASCII, "Firmware Version 1.0.3"),
            0x0132: (eb.ASCII, "2026:09:01 10:00:05")}
    exif = {0x9003: (eb.ASCII, "2026:09:01 10:00:03"), 0x9004: (eb.ASCII, "2026:09:01 10:00:03"), 0x829A: (eb.RATIONAL, 0.008),
            0x8827: (eb.SHORT, 400), 0x927C: (eb.UNDEF, b"CANON-MAKERNOTE")}
    ifd0.update(over.get("ifd0", {}))
    exif.update(over.get("exif", {}))
    base = over.get("jpeg") or eb.jpeg()
    return eb.with_exif(base, eb.build_tiff(ifd0, exif, over.get("gps"), over.get("thumb")))


def test_untouched_camera_photo_has_no_signals():
    r = mf.analyze(_camera_jpeg(), "a.jpg", now=NOW)
    assert r["verdict"] == "no_signals", r["findings"]
    assert r["fields"]["make"] == "Canon" and r["fields"]["datetime_original"] == "2026:09:01 10:00:03"


def test_stripped_file_is_cannot_judge_never_tampered():
    r = mf.analyze(eb.jpeg(), "stripped.jpg", now=NOW)
    assert r["verdict"] == "cannot_judge" and r["reason"] == "no_metadata"
    assert not any(f["severity"] in ("medium", "high") for f in r["findings"])


def test_unreadable_bytes_do_not_raise():
    r = mf.analyze(b"not an image at all", "x.jpg", now=NOW)
    assert r["verdict"] == "cannot_judge" and r["supported"] is False


def test_editor_software_alone_is_one_category_inconsistent_single():
    r = mf.analyze(_camera_jpeg(ifd0={0x0131: (eb.ASCII, "Adobe Photoshop 26.0")}), now=NOW)
    t1 = [f for f in r["findings"] if f["id"] == "T1"]
    assert t1 and t1[0]["evidence"]["value"] == "Adobe Photoshop 26.0"
    assert r["verdict"] == "inconsistent_single"


def test_editor_plus_late_modify_date_is_inconsistent_multiple():
    r = mf.analyze(_camera_jpeg(ifd0={0x0131: (eb.ASCII, "GIMP 3.0"), 0x0132: (eb.ASCII, "2026:09:04 18:30:00")}), now=NOW)
    ids = {f["id"] for f in r["findings"]}
    assert {"T1", "T2"} <= ids
    assert r["verdict"] == "inconsistent_multiple"
    t2 = next(f for f in r["findings"] if f["id"] == "T2")
    assert t2["evidence"]["gap_text"].startswith("3 day")


def test_small_modify_gap_is_not_flagged():
    r = mf.analyze(_camera_jpeg(ifd0={0x0132: (eb.ASCII, "2026:09:01 10:02:00")}), now=NOW)
    assert not [f for f in r["findings"] if f["id"] == "T2"]


def test_future_date_is_flagged():
    r = mf.analyze(_camera_jpeg(exif={0x9003: (eb.ASCII, "2030:01:01 00:00:00")}, ifd0={0x0132: (eb.ASCII, "2030:01:01 00:00:00")}), now=NOW)
    assert any(f["id"] == "T2" and "future" in f["title"] for f in r["findings"])


def test_capture_after_upload_time_is_flagged():
    r = mf.analyze(_camera_jpeg(), now=NOW, uploaded_at=datetime(2026, 8, 1))
    assert any(f["id"] == "T2" and "later than the upload" in f["title"] for f in r["findings"])


def test_thumbnail_mismatch_is_high_and_matching_thumbnail_is_clean():
    main = eb.jpeg(size=(96, 64), color=(10, 200, 30))
    other = eb.jpeg_bytes_of(Image.new("RGB", (32, 21), (250, 10, 10)))        # different picture
    r_bad = mf.analyze(_camera_jpeg(jpeg=main, thumb=other), now=NOW)
    t3 = [f for f in r_bad["findings"] if f["id"] == "T3"]
    assert t3 and t3[0]["severity"] == "high"
    good_thumb = eb.jpeg_bytes_of(Image.open(BytesIO(main)).resize((32, 21)))
    r_ok = mf.analyze(_camera_jpeg(jpeg=main, thumb=good_thumb), now=NOW)
    assert not [f for f in r_ok["findings"] if f["id"] == "T3"], r_ok["findings"]
    assert r_ok["fields"]["has_thumbnail"] is True


def test_thumbnail_mismatch_plus_editor_gives_inconsistent_multiple():
    main = eb.jpeg(color=(10, 200, 30))
    other = eb.jpeg_bytes_of(Image.new("RGB", (32, 21), (250, 10, 10)))
    r = mf.analyze(_camera_jpeg(jpeg=main, thumb=other, ifd0={0x0131: (eb.ASCII, "Snapseed 2.0")}), now=NOW)
    assert r["verdict"] == "inconsistent_multiple"


def test_missing_camera_fields_with_software_is_only_low():
    tiff = eb.build_tiff({0x0131: (eb.ASCII, "SomeExporter 2")}, {0x9003: (eb.ASCII, "2026:09:01 10:00:03")})
    r = mf.analyze(eb.with_exif(eb.jpeg(), tiff), now=NOW)
    t4 = [f for f in r["findings"] if f["id"] == "T4"]
    assert t4 and all(f["severity"] == "low" for f in t4)
    assert r["verdict"] == "no_signals"


def test_dimension_mismatch_low():
    r = mf.analyze(_camera_jpeg(exif={0xA002: (eb.LONG, 4000), 0xA003: (eb.LONG, 3000)}), now=NOW)
    assert any(f["id"] == "T6" for f in r["findings"])


def test_timezone_offset_vs_gps_longitude():
    gps = {1: (eb.ASCII, "N"), 2: (eb.RATIONAL, [28.0, 36.0, 0.0]), 3: (eb.ASCII, "E"), 4: (eb.RATIONAL, [77.0, 12.0, 0.0])}
    r = mf.analyze(_camera_jpeg(exif={0x9011: (eb.ASCII, "-08:00")}, gps=gps), now=NOW)
    assert any(f["id"] == "T5" for f in r["findings"])
    ok = mf.analyze(_camera_jpeg(exif={0x9011: (eb.ASCII, "+05:30")}, gps=gps), now=NOW)
    assert not any(f["id"] == "T5" for f in ok["findings"])


def test_xmp_history_is_read_without_an_xml_parser_and_flags_edits():
    xmp = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description xmp:CreatorTool="Lightroom 12" '
           'xmp:ModifyDate="2026-09-05T10:00:00+00:00"><xmpMM:History><rdf:Seq><rdf:li stEvt:action="saved" '
           'stEvt:softwareAgent="Adobe Photoshop 26"/></rdf:Seq></xmpMM:History></rdf:Description></rdf:RDF></x:xmpmeta>')
    r = mf.analyze(eb.with_xmp(eb.jpeg(), xmp), now=NOW)
    ids = {f["id"] for f in r["findings"]}
    assert "T1" in ids and "T8" in ids
    assert r["verdict"] == "inconsistent_multiple"


def test_xml_entity_bomb_in_xmp_is_inert():
    bomb = '<x:xmpmeta><!DOCTYPE lolz [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]> xmp:CreatorTool="&b;"</x:xmpmeta>'
    r = mf.analyze(eb.with_xmp(eb.jpeg(), bomb), now=NOW)
    assert r["verdict"] in ("no_signals", "inconsistent_single", "cannot_judge", "inconsistent_multiple")


def test_png_without_metadata_cannot_judge_and_png_text_counts():
    img = Image.new("RGB", (40, 40), (1, 2, 3))
    buf = BytesIO(); img.save(buf, "PNG")
    assert mf.analyze(buf.getvalue(), now=NOW)["verdict"] == "cannot_judge"
    r = mf.analyze(eb.png_with_text(img, {"Comment": "hello"}), now=NOW)
    assert r["fields"]["has_png_text"] is True and r["verdict"] == "no_signals"


def test_malformed_exif_does_not_raise():
    bad = eb.with_exif(eb.jpeg(), b"II*\x00\x08\x00\x00\x00\xff\xff" + b"\x00" * 20)
    r = mf.analyze(bad, now=NOW)
    assert r["verdict"] in ("cannot_judge", "no_signals")


def test_describe_names_fields_and_always_carries_caveat():
    r = mf.analyze(_camera_jpeg(ifd0={0x0131: (eb.ASCII, "GIMP 3.0"), 0x0132: (eb.ASCII, "2026:09:04 18:30:00")}), now=NOW)
    text = mf.describe(r)
    assert "Software" in text and "GIMP 3.0" in text and "not proof" in text
    assert "संकेत" in mf.describe(r, "hi")


def test_quantisation_quality_estimate_recognises_libjpeg_tables():
    raw = eb.jpeg(quality=75, pattern=True)
    tables = mf.jpeg_quant_tables(raw)
    assert tables and mf.estimate_ijg_quality(tables[0]) == 75


def test_diff_reports_lists_drift_between_copies():
    a = mf.analyze(_camera_jpeg(), now=NOW)
    b = mf.analyze(eb.jpeg(), now=NOW)
    fields = {d["field"] for d in mf.diff_reports(a, b)}
    assert {"make", "has_exif"} <= fields
