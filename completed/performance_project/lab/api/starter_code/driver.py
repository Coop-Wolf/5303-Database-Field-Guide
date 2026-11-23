"""
driver.py -- run every read query against every database through the API.

Start the API first (python -m app.main), then from lab/api/starter_code/:

    python driver.py                       # all sizes, both variants
    python driver.py --sizes 10k 100k      # skip 1m while you are debugging
    python driver.py --only Q08 Q09        # rerun a few queries
    python driver.py --base http://127.0.0.1:8002 --out results_duckdb   # another engine's API

For each (query, database) it calls the route RUNS times and keeps the median
of the elapsed_ms values the API reports. Output, in results/ (or --out):

    results.csv    one row per (query, database): time, rows, plan
    results.md     the same numbers as a table, ready to paste into FINDINGS

The driver only knows the route contract. It doesn't care which engine
answers. The one exception is facts(), which reads two values from the SQLite
files; every engine loads the same rows, so those values hold everywhere.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import statistics
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
# FIELD_GUIDE: where the field-guide clone is, if this folder was copied out of it
ROOT = Path(os.environ.get("FIELD_GUIDE", HERE.parents[2])).expanduser()
DATA = Path(
    os.environ.get("DATA_DIR", ROOT / "datasets" / "store" / "generated" / "sqlite")
)
OUT = HERE / "results"
RUNS = 5
SIZES = ["10k", "100k", "1m"]
VARIANTS = ["noidx", "idx"]

# (query id, route, query-string params), in catalog order
# {whale} = the customer with the most purchases in that database
# {deep}  = a purchase_id 90% of the way through the table
JOBS = [
    ("Q01", "/customers", {"customer_id": "{whale}"}),
    ("Q02", "/products", {"limit": 50, "offset": 0}),
    ("Q03", "/products/start/end", {"start": "2025-03-01", "end": "2025-03-08"}),
    ("Q04", "/customers/purchases", {"customer_id": "{whale}"}),
    ("Q05", "/stats/department_count", {"department": "Games"}),
    ("Q06", "/customers/streaks", {"customer_id": "{whale}"}),
    ("Q07", "/stats/leaderboard", {"start": "2026-06-02", "end": "2026-09-01"}),
    ("Q08", "/products/dead/state", {"state": "TX"}),
    ("Q09", "/stats/revenue_by_state", {}),
    ("Q10", "/products/top", {}),
    ("Q11", "/purchases/page", {"offset": "{deep}"}),
    ("Q11-fast", "/purchases/page/fast", {"after_id": "{deep}"}),
    ("Q12", "/purchases/sample", {}),
    ("Q12-fast", "/purchases/sample/fast", {}),
    ("Q13", "/stats/revenue_by_month", {}),
    ("Q13-fast", "/stats/revenue_by_month/fast", {}),
    (
        "Q14",
        "/reports/cube",
        {"start": "2025-01-01", "end": "2026-01-01", "min_purchases": 10},
    ),
    (
        "Q14-fast",
        "/reports/cube/fast",
        {"start": "2025-01-01", "end": "2026-01-01", "min_purchases": 10},
    ),
]


def facts(db_name: str) -> dict[str, int]:
    """Look up the per-database values the routes need (read-only)."""
    path = DATA / f"{db_name}.db"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run datasets/store/generator/make_dbs.py first."
        )
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    whale = con.execute(
        "SELECT customer_id FROM purchases GROUP BY customer_id "
        "ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()[0]
    max_id = con.execute("SELECT MAX(purchase_id) FROM purchases").fetchone()[0]
    con.close()
    return {"whale": whale, "deep": int(max_id * 0.9)}


def fill(value, f: dict[str, int]):
    return value.format(**f) if isinstance(value, str) else value


def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--base", default="http://127.0.0.1:8001")
    p.add_argument("--sizes", nargs="+", default=SIZES, choices=SIZES)
    p.add_argument("--only", nargs="+", help="query ids to run, e.g. Q08 Q11-fast")
    p.add_argument(
        "--runs", type=int, default=RUNS, help=f"calls per (query, db); default {RUNS}"
    )
    p.add_argument(
        "--out",
        default=OUT,
        type=Path,
        help="folder for results.csv and results.md; default results/",
    )
    a = p.parse_args(argv)

    jobs = [j for j in JOBS if not a.only or j[0] in a.only]
    dbs = [f"{v}_{s}" for s in a.sizes for v in VARIANTS]
    results = []

    with httpx.Client(base_url=a.base, timeout=120) as client:
        try:
            client.get("/health").raise_for_status()
        except httpx.HTTPError as exc:
            raise SystemExit(
                f"API not reachable at {a.base} ({exc}). Start it with: python -m app.main"
            )
        for db in dbs:
            f = facts(db)
            for qid, route, params in jobs:
                print(f"qid:{qid}")
                q = {k: fill(v, f) for k, v in params.items()} | {"db": db}
                times = []
                for _ in range(a.runs):
                    r = client.get(route, params=q)
                    if r.status_code != 200:
                        raise SystemExit(
                            f"{qid} {route} on {db}: HTTP {r.status_code}\n{r.text[:500]}"
                        )
                    body = r.json()
                    times.append(body["elapsed_ms"])
                ms = statistics.median(times)
                results.append(
                    {
                        "query": qid,
                        "db": db,
                        "median_ms": ms,
                        "rows": body["row_count"],
                        "plan": " | ".join(body["plan"]),
                    }
                )
                print(f"{db:<11} {qid:<9} {ms:>10.2f} ms  {body['row_count']:>4} rows")

    a.out.mkdir(exist_ok=True)
    with open(a.out / "results.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)

    # pivot: one row per query, one column per database
    ms = {(r["query"], r["db"]): r["median_ms"] for r in results}
    lines = [
        "| Query | " + " | ".join(dbs) + " |",
        "| :--- | " + " | ".join("---:" for _ in dbs) + " |",
    ]
    for qid, _, _ in jobs:
        lines.append(
            f"| {qid} | " + " | ".join(f"{ms[(qid, d)]:.2f}" for d in dbs) + " |"
        )
    (a.out / "results.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {a.out / 'results.csv'} and {a.out / 'results.md'}")


if __name__ == "__main__":
    main()
