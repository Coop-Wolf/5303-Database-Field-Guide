"""
Assignment 01 -- SQLite behind a FastAPI service.

Run it from the starter folder, either way:
    python -m app.main                   # uses the __main__ block below (port 8001)
    uvicorn app.main:app --port 8001     # equivalent

Then open http://127.0.0.1:8001/docs

(Do NOT run `python app/main.py` -- the package-relative imports need the
`app.` package context, which only `-m app.main` / uvicorn provide.)

Q01 below is a worked example. Add Q02-Q15 the same way, copying the SQL from
../QUERIES.md. Every experiment route takes ?db=<name> (e.g. ?db=noidx_1m).
"""

from __future__ import annotations

import random  # noqa: F401  -- you need this for Q12 /fast
import sqlite3

from fastapi import Depends, FastAPI, HTTPException  # noqa: F401
from fastapi.responses import RedirectResponse

from .auth import require_api_key
from .experiment import get_exp_db, run_query
from .models import NewPurchase  # noqa: F401  -- you need this for Q15

app = FastAPI(title="SQLite API -- Assignment 01")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Bare host -> the Swagger UI."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# --------------------------------------------------------------------------- #
# SQL -- copied from ../QUERIES.md
# --------------------------------------------------------------------------- #

Q01_SQL = """
SELECT c.customer_id, c.first_name, c.last_name, c.email, c.zipcode, z.state_code
FROM customers c
JOIN zipcodes z ON z.zipcode = c.zipcode
WHERE c.customer_id = :customer_id
"""

Q02_SQL = """SELECT product_id, product_name, unit_price
FROM products
ORDER BY product_id
LIMIT :limit OFFSET :offset"""
Q03_SQL = """SELECT purchase_id, customer_id, product_id, department, amount, purchase_date
FROM purchases
WHERE purchase_date >= :start AND purchase_date < :end
ORDER BY purchase_date
LIMIT 100"""
Q04_SQL = """SELECT pu.purchase_id, pu.purchase_date, pr.product_name, pu.department, pu.amount
FROM purchases pu
JOIN products pr ON pr.product_id = pu.product_id
WHERE pu.customer_id = :customer_id
ORDER BY pu.purchase_date DESC
LIMIT 100"""
Q05_SQL = """SELECT COUNT(*) AS num_purchases
FROM purchases
WHERE department = :department"""
Q06_SQL = """WITH days AS (
    SELECT DISTINCT purchase_date AS day
    FROM purchases
    WHERE customer_id = :customer_id
),
islands AS (
    SELECT day,
           julianday(day) - ROW_NUMBER() OVER (ORDER BY day) AS grp
    FROM days
)
SELECT MIN(day) AS streak_start, MAX(day) AS streak_end, COUNT(*) AS days
FROM islands
GROUP BY grp
HAVING COUNT(*) >= 2
ORDER BY days DESC, streak_start
LIMIT 10"""
Q07_SQL = """WITH spend AS (
    SELECT customer_id, SUM(amount) AS total
    FROM purchases
    WHERE purchase_date >= :start AND purchase_date < :end
    GROUP BY customer_id
)
SELECT customer_id, ROUND(total, 2) AS total,
       RANK() OVER (ORDER BY total DESC) AS rank
FROM spend
ORDER BY total DESC
LIMIT 20"""
Q08_SQL = """SELECT pr.product_id, pr.product_name
FROM products pr
WHERE NOT EXISTS (
    SELECT 1
    FROM purchases pu
    JOIN customers c ON c.customer_id = pu.customer_id
    JOIN zipcodes  z ON z.zipcode     = c.zipcode
    WHERE pu.product_id = pr.product_id
      AND z.state_code  = :state
)
ORDER BY pr.product_id
LIMIT 100"""
Q09_SQL = """SELECT z.state_code, COUNT(*) AS num_purchases, ROUND(SUM(pu.amount), 2) AS revenue
FROM purchases pu
JOIN customers c ON c.customer_id = pu.customer_id
JOIN zipcodes  z ON z.zipcode     = c.zipcode
GROUP BY z.state_code
ORDER BY revenue DESC"""
Q010_SQL = """SELECT pr.product_id, pr.product_name,
       COUNT(*) AS num_purchases, ROUND(SUM(pu.amount), 2) AS revenue
FROM purchases pu
JOIN products pr ON pr.product_id = pu.product_id
GROUP BY pr.product_id
ORDER BY revenue DESC
LIMIT 10"""
Q011_SLOW_SQL = """SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
ORDER BY purchase_id
LIMIT 50 OFFSET :offset"""
Q011_FAST_SQL = """SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
WHERE purchase_id > :after_id
ORDER BY purchase_id
LIMIT 50"""
Q012_SLOW_SQL = """SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
ORDER BY random()
LIMIT 10"""
Q012_FAST_SQL = """SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
WHERE purchase_id IN (:id1, :id2, :id3, :id4, :id5, :id6, :id7, :id8, :id9, :id10)"""
Q013_SLOW_SQL = """SELECT substr(purchase_date, 1, 7) AS month,
       COUNT(*) AS num_purchases, ROUND(SUM(amount), 2) AS revenue
FROM purchases
GROUP BY month
ORDER BY month"""
Q013_FAST_SQL = """SELECT month, SUM(num_purchases) AS num_purchases, ROUND(SUM(revenue), 2) AS revenue
FROM monthly_sales
GROUP BY month
ORDER BY month"""
Q014_SLOW_SQL = """WITH base AS (
    SELECT z.state_code, pu.department,
           substr(pu.purchase_date, 1, 7) AS month, pu.amount
    FROM purchases pu
    JOIN customers c ON c.customer_id = pu.customer_id
    JOIN zipcodes  z ON z.zipcode     = c.zipcode
    WHERE pu.purchase_date >= :start AND pu.purchase_date < :end
),
cube AS (
    SELECT state_code, department, month,
           COUNT(*) AS num_purchases, SUM(amount) AS revenue
    FROM base
    GROUP BY state_code, department, month
)
SELECT state_code, department, month, num_purchases, ROUND(revenue, 2) AS revenue
FROM cube
WHERE num_purchases >= :min_purchases
ORDER BY revenue DESC
LIMIT 50"""
Q014_FAST_SQL = """SELECT state_code, department, month, num_purchases, ROUND(revenue, 2) AS revenue
FROM monthly_sales
WHERE month >= substr(:start, 1, 7) AND month < substr(:end, 1, 7)
  AND num_purchases >= :min_purchases
ORDER BY revenue DESC
LIMIT 50"""


