"""docs/THREAT_MODEL.md stays honest: every code and test reference must exist."""
import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
DOC = ROOT / "docs" / "THREAT_MODEL.md"
REF = re.compile(r"`([^`]+?)`")


def _rows():
    for line in DOC.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and re.fullmatch(r"T-[A-Z]+-\d+[a-z]?", cells[0]):
            yield cells


def _resolve(path: str) -> Path:
    for base in (BACKEND, ROOT):
        if (base / path).exists():
            return base / path
    raise AssertionError(f"file not found: {path}")


def _symbol_exists(file: Path, symbol: str) -> bool:
    tree = ast.parse(file.read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    return symbol in names


def _check_ref(ref: str):
    path, _, symbol = ref.partition("::")
    f = _resolve(path)
    if symbol and f.suffix == ".py":
        assert _symbol_exists(f, symbol), f"{symbol} not defined in {path}"


def test_document_has_rows():
    assert len(list(_rows())) >= 25


def test_every_mitigation_points_to_real_code_and_a_real_test_or_declares_a_gap():
    gaps = 0
    for id_, _threat, _mit, code, test in _rows():
        code_refs = REF.findall(code)
        assert code_refs, f"{id_}: no code reference"
        for r in code_refs:
            _check_ref(r)
        if test.startswith("GAP"):
            gaps += 1
            assert len(test) > 20, f"{id_}: a GAP needs a reason"
            continue
        test_refs = REF.findall(test)
        assert test_refs, f"{id_}: no test reference and not marked GAP"
        for r in test_refs:
            assert r.startswith("tests/"), f"{id_}: {r} is not a test path"
            _check_ref(r)
    assert gaps <= 3, "too many untested mitigations; add tests instead of more GAP rows"


def test_ids_are_unique():
    ids = [r[0] for r in _rows()]
    assert len(ids) == len(set(ids))
