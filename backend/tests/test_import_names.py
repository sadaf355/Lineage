"""Every `from app.x import name` must resolve to a real module or a top-level name.

Catches broken imports that only show up when the API starts (for example importing a module
name from a module that does not define it). Pure ast, no framework needed.
"""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _top_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        names.add(x.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, (ast.If, ast.Try)):
            for x in ast.walk(n):
                if isinstance(x, (ast.FunctionDef, ast.ClassDef)):
                    names.add(x.name)
                elif isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                    names.add(x.id)
                elif isinstance(x, (ast.Import, ast.ImportFrom)):
                    for a in x.names:
                        names.add((a.asname or a.name).split(".")[0])
    return names


def test_app_imports_resolve():
    problems = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.startswith("app")):
                continue
            target = APP.parent / Path(*node.module.split("."))
            if target.is_dir():
                init = target / "__init__.py"
                for a in node.names:
                    if (target / f"{a.name}.py").exists() or (target / a.name).is_dir():
                        continue
                    if not init.exists() or a.name not in _top_names(init):
                        problems.append(f"{path.relative_to(APP)}:{node.lineno} {node.module}.{a.name}")
            elif target.with_suffix(".py").exists():
                names = _top_names(target.with_suffix(".py"))
                for a in node.names:
                    if a.name != "*" and a.name not in names:
                        problems.append(f"{path.relative_to(APP)}:{node.lineno} {node.module}.{a.name}")
            else:
                problems.append(f"{path.relative_to(APP)}:{node.lineno} missing module {node.module}")
    assert not problems, "\n".join(problems)