# TODO: Q02_SQL ... Q14_FAST_SQL


# --------------------------------------------------------------------------- #
# Routes
#
# FastAPI matches top to bottom, so keep the fixed paths (/purchases/page,
# /purchases/sample, .../fast) above anything shaped like /purchases/{x}.
# --------------------------------------------------------------------------- #

# Phase 1 ------------------------------------------------------------------- #

@app.get("/customers/{customer_id}", dependencies=[Depends(require_api_key)])
def q01_customer(customer_id: int, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q01_SQL, {"customer_id": customer_id})


# TODO Q02  GET /products?limit=&offset=
@app.get("/products", dependencies=[Depends(require_api_key)])
def q02_products(limit: int = 10, offset: int = 0, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q02_SQL, {"limit": limit, "offset": offset})


# TODO Q03  GET /purchases?start=&end=
@app.get("/purchases", dependencies=[Depends(require_api_key)])
def q03_purchases(start: str, end: str, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q03_SQL, {"start": start, "end": end})


# Phase 2 ------------------------------------------------------------------- #

# TODO Q04  GET /customers/{customer_id}/purchases
@app.get("/customers/{customer_id}/purchases", dependencies=[Depends(require_api_key)])
def q04_customer_purchases(customer_id: int, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q04_SQL, {"customer_id": customer_id})


# TODO Q05  GET /stats/department-count?department=
@app.get("/stats/department-count", dependencies=[Depends(require_api_key)])
def q05_department_count(department: str, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q05_SQL, {"department": department})


# TODO Q06  GET /customers/{customer_id}/streaks
@app.get("/customers/{customer_id}/streaks", dependencies=[Depends(require_api_key)])
def q06_customer_streaks(customer_id: int, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q06_SQL, {"customer_id": customer_id})

# TODO Q07  GET /stats/leaderboard?start=&end=
@app.get("/stats/leaderboard", dependencies=[Depends(require_api_key)])
def q07_leaderboard(start: str, end: str, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q07_SQL, {"start": start, "end": end})

