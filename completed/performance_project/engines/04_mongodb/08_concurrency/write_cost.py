#!/usr/bin/env python3
"""
write_cost.py -- what does a write cost, and what does the write concern buy?

Inserts purchases straight into the `writes` database, with no API in between,
so the numbers are MongoDB's own:

    python3 write_cost.py
    python3 write_cost.py --inserts 1000     # more per thread, steadier numbers

For each combination of

    write concern     {w: 1, j: false}  acknowledged once it's in memory
                      {w: 1, j: true}   ... once it's in the on-disk journal
                      {w: "majority"}   ... once a majority of the replica set has it
                                        (MongoDB's default; on one node, also the journal)
    threads           1, 8
    docs per write    1 (insert_one), 25 (insert_many)

it reports writes per second and documents per second.

Writes only to the `writes` database (build it with build_mongo.py --writes).
Connection: --uri, else $MONGO_URL, else the course default.

Needs: pip install pymongo
"""

from __future__ import annotations

import argparse
import os
import threading
import time
from datetime import datetime

from bson.decimal128 import Decimal128
from pymongo import MongoClient
from pymongo.write_concern import WriteConcern

DEFAULT_URI = "mongodb://localhost:27017/?directConnection=true"
CONCERNS = [("w:1 j:false", WriteConcern(w=1, j=False)),
            ("w:1 j:true", WriteConcern(w=1, j=True)),
            ("w:majority", WriteConcern(w="majority"))]


def doc() -> dict:
    return {"customer_id": 1, "card_id": 1, "product_id": 1, "department": "Games",
            "amount": Decimal128("9.99"), "purchase_date": datetime(2026, 1, 15),
            "product_name": "test", "state_code": "TX", "card_type": "visa"}


def run(client: MongoClient, wc: WriteConcern, threads: int, per_write: int, inserts: int) -> tuple[float, float]:
    coll = client.writes.get_collection("write_cost", write_concern=wc)
    start = threading.Barrier(threads + 1)

    def worker() -> None:
        start.wait()
        for _ in range(inserts // per_write):
            if per_write == 1:
                coll.insert_one(doc())
            else:
                coll.insert_many([doc() for _ in range(per_write)])

    ts = [threading.Thread(target=worker) for _ in range(threads)]
    for t in ts:
        t.start()
    start.wait()
    t0 = time.perf_counter()
    for t in ts:
        t.join()
    secs = time.perf_counter() - t0
    docs = threads * (inserts // per_write) * per_write
    return docs / per_write / secs, docs / secs


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inserts", type=int, default=400, help="documents each thread inserts (default 400)")
    p.add_argument("--uri", default=os.environ.get("MONGO_URL", DEFAULT_URI))
    a = p.parse_args(argv)

    client = MongoClient(a.uri, maxPoolSize=16)
    if "writes" not in client.list_database_names():
        raise SystemExit("Database writes not found. Run build_mongo.py --writes first.")
    client.writes.write_cost.drop()

    print(f"{'write concern':<14} {'threads':>7} {'docs/write':>10} {'writes/sec':>11} {'docs/sec':>10}")
    for per_write in (1, 25):
        for threads in (1, 8):
            for label, wc in CONCERNS:
                writes, docs = run(client, wc, threads, per_write, a.inserts)
                print(f"{label:<14} {threads:>7} {per_write:>10} {writes:>11,.0f} {docs:>10,.0f}")
    client.writes.write_cost.drop()


if __name__ == "__main__":
    main()
