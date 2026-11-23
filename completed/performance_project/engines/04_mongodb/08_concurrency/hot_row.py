#!/usr/bin/env python3
"""
hot_row.py -- many clients sell the same product at once. Does every sale count?

The MongoDB twin of engines/03_postgres/08_concurrency/hot_row.py. One
document, writes.stock {_id: 1, on_hand: N}, holds how many units of product 1
are on hand. Each worker thread sells one unit at a time, over and over. Every
strategy makes exactly as many sales as there were units, so on_hand should
end at 0. Anything else is a sale the database lost track of.

    python3 hot_row.py                         # all four strategies
    python3 hot_row.py --strategy naive        # just one
    python3 hot_row.py --workers 16 --sales 100

The four ways to sell one unit:

    naive        find_one() the document; compute on_hand - 1 in Python;
                 update_one({$set: {on_hand: <that>}})
    atomic       update_one({$inc: {on_hand: -1}})         (one operation)
    find_modify  find_one_and_update({$inc: ...})          (atomic, and returns the new value)
    transaction  naive, inside a multi-document transaction, retried whenever
                 MongoDB reports a write conflict (needs a replica set)

Writes only to the `writes` database (build it with build_mongo.py --writes).
Connection: --uri, else $MONGO_URL, else the course default.

Needs: pip install pymongo
"""

from __future__ import annotations

import argparse
import os
import threading
import time

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError

DEFAULT_URI = "mongodb://localhost:27017/?directConnection=true"
STRATEGIES = ["naive", "atomic", "find_modify", "transaction"]


def sell_one(client: MongoClient, strategy: str, seen: list[str]) -> int:
    """Sell one unit. Returns how many times it had to retry; keeps the first error text."""
    stock = client.writes.stock
    if strategy == "atomic":
        stock.update_one({"_id": 1}, {"$inc": {"on_hand": -1}})
        return 0
    if strategy == "find_modify":
        stock.find_one_and_update({"_id": 1}, {"$inc": {"on_hand": -1}},
                                  return_document=ReturnDocument.AFTER)
        return 0
    if strategy == "naive":
        n = stock.find_one({"_id": 1})["on_hand"]
        stock.update_one({"_id": 1}, {"$set": {"on_hand": n - 1}})
        return 0
    retries = 0                                   # strategy == "transaction"
    while True:
        try:
            with client.start_session() as s:
                with s.start_transaction():
                    n = stock.find_one({"_id": 1}, session=s)["on_hand"]
                    stock.update_one({"_id": 1}, {"$set": {"on_hand": n - 1}}, session=s)
            return retries
        except PyMongoError as exc:
            if not exc.has_error_label("TransientTransactionError"):
                raise
            if not seen:
                seen.append(str(exc).split(", full error")[0])
            retries += 1                          # someone else changed the document first: try again


def run(uri: str, strategy: str, workers: int, sales: int) -> dict:
    units = workers * sales
    client = MongoClient(uri, maxPoolSize=workers + 2)
    if "writes" not in client.list_database_names():
        raise SystemExit("Database writes not found. Run build_mongo.py --writes first.")
    client.writes.stock.replace_one({"_id": 1}, {"_id": 1, "on_hand": units}, upsert=True)

    retries = [0] * workers
    first_error: list[str] = []
    start = threading.Barrier(workers + 1)

    def worker(i: int) -> None:
        start.wait()
        for _ in range(sales):
            retries[i] += sell_one(client, strategy, first_error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    for t in threads:
        t.start()
    start.wait()
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    seconds = time.perf_counter() - t0
    left = client.writes.stock.find_one({"_id": 1})["on_hand"]
    client.close()
    return {"strategy": strategy, "on_hand_after": left, "retries": sum(retries),
            "seconds": seconds, "sales_per_sec": units / seconds,
            "error": first_error[0] if first_error else ""}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--strategy", choices=STRATEGIES, nargs="+", default=STRATEGIES)
    p.add_argument("--workers", type=int, default=8, help="threads selling at once")
    p.add_argument("--sales", type=int, default=200, help="units each worker sells")
    p.add_argument("--uri", default=os.environ.get("MONGO_URL", DEFAULT_URI))
    a = p.parse_args(argv)

    print(f"{a.workers} workers x {a.sales} sales = {a.workers * a.sales} units, all from one document\n")
    print(f"{'strategy':<13} {'on_hand after':>13} {'retries':>8} {'seconds':>8} {'sales/sec':>10}")
    errors_seen: list[str] = []
    for s in a.strategy:
        r = run(a.uri, s, a.workers, a.sales)
        print(f"{r['strategy']:<13} {r['on_hand_after']:>13,} {r['retries']:>8,} "
              f"{r['seconds']:>8.2f} {r['sales_per_sec']:>10,.0f}")
        if r["error"]:
            errors_seen.append(f"{s}: {r['error']}")
    print("\non_hand after should be 0. Anything above 0 is sales the database lost.")
    for e in errors_seen:
        print("first error retried --", e)


if __name__ == "__main__":
    main()
