"""
Trigger contention, don't benchmark it.

Fires N concurrent requests at one route and reports the status-code spread,
latency percentiles, and one example body per failure. Use it in
08_concurrency against POST /purchases to make "database is locked" show up,
then again after each change.

    python loadtest.py --n 200 --method POST --path "/purchases?db=writes"
    python loadtest.py --n 200 --path "/stats/revenue_by_state?db=idx_100k"

    # batched writes: 20 requests x 25 purchases each, one commit per request
    python loadtest.py --n 20 --method POST --path "/purchases/fast?db=writes" --batch 25

    # mixed: 90% GET --path, 10% POST --write-path (scenario S4)
    python loadtest.py --n 500 --path "/customers?customer_id=7&db=writes" \
                       --write-share 0.1 --write-path "/purchases?db=writes"

Needs httpx (installed with lab/api/starter_code).
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import random
import statistics
import time

import httpx

# customer 1 owns card 1 in every database make_dbs.py builds
SAMPLE_PURCHASE = {
    "customer_id": 1,
    "card_id": 1,
    "product_id": 1,
    "department": "Games",
    "amount": 9.99,
    "purchase_date": "2026-01-15",
}


async def _one(client: httpx.AsyncClient, method: str, url: str, batch: int = 0):
    t0 = time.perf_counter()
    try:
        if method == "POST":
            body = [SAMPLE_PURCHASE] * batch if batch else SAMPLE_PURCHASE
            r = await client.post(url, json=body)
        else:
            r = await client.get(url)
        code, body = r.status_code, r.text[:200]
    except Exception as exc:  # noqa: BLE001 -- we want to see everything
        code, body = "EXC", f"{type(exc).__name__}: {exc}"
    return code, body, (time.perf_counter() - t0) * 1000


def percentile(sorted_ms: list[float], p: float) -> float:
    if not sorted_ms:
        return float("nan")
    k = max(0, min(len(sorted_ms) - 1, round(p / 100 * len(sorted_ms)) - 1))
    return sorted_ms[k]


async def main_async(a):
    url = a.base.rstrip("/") + a.path
    write_url = a.base.rstrip("/") + a.write_path
    # every request is (method, url); with --write-share, that fraction are POSTs
    rng = random.Random(a.seed)
    calls = [("POST", write_url) if rng.random() < a.write_share else (a.method, url)
             for _ in range(a.n)]
    limits = httpx.Limits(max_connections=a.n, max_keepalive_connections=a.n)
    async with httpx.AsyncClient(timeout=a.timeout, limits=limits) as client:
        t0 = time.perf_counter()
        results = await asyncio.gather(*(_one(client, m, u, a.batch if u == url else 0)
                                         for m, u in calls))
        elapsed = time.perf_counter() - t0

    codes = collections.Counter(code for code, _, _ in results)
    ok = [ms for code, _, ms in results if isinstance(code, int) and 200 <= code < 300]
    all_ms = sorted(ms for _, _, ms in results)
    if a.write_share:
        writes = sum(m == "POST" for m, _ in calls)
        print(f"{a.method} {url}  +  POST {write_url}")
        print(f"  x{a.n} ({a.n - writes} reads, {writes} writes)  in {elapsed:.2f}s")
    else:
        print(f"{a.method} {url}  x{a.n}  in {elapsed:.2f}s")
    for code, count in sorted(codes.items(), key=lambda kv: str(kv[0])):
        print(f"  {code}: {count}")
    print(f"  succeeded/sec: {len(ok) / elapsed:,.1f}")
    if a.batch:
        print(f"  purchases written/sec: {len(ok) * a.batch / elapsed:,.1f}  ({a.batch} per request)")
    print(f"  latency ms (all requests): p50 {percentile(all_ms, 50):,.1f}  "
          f"p95 {percentile(all_ms, 95):,.1f}  p99 {percentile(all_ms, 99):,.1f}  "
          f"max {all_ms[-1]:,.1f}")
    if ok:
        print(f"  latency ms (successes):    p50 {statistics.median(ok):,.1f}  "
              f"p95 {percentile(sorted(ok), 95):,.1f}")
    # one example body per non-2xx outcome
    seen = set()
    for code, body, _ in results:
        if code not in seen and not (isinstance(code, int) and 200 <= code < 300):
            seen.add(code)
            print(f"  --- {code} ---\n  {body}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="http://127.0.0.1:8001")
    p.add_argument("--path", default="/purchases?db=writes")
    p.add_argument("--method", default="GET", choices=["GET", "POST"])
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--timeout", type=float, default=30, help="seconds per request")
    p.add_argument("--write-share", type=float, default=0.0,
                   help="fraction of requests sent as POST --write-path (S4 mix: 0.1)")
    p.add_argument("--write-path", default="/purchases?db=writes")
    p.add_argument("--seed", type=int, default=5303, help="seed for which requests are writes")
    p.add_argument("--batch", type=int, default=0,
                   help="POST a JSON array of this many purchases per request (for /purchases/fast)")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
