#!/usr/bin/env python3
"""
load_classroom.py -- the 1,000-row classroom CSV into the `classroom` database.

    python3 engines/04_mongodb/05_load/load_classroom.py

The same plan as SQLite's load_classroom.sql, done the MongoDB way:

  1. Stage. Every CSV row becomes one document in `staging_raw`, every value a
     string (so zipcode 01114 stays "01114").
  2. Transform inside the database. Aggregation pipelines read staging_raw and
     write each real collection with $merge, which inserts or replaces by _id.
     Parents first is no longer required: nothing enforces references.
  3. Drop staging, move the purchase-id counter past the loaded ids, verify.

Each pipeline below is one step. Read them next to the SQL version: $group is
GROUP BY, $setWindowFields is a window function, $lookup is a join, and
$merge is INSERT ... SELECT.

Connection: --uri, else $MONGO_URL, else the course default.
Needs: pip install pymongo
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from pymongo import ASCENDING, MongoClient

HERE = Path(__file__).resolve().parent
CSV = HERE.parents[2] / "datasets" / "store" / "classroom" / "store_flat.csv"
DEFAULT_URI = "mongodb://localhost:27017/?directConnection=true"

# 1 -> M/D/YYYY text to a real Date, used by the purchases pipeline
TO_DATE = {"$dateFromString": {"dateString": "$purchase_data", "format": "%m/%d/%Y"}}
TO_MONEY = {"$toDecimal": "$purchase_amount"}

PIPELINES = {
    # customers: one per row (the CSV has one purchase per customer), with
    # the state copied in and the card embedded
    "customers": [
        {"$project": {"_id": {"$toInt": "$id"}, "first_name": 1, "last_name": 1, "email": 1,
                      "address": 1, "zipcode": 1, "state_code": "$state",
                      "cards": [{"card_id": {"$toInt": "$id"}, "card_type": "$cc_type",
                                 "card_number": "$cc_number"}]}},
        {"$merge": {"into": "customers", "on": "_id", "whenMatched": "replace"}},
    ],
    # products: one per distinct name; ids numbered in name order, the same as SQLite
    "products": [
        {"$group": {"_id": "$prod_name", "unit_price": {"$max": TO_MONEY}}},
        {"$setWindowFields": {"sortBy": {"_id": 1}, "output": {"n": {"$documentNumber": {}}}}},
        {"$project": {"_id": "$n", "product_name": "$_id", "unit_price": 1}},
        {"$merge": {"into": "products", "on": "_id", "whenMatched": "replace"}},
    ],
    # purchases: look up the product id by name, copy in the extended reference
    "purchases": [
        {"$lookup": {"from": "products", "localField": "prod_name", "foreignField": "product_name",
                     "as": "p"}},
        {"$unwind": "$p"},
        {"$project": {"_id": {"$toInt": "$id"}, "customer_id": {"$toInt": "$id"},
                      "card_id": {"$toInt": "$id"}, "product_id": "$p._id",
                      "department": "$purchase_dept", "amount": TO_MONEY, "purchase_date": TO_DATE,
                      "product_name": "$prod_name", "state_code": "$state", "card_type": "$cc_type"}},
        {"$merge": {"into": "purchases", "on": "_id", "whenMatched": "replace"}},
    ],
}

SUMMARY = [
    {"$group": {"_id": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$purchase_date"}},
                        "state_code": "$state_code", "department": "$department"},
                "num_purchases": {"$sum": 1}, "revenue": {"$sum": "$amount"}}},
    {"$project": {"_id": 0, "month": "$_id.month", "state_code": "$_id.state_code",
                  "department": "$_id.department", "num_purchases": 1, "revenue": 1}},
    {"$out": "monthly_sales"},
]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--uri", default=os.environ.get("MONGO_URL", DEFAULT_URI))
    a = p.parse_args(argv)

    client = MongoClient(a.uri, serverSelectionTimeoutMS=5000)
    client.drop_database("classroom")
    db = client.classroom

    # 1. stage: strings only
    with open(CSV, newline="") as fh:
        rows = list(csv.DictReader(fh))
    db.staging_raw.insert_many(rows)
    print(f"staging_raw documents loaded: {db.staging_raw.count_documents({})}")

    # 2. transform, one pipeline per collection
    for name, pipeline in PIPELINES.items():
        db.staging_raw.aggregate(pipeline)
        print(f"{name:<14} {db[name].count_documents({}):>6}")
    db.purchases.aggregate(SUMMARY)

    # 3. clean up, counter, indexes, verify
    db.staging_raw.drop()
    top = db.purchases.find_one(sort=[("_id", -1)])["_id"]
    db.counters.insert_one({"_id": "purchase_id", "seq": top})
    db.customers.create_index([("email", ASCENDING)], unique=True)
    db.products.create_index([("product_name", ASCENDING)], unique=True)
    for keys in (["customer_id"], ["product_id"], ["department"], ["purchase_date"]):
        db.purchases.create_index([(k, ASCENDING) for k in keys])

    total = db.purchases.aggregate([{"$group": {"_id": None, "n": {"$sum": 1}, "revenue": {"$sum": "$amount"}}}]).next()
    zeros = db.customers.count_documents({"zipcode": {"$regex": "^0"}})
    print("== verification ==")
    print(f"purchases {total['n']}  revenue {total['revenue']}  zipcodes starting with 0: {zeros}")
    print("== rebuild complete ==")


if __name__ == "__main__":
    main()
