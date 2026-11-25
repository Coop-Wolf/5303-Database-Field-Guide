# setup_db.py  (required: "database setup script")
#
# Builds shop.db: the purchases table with 500,000 rows (handout section 4.2).
# Seed the random generator so anyone who runs this gets the same data.
#
# If Part E needs an index for the "simple indexed lookup" query, create it
# here too, so the database is fully reproducible from this one script.
#
# shop.db itself is generated: don't commit it.

import random
import sqlite3

random.seed(42)

with sqlite3.connect("shop.db") as db:
    db.execute("DROP TABLE IF EXISTS purchases")

    db.execute("""
        CREATE TABLE purchases (
            purchase_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount REAL
        )
    """)

    rows = [
        (
            random.randint(1, 10000),
            round(random.uniform(5, 500), 2)
        )
        for _ in range(500000)
    ]

    db.executemany("""
        INSERT INTO purchases (customer_id, amount)
        VALUES (?, ?)
    """, rows)

print("Created 500,000 purchase records.")