# TODO Q08  GET /products/dead?state=
@app.get("/products/dead", dependencies=[Depends(require_api_key)])
def q08_dead_products(state: str, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q08_SQL, {"state": state})

# TODO Q09  GET /stats/revenue-by-state
@app.get("/stats/revenue-by-state", dependencies=[Depends(require_api_key)])
def q09_revenue_by_state(db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q09_SQL)

# TODO Q10  GET /products/top
@app.get("/products/top", dependencies=[Depends(require_api_key)])
def q10_top_products(limit: int = 10, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q010_SQL, {"limit": limit})

# Phase 3 -- each has a slow route and a /fast route ------------------------ #

# TODO Q11  GET /purchases/page?offset=        GET /purchases/page/fast?after_id=

@app.get("/purchases/page", dependencies=[Depends(require_api_key)])
def q11_purchases_page(offset: int = 0, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q011_SLOW_SQL, {"offset": offset})

@app.get("/purchases/page/fast", dependencies=[Depends(require_api_key)])
def q11_purchases_page_fast(after_id: int = 0, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q011_FAST_SQL, {"after_id": after_id})

# TODO Q12  GET /purchases/sample              GET /purchases/sample/fast
@app.get("/purchases/sample", dependencies=[Depends(require_api_key)])
def q12_purchases_sample(db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q012_SLOW_SQL)

@app.get("/purchases/sample/fast", dependencies=[Depends(require_api_key)])
def q12_sample_fast(db: sqlite3.Connection = Depends(get_exp_db)):
    max_id = db.execute("SELECT MAX(purchase_id) FROM purchases").fetchone()[0]
    ids = random.sample(range(1, max_id + 1), 10)
    params = {f"id{i}": v for i, v in enumerate(ids, start=1)}
    return run_query(db, Q012_FAST_SQL, params)


# TODO Q13  GET /stats/revenue-by-month        GET /stats/revenue-by-month/fast
@app.get("/stats/revenue-by-month", dependencies=[Depends(require_api_key)])
def q13_revenue_by_month(db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q013_SLOW_SQL)

@app.get("/stats/revenue-by-month/fast", dependencies=[Depends(require_api_key)])
def q13_revenue_by_month_fast(db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q013_FAST_SQL)

# TODO Q14  GET /reports/cube?start=&end=&min_purchases=
#                                              GET /reports/cube/fast?(same)
@app.get("/reports/cube", dependencies=[Depends(require_api_key)])
def q14_cube_report(start: str, end: str, min_purchases: int, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q014_SLOW_SQL, {"start": start, "end": end, "min_purchases": min_purchases})

@app.get("/reports/cube/fast", dependencies=[Depends(require_api_key)])
def q14_cube_report_fast(start: str, end: str, min_purchases: int, db: sqlite3.Connection = Depends(get_exp_db)):
    return run_query(db, Q014_FAST_SQL, {"start": start, "end": end, "min_purchases": min_purchases})


# Phase 4 ------------------------------------------------------------------- #

# TODO Q15  POST /purchases   (the full code is in QUERIES.md)
from .models import NewPurchase

@app.post("/purchases", status_code=201, dependencies=[Depends(require_api_key)])
def q15_create_purchase(body: NewPurchase, db: sqlite3.Connection = Depends(get_exp_db)):
    try:
        with db:  # BEGIN ... COMMIT, or ROLLBACK if anything raises
            row = db.execute(
                """
                INSERT INTO purchases
                    (customer_id, card_id, product_id, department, amount, purchase_date)
                VALUES (:customer_id, :card_id, :product_id, :department, :amount, :purchase_date)
                RETURNING purchase_id, customer_id, product_id, department, amount, purchase_date
                """,
                body.model_dump(mode="json"),
            ).fetchone()
    except sqlite3.OperationalError as exc:   # "database is locked"
        raise HTTPException(503, f"database error: {exc}") from exc
    return dict(row)

# --------------------------------------------------------------------------- #
# Dev entrypoint:  python -m app.main   (run from the starter folder)
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(
        "app.main:app",   # import string, so --reload can re-import on change
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8001")),
        reload=os.environ.get("RELOAD", "1") == "1",
    )