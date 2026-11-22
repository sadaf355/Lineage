import json
from types import SimpleNamespace
from app.services.metadata_snapshots import compare_snapshots

def snap(fields):
    return SimpleNamespace(normalized_fields_json=json.dumps(fields))
def test_no_preserved_snapshot_is_unknown_not_changed():
    assert compare_snapshots(None, {"make":"Canon"})["state"] == "unknown"
def test_unchanged_against_snapshot():
    assert compare_snapshots(snap({"make":"Canon","model":"EOS"}), {"make":"Canon","model":"EOS"})["state"] == "unchanged"
def test_changed_requires_and_names_preserved_snapshot():
    result=compare_snapshots(snap({"make":"Canon"}), {"make":"Nikon"})
    assert result["state"] == "changed against snapshot" and result["changed_fields"] == ["make"]
def test_stripped_when_no_comparable_fields_exist():
    assert compare_snapshots(snap({"make":"Canon"}), {})["state"] == "stripped"
def test_stripped_metadata_is_not_hidden_by_file_geometry():
    result=compare_snapshots(snap({"make":"Canon","width":1200,"height":800}), {"filename":"copy.jpg","format":"JPEG","width":1200,"height":800,"mode":"RGB"})
    assert result["state"] == "stripped"
def test_inconsistent_when_earlier_fields_are_missing():
    assert compare_snapshots(snap({"make":"Canon","model":"EOS"}), {"make":"Canon"})["state"] == "inconsistent"
