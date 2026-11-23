#!/usr/bin/env python3
"""
build_mongo.py -- build the MongoDB experiment databases from the SQLite files.

    python3 datasets/store/generator/make_dbs.py        # first: the SQLite files
    python3 engines/04_mongodb/05_load/build_mongo.py               # 10k, 100k, 1m
    python3 engines/04_mongodb/05_load/build_mongo.py --sizes 10k
    python3 engines/04_mongodb/05_load/build_mongo.py --writes      # scratch copy for 08

Each experiment database is a MongoDB **database** with the same name as the
SQLite file: idx_10k, noidx_1m, ... plus writes. It reads idx_<size>.db with
Python's sqlite3, so every engine holds the same facts, and reshapes them into
the document design from ../04_model/:

    customers      {_id: customer_id, name, email, address, zipcode, state_code,
                    cards: [{card_id, card_type, card_number}, ...]}
    products       {_id: product_id, product_name, unit_price}
    purchases      {_id: purchase_id, customer_id, card_id, product_id, department,
                    amount, purchase_date,
                    product_name, state_code, card_type}    <- copied in (extended reference)
    monthly_sales  {month, state_code, department, num_purchases, revenue}
    counters       {_id: "purchase_id", seq: <highest id>}  <- where new ids come from

idx_<size> gets the indexes in INDEXES below; noidx_<size> only _id and the
unique ones. Money is Decimal128 (exact), dates are real Dates.

Connection: --uri, else $MONGO_URL, else the course default below.
Re-running is safe: each database is dropped and rebuilt.

Needs: pip install pymongo
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from bson.decimal128 import Decimal128
from pymongo import ASCENDING, MongoClient

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SQLITE_DIR = Path(os.environ.get("DATA_DIR", ROOT / "datasets" / "store" / "generated" / "sqlite")).expanduser()
DEFAULT_URI = "mongodb://localhost:27017/?directConnection=true"
SIZES = ["10k", "100k", "1m", "practice"]
BATCH = 10_000

# The unique constraints every variant keeps (SQLite's noidx keeps its UNIQUEs too).
UNIQUE = [
    ("customers", [("email", ASCENDING)]),
    ("customers", [("cards.card_number", ASCENDING)]),
    ("products", [("product_name", ASCENDING)]),
    ("monthly_sales", [("month", ASCENDING), ("state_code", ASCENDING), ("department", ASCENDING)]),
]

# The same ten secondary indexes SQLite's idx_* files have, on this design's fields.
# (The two on zipcodes/cards are folded in: zipcode lives on the customer, cards
# are embedded in the customer, so they have no collection of their own.)
INDEXES = [
    ("customers", [("zipcode", ASCENDING)]),
    ("customers", [("cards.card_id", ASCENDING)]),
    ("purchases", [("customer_id", ASCENDING)]),
    ("purchases", [("product_id", ASCENDING)]),
    ("purchases", [("department", ASCENDING)]),
    ("purchases", [("purchase_date", ASCENDING)]),
    ("purchases", [("customer_id", ASCENDING), ("amount", ASCENDING)]),
    ("purchases", [("product_id", ASCENDING), ("amount", ASCENDING)]),
    ("purchases", [("purchase_date", ASCENDING), ("customer_id", ASCENDING), ("amount", ASCENDING)]),
    ("customers", [("state_code", ASCENDING)]),
]


def money(x) -> Decimal128:
    return Decimal128(Decimal(str(x)).quantize(Decimal("0.01")))


def day(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%d")


def batches(rows, size=BATCH):
    batch = []
    for r in rows:
        batch.append(r)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def build(client: MongoClient, name: str, source: Path, with_indexes: bool) -> tuple[int, int, float]:
    t0 = time.perf_counter()
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    client.drop_database(name)
    db = client[name]

    cards: dict[int, list] = {}
    for card_id, customer_id, card_type, card_number in src.execute(
            "SELECT card_id, customer_id, card_type, card_number FROM cards ORDER BY card_id"):
        cards.setdefault(customer_id, []).append(
            {"card_id": card_id, "card_type": card_type, "card_number": card_number})
    customers = (
        {"_id": cid, "first_name": f, "last_name": l, "email": e, "address": a,
         "zipcode": z, "state_code": s, "cards": cards.get(cid, [])}
        for cid, f, l, e, a, z, s in src.execute(
            "SELECT c.customer_id, first_name, last_name, email, address, c.zipcode, z.state_code "
            "FROM customers c JOIN zipcodes z ON z.zipcode = c.zipcode ORDER BY c.customer_id"))
    for b in batches(customers):
        db.customers.insert_many(b, ordered=False)

    products = ({"_id": pid, "product_name": n, "unit_price": money(p)}
                for pid, n, p in src.execute("SELECT product_id, product_name, unit_price FROM products"))
    for b in batches(products):
        db.products.insert_many(b, ordered=False)

    purchases = (
        {"_id": pid, "customer_id": cid, "card_id": card, "product_id": prod, "department": dept,
         "amount": money(amt), "purchase_date": day(d),
         "product_name": pname, "state_code": st, "card_type": ctype}
        for pid, cid, card, prod, dept, amt, d, pname, st, ctype in src.execute(
            "SELECT pu.purchase_id, pu.customer_id, pu.card_id, pu.product_id, pu.department, "
            "       pu.amount, pu.purchase_date, pr.product_name, z.state_code, cd.card_type "
            "FROM purchases pu "
            "JOIN products  pr ON pr.product_id = pu.product_id "
            "JOIN customers c  ON c.customer_id = pu.customer_id "
            "JOIN zipcodes  z  ON z.zipcode     = c.zipcode "
            "JOIN cards     cd ON cd.card_id    = pu.card_id "
            "ORDER BY pu.purchase_id"))
    for b in batches(purchases):
        db.purchases.insert_many(b, ordered=False)

    # The rollup, built by MongoDB itself from the purchases it now holds.
    db.purchases.aggregate([
        {"$group": {"_id": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$purchase_date"}},
                            "state_code": "$state_code", "department": "$department"},
                    "num_purchases": {"$sum": 1}, "revenue": {"$sum": "$amount"}}},
        {"$project": {"_id": 0, "month": "$_id.month", "state_code": "$_id.state_code",
                      "department": "$_id.department", "num_purchases": 1, "revenue": 1}},
        {"$out": "monthly_sales"},
    ])

    top = db.purchases.find_one(sort=[("_id", -1)], projection={"_id": 1})
    db.counters.insert_one({"_id": "purchase_id", "seq": top["_id"] if top else 0})

    for coll, keys in UNIQUE:
        db[coll].create_index(keys, unique=True)
    if with_indexes:
        for coll, keys in INDEXES:
            db[coll].create_index(keys)

    client.admin.command("fsync")                 # flush to disk, so the sizes are real
    n = db.purchases.estimated_document_count()
    stats = db.command("dbStats")
    size = int(stats["storageSize"] + stats["indexSize"])
    src.close()
    return n, size, time.perf_counter() - t0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sizes", nargs="+", default=["10k", "100k", "1m"], choices=SIZES)
    p.add_argument("--writes", action="store_true",
                   help="only (re)build the scratch database 'writes' from idx_100k.db")
    p.add_argument("--uri", default=os.environ.get("MONGO_URL", DEFAULT_URI))
    a = p.parse_args(argv)

    client = MongoClient(a.uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        raise SystemExit(f"Can't reach MongoDB at {a.uri}\n{exc}\nIs the server running? (see 02_install/)")

    jobs = ([("writes", "100k", True)] if a.writes else
            [(f"{v}_{s}", s, v == "idx") for s in a.sizes for v in ("idx", "noidx")])
    for name, size, with_indexes in jobs:
        source = SQLITE_DIR / f"idx_{size}.db"
        if not source.exists():
            raise SystemExit(f"{source} not found. Run datasets/store/generator/make_dbs.py first.")
        n, size_bytes, secs = build(client, name, source, with_indexes)
        print(f"{name:<12} {n:>10,} purchases  {size_bytes / 1e6:7.1f} MB  {secs:5.1f} s")


if __name__ == "__main__":
    main()
