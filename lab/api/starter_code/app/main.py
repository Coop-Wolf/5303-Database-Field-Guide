"""
The measurement API: the store query catalog behind FastAPI, on SQLite
(or DuckDB / PostgreSQL / MongoDB: ENGINE=duckdb, postgres, or mongodb; see each engine's 07_explain/).

Run it from lab/api/starter_code/, either way:
    python -m app.main                   # uses the __main__ block below (port 8001)
    uvicorn app.main:app --port 8001     # equivalent

Then open http://127.0.0.1:8001/docs

(Don't run `python app/main.py`. The package-relative imports need the `app.`
package context, which only `-m app.main` and uvicorn provide.)

Each route is one row of the query catalog (datasets/store/query_catalog.md):
the decorator holds the method and path, the function's parameters are the
query-string parameters, and the SQL lives in engines/01_sqlite/06_queries/
(engines/02_duckdb/06_queries/ with ENGINE=duckdb, engines/03_postgres/06_queries/ with ENGINE=postgres,
engines/04_mongodb/06_queries/*.json with ENGINE=mongodb).
Every route also takes ?db=<name>, e.g. ?db=noidx_1m.

Three routes are yours to write: Q03, Q08, and Q15 (search for TODO). Most
of what you need appears in the routes already here; each TODO points to the
rest. You're done when

    pytest tests/test_your_routes.py

passes.
"""

from __future__ import annotations

import os
import random
from datetime import date
import typing
from fastapi import Depends, FastAPI, Query
from fastapi.responses import RedirectResponse

from .models import NewPurchase  # noqa: F401  -- you need this for Q15

# ENGINE picks the harness: the routes below don't change (see 03_experiment_py/).
ENGINE = os.environ.get("ENGINE", "sqlite")
if ENGINE == "duckdb":
    from .experiment_duckdb import ExpDB, get_exp_db, run_query, run_write, run_write_many  # noqa: F401
elif ENGINE == "postgres":
    from .experiment_postgres import ExpDB, get_exp_db, run_query, run_write, run_write_many  # noqa: F401
elif ENGINE == "mongodb":
    from .experiment_mongo import ExpDB, get_exp_db, run_query, run_write, run_write_many  # noqa: F401
else:
    from .experiment import ExpDB, get_exp_db, run_query, run_write, run_write_many  # noqa: F401  -- run_write: Q15

app = FastAPI(title=f"Store measurement API ({ENGINE})")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Bare host -> the Swagger UI."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Routes, in catalog order.
#
# FastAPI matches top to bottom. Keep fixed paths like /purchases/page and
# /purchases/sample above anything that could also match them.
# --------------------------------------------------------------------------- #

@app.get("/customers")
def q01_customer(customer_id: int, db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q01", {"customer_id": customer_id})


@app.get("/products")
def q02_products(limit: int = 50, offset: int = 0, db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q02", {"limit": limit, "offset": offset})


# TODO Q03 -- Purchases in a date range
#   Catalog row:  GET  /purchases   parameters: start, end
#   SQL:          06_queries/q03.sql  (uses :start and :end)
#   A request with a missing or non-date value should get a 422 and never
#   reach the database.
@app.get("/purchases")
def q03_purchases(start: date, end: date, db: ExpDB = Depends(get_exp_db),):
    return run_query(db, "Q03", {"start": start, "end": end})


@app.get("/customers/purchases")
def q04_customer_purchases(customer_id: int, db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q04", {"customer_id": customer_id})


@app.get("/stats/department_count")
def q05_department_count(department: str, db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q05", {"department": department})


@app.get("/customers/streaks")
def q06_streaks(customer_id: int, db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q06", {"customer_id": customer_id})


@app.get("/stats/leaderboard")
def q07_leaderboard(start: date, end: date, db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q07", {"start": start, "end": end})


# TODO Q08 -- Products never bought in a state
#   Catalog row:  GET  /products/dead   parameters: state
#   SQL:          06_queries/q08.sql  (uses :state)
#   state is a two-letter code like TX. Anything else ("Texas", "tx")
#   should get a 422. Query() can check a pattern: see how get_exp_db in
#   experiment.py validates ?db=.
@app.get("/products/dead")
def q08_products_dead(state: str = Query(pattern=r"^[A-Z]{2}$"),db: ExpDB = Depends(get_exp_db),):
    return run_query(db, "Q08", {"state": state})

@app.get("/stats/revenue_by_state")
def q09_revenue_by_state(db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q09")


@app.get("/products/top")
def q10_top_products(db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q10")


@app.get("/purchases/page")
def q11_page(offset: int = Query(0, ge=0), db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q11", {"offset": offset})


@app.get("/purchases/page/fast")
def q11_page_fast(after_id: int = Query(0, ge=0), db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q11-fast", {"after_id": after_id})


@app.get("/purchases/sample")
def q12_sample(db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q12")


@app.get("/purchases/sample/fast")
def q12_sample_fast(db: ExpDB = Depends(get_exp_db)):
    # Pick 10 ids in Python, then fetch exactly those rows. Ids run 1..max with
    # no gaps here, because the generator never deletes.
    max_id = db.con.execute("SELECT MAX(purchase_id) FROM purchases").fetchone()[0] or 0
    ids = random.sample(range(1, max_id + 1), k=min(10, max_id))
    ids += [0] * (10 - len(ids))  # pad so all 10 placeholders are bound
    return run_query(db, "Q12-fast", {f"id{i}": v for i, v in enumerate(ids, start=1)})


@app.get("/stats/revenue_by_month")
def q13_revenue_by_month(db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q13")


@app.get("/stats/revenue_by_month/fast")
def q13_revenue_by_month_fast(db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q13-fast")


@app.get("/reports/cube")
def q14_cube(start: date, end: date, min_purchases: int = Query(10, ge=1),
             db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q14", {"start": start, "end": end, "min_purchases": min_purchases})


@app.get("/reports/cube/fast")
def q14_cube_fast(start: date, end: date, min_purchases: int = Query(10, ge=1),
                  db: ExpDB = Depends(get_exp_db)):
    return run_query(db, "Q14-fast", {"start": start, "end": end, "min_purchases": min_purchases})


# TODO Q15 -- Insert a purchase
#   Catalog row:  POST /purchases   parameters: JSON body (see models.py)
#   SQL:          06_queries/q15.sql  -- it writes, so run it with run_write()
#   Success answers 201, not 200. A body that doesn't fit the model should
#   get a 422. A parameter typed as a Pydantic model is read from the JSON
#   body instead of the query string.
@app.post("/purchases", status_code=201)
def q15_insert_purchase(purchase: NewPurchase,db: ExpDB = Depends(get_exp_db),):
    return run_write(db, "Q15", purchase.model_dump())

@app.post("/purchases/fast", status_code=201)
def q15_insert_purchases_fast(purchases: list[NewPurchase], db: ExpDB = Depends(get_exp_db)):
    # Many purchases, one transaction, one commit. Compare with Q15 in 08_concurrency.
    return run_write_many(db, "Q15-fast", [p.model_dump() for p in purchases])


# --------------------------------------------------------------------------- #
# Dev entrypoint:  python -m app.main   (run from lab/api/starter_code/)
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",   # import string, so --reload can re-import on change
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8001")),
        reload=os.environ.get("RELOAD", "1") == "1",
    )
