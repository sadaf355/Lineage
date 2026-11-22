#!/usr/bin/env python3
"""Write a CycloneDX 1.5 SBOM (JSON) from backend requirements*.txt and frontend/package-lock.json.
No network and no third-party packages. Usage: python scripts/make_sbom.py [out.json]"""
import json, re, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def py_components():
    out = []
    for f in sorted((ROOT / "backend").glob("requirements*.txt")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*==\s*([^\s;]+)", line)
            if m:
                n, v = m.group(1), m.group(3)
                out.append({"type": "library", "name": n, "version": v, "purl": f"pkg:pypi/{n.lower()}@{v}",
                            "properties": [{"name": "lineage:source", "value": f.name}]})
    return out


def npm_components():
    p = ROOT / "frontend" / "package-lock.json"
    if not p.exists():
        return []
    out = []
    for path, meta in json.loads(p.read_text(encoding="utf-8")).get("packages", {}).items():
        if not path or "version" not in meta:
            continue
        name = path.split("node_modules/")[-1]
        out.append({"type": "library", "name": name, "version": meta["version"], "purl": f"pkg:npm/{name}@{meta['version']}",
                    "properties": [{"name": "lineage:dev", "value": str(bool(meta.get("dev"))).lower()}]})
    return out


def build():
    comps = py_components() + npm_components()
    seen, uniq = set(), []
    for c in comps:
        k = (c["purl"], tuple(p["value"] for p in c.get("properties", [])))
        if k not in seen:
            seen.add(k); uniq.append(c)
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1,
            "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "component": {"type": "application", "name": "lineage"}},
            "components": uniq}


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "sbom.cdx.json")
    bom = build()
    out.write_text(json.dumps(bom, indent=1), encoding="utf-8")
    print(f"Wrote {out} with {len(bom['components'])} components")
