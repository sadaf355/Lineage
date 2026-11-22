import io
import json
import zipfile
import pytest
from app.services.case_bundle import build_bundle, verify_bundle


def test_build_bundle_with_extra_entries_and_report_pdf():
    extra = [
        ("metadata_snapshot_m1.json", b'{"snap": 1}'),
        ("c2pa_results.json", b'{"c2pa": 1}'),
        ("bundle_timestamp.json", b'{"ts": 1}'),
    ]
    data = build_bundle(
        incident_id="case",
        title="test",
        evidence_rows=[],
        manifest_envelope=None,
        extra_entries=extra,
        include_report_pdf=b"%PDF-test",
        include_original_files=False,
    )
    result = verify_bundle(data)
    assert result["ok"], result["problems"]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        index = json.loads(z.read("bundle_index.json"))
        assert index["includes_original_files"] is False
        for expected in ("metadata_snapshot_m1.json", "c2pa_results.json", "bundle_timestamp.json", "report.pdf"):
            assert expected in names
            assert expected in index["files"]
        assert not any(n.startswith("files/") for n in names)


def test_extra_entry_report_pdf_with_include_report_pdf_raises_value_error():
    with pytest.raises(ValueError, match="extra bundle entry would overwrite report.pdf"):
        build_bundle(
            incident_id="case",
            title="test",
            evidence_rows=[],
            manifest_envelope=None,
            extra_entries=[("report.pdf", b"duplicate")],
            include_report_pdf=b"%PDF-test",
        )


def test_extra_entry_path_traversal_sanitized():
    data = build_bundle(
        incident_id="case",
        title="test",
        evidence_rows=[],
        manifest_envelope=None,
        extra_entries=[("../../evil.json", b'{"evil": true}')],
    )
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        for n in names:
            assert ".." not in n
            assert not n.startswith("/")
        assert "evil.json" in names


def test_verifier_flags_unindexed_file():
    data = build_bundle(incident_id="case", title="test", evidence_rows=[], manifest_envelope=None)
    src = io.BytesIO(data)
    out = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for n in zin.namelist():
            zout.writestr(n, zin.read(n))
        zout.writestr("surprise.txt", b"bad")
    result = verify_bundle(out.getvalue())
    assert not result["ok"] and "unlisted file: surprise.txt" in result["problems"]
