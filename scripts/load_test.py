#!/usr/bin/env python3
"""Load test for a RUNNING LINEAGE API. Standard library + `requests` only.

    python scripts/load_test.py --base http://127.0.0.1:8000 --email demo@lineage.app --password '...' \
        --users 20 --duration 60 --json results.json

What it does
* Logs in ONCE (login is rate-limited to RATE_LIMIT_LOGIN_PER_MINUTE per IP+email) and shares the token.
* Creates ONE disposable investigation, then runs N concurrent virtual users for the duration, each looping over a
  weighted mix of read endpoints a real investigator hits (dashboard list, case, sources, evidence, fingerprint,
  progress data, manifest verify). Optionally exercises manifest signing (--include-writes).
* Records per-endpoint count, error count, HTTP 429 count (rate limiting is expected behaviour, not failure) and
  p50/p95/p99 latency, plus overall throughput. Deletes nothing it did not create (it leaves the test case; delete it).

What it does NOT do
* No uploads or detection runs (those are CPU-heavy and rate-limited; load-test them separately with a real model).
* It is a client on one machine: if the client saturates (watch CPU), the numbers describe the client, not the server.
* Do not run against production, or against a system holding real case data.

Record the output together with: git commit, machine specs, DB (SQLite/Postgres), worker count, and Redis on/off.
"""
import argparse, json, statistics, sys, threading, time, random
import requests


def pct(xs, p):
    if not xs: return None
    xs = sorted(xs); k = min(len(xs) - 1, int(round((p / 100) * (len(xs) - 1)))); return round(xs[k] * 1000, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--email", required=True); ap.add_argument("--password", required=True)
    ap.add_argument("--users", type=int, default=10); ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--include-writes", action="store_true", help="also sign integrity manifests (creates rows)")
    ap.add_argument("--json"); a = ap.parse_args()
    base = a.base.rstrip("/")
    r = requests.post(f"{base}/auth/login", data={"username": a.email, "password": a.password}, timeout=15)
    if r.status_code != 200: sys.exit(f"Login failed: HTTP {r.status_code} {r.text[:200]}")
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}
    c = requests.post(f"{base}/incidents", json={"title": f"LOAD TEST {int(time.time())} — delete me", "description": "load test", "victim_ref": "LT"}, headers=H, timeout=15)
    if c.status_code not in (200, 201): sys.exit(f"Could not create test case: {c.status_code} {c.text[:200]}")
    iid = c.json()["id"]
    mix = [("GET /incidents", "GET", "/incidents", 4), ("GET /incidents/{id}", "GET", f"/incidents/{iid}", 3),
           ("GET sources", "GET", f"/incidents/{iid}/sources", 3), ("GET evidence", "GET", f"/incidents/{iid}/evidence", 3),
           ("GET media", "GET", f"/incidents/{iid}/media", 2), ("GET attribution-gap", "GET", f"/incidents/{iid}/attribution-gap", 1),
           ("GET /health", "GET", "/health", 1)]
    if a.include_writes: mix.append(("POST manifest", "POST", f"/incidents/{iid}/evidence/manifest", 1))
    pool = [m for m in mix for _ in range(m[3])]
    lock = threading.Lock(); stats = {m[0]: {"ok": 0, "err": 0, "rate_limited": 0, "lat": []} for m in mix}
    stop = time.time() + a.duration

    def worker():
        s = requests.Session(); s.headers.update(H); rnd = random.Random()
        while time.time() < stop:
            name, method, path, _ = rnd.choice(pool); t = time.perf_counter()
            try:
                resp = s.request(method, base + path, timeout=30); dt = time.perf_counter() - t; code = resp.status_code
            except requests.RequestException:
                dt, code = time.perf_counter() - t, 0
            with lock:
                st = stats[name]
                if code == 429: st["rate_limited"] += 1
                elif 200 <= code < 300 or code == 404 and name == "GET attribution-gap": st["ok"] += 1; st["lat"].append(dt)
                else: st["err"] += 1
    t0 = time.time(); ths = [threading.Thread(target=worker, daemon=True) for _ in range(a.users)]
    [t.start() for t in ths]; [t.join() for t in ths]; wall = time.time() - t0
    rows, total, errs, rl, allv = {}, 0, 0, 0, []
    for name, st in stats.items():
        n = st["ok"] + st["err"] + st["rate_limited"]; total += n; errs += st["err"]; rl += st["rate_limited"]; allv += st["lat"]
        rows[name] = {"requests": n, "errors": st["err"], "rate_limited_429": st["rate_limited"], "p50_ms": pct(st["lat"], 50), "p95_ms": pct(st["lat"], 95), "p99_ms": pct(st["lat"], 99)}
    out = {"base": base, "virtual_users": a.users, "duration_s": round(wall, 1), "total_requests": total, "throughput_rps": round(total / wall, 1),
           "error_rate": round(errs / total, 4) if total else None, "rate_limited": rl, "overall_p50_ms": pct(allv, 50), "overall_p95_ms": pct(allv, 95), "overall_p99_ms": pct(allv, 99),
           "endpoints": rows, "test_case_id": iid, "note": "Delete the test case. Client and server share this machine unless you ran it elsewhere."}
    print(json.dumps(out, indent=2))
    if a.json: open(a.json, "w").write(json.dumps(out, indent=2))
    sys.exit(1 if out["error_rate"] and out["error_rate"] > 0.01 else 0)


if __name__ == "__main__":
    main()
