from datetime import datetime

from app.services import origin
from tests import exif_builder as eb


def _photo(sw="Firmware 1.0.3"):
    tiff = eb.build_tiff({0x010F: (eb.ASCII, "Canon"), 0x0110: (eb.ASCII, "EOS"), 0x0131: (eb.ASCII, sw), 0x0132: (eb.ASCII, "2026:09:01 10:00:05")},
                         {0x9003: (eb.ASCII, "2026:09:01 10:00:03"), 0x829A: (eb.RATIONAL, 0.01), 0x8827: (eb.SHORT, 200), 0x927C: (eb.UNDEF, b"x")},
                         {1: (eb.ASCII, "N"), 2: (eb.RATIONAL, [28.0, 36.0, 0.0]), 3: (eb.ASCII, "E"), 4: (eb.RATIONAL, [77.0, 12.0, 0.0])})
    return eb.with_exif(eb.jpeg(), tiff)


def test_media_analysis_has_all_three_layers_and_gps():
    a = origin.analyse_media(_photo(), "p.jpg", now=datetime(2026, 10, 6))
    assert a["file"]["device"] == "Canon EOS" and a["file"]["gps"]["latitude"] > 28
    assert a["tamper"]["verdict"] == "no_signals" and "not proof" in a["tamper"]["description"]
    assert a["provenance"]["c2pa"]["present"] is False


def test_hindi_description_selected():
    a = origin.analyse_media(_photo(), "p.jpg", lang="hi", now=datetime(2026, 10, 6))
    assert "मेटाडेटा" in a["tamper"]["description"]


def test_case_report_never_exposes_a_creator_ip_and_labels_hosting():
    media = [{"media_id": "m1", "filename": "p.jpg", "analysis": origin.analyse_media(_photo("Adobe Photoshop 26"), "p.jpg", now=datetime(2026, 10, 6))}]
    rep = origin.build_case(media, [{"domain": "example.org", "server_ips": ["93.184.216.34"]}])
    assert rep["creator_ip"]["available"] is False
    assert rep["layers"]["hosting"][0]["label"] == "Hosting server, not the creator"
    flat = str(rep).lower()
    assert "creator_ip" in flat and rep["layers"]["platform"]["status"] == "not_requested_by_this_app"
    assert any("inconsistent_single" in s or "inconsistent_multiple" in s for s in rep["signals_found"])
    assert "93.184.216.34" in str(rep["layers"]["hosting"])


def test_non_image_bytes_are_safe():
    a = origin.analyse_media(b"RIFF....WAVEfmt ", "a.wav", now=datetime(2026, 10, 6))
    assert a["tamper"]["verdict"] == "cannot_judge" and a["file"]["gps"] is None
