# 01 — FastAPI Basics

Just enough FastAPI to read and write query routes. This isn't a
web-development unit.

## Why an API at all

Real applications rarely talk to a database from a terminal. A web or mobile
app calls an **API**, and the API runs the query. Putting each database behind
the same API gives us two things:

- **A realistic setting.** You measure queries the way an application would
  run them.
- **A fair comparison.** The [driver](../04_driver/README.md) calls the same
  routes no matter which engine answers, so the only thing that changes
  between engines is the engine.

## One route, start to finish

```python
@app.get("/customers")                                  # 1. method + path
def q01_customer(customer_id: int,                      # 2. query-string parameter
                 db: ExpDB = Depends(get_exp_db)):      # 3. a database connection
    return run_query(db, "Q01", {"customer_id": customer_id})   # 4. run, return JSON
```

1. **The decorator** says which HTTP method and path this function answers:
   `GET /customers`. Use `@app.post(...)` for a write.
2. **The function's parameters are the request's parameters.** A request to
   `/customers?customer_id=7` calls `q01_customer(customer_id=7)`.
3. **`Depends(...)`** asks FastAPI to call another function first and pass in
   what it returns. Here, `get_exp_db` reads `?db=`, opens that database, and
   closes it after the response is sent.
4. **Whatever you return becomes the JSON response.**

Run it with `python -m app.main`, then open <http://127.0.0.1:8001/docs>.
FastAPI builds that page from your code: every route, its parameters, and a
**Try it out** button.

## Types are validation

The type hint isn't decoration. FastAPI uses it to check the request
**before your code runs**:

| Request                         | What happens                                          |
| ------------------------------- | ----------------------------------------------------- |
| `/customers?customer_id=7`      | `customer_id` arrives as the integer `7`              |
| `/customers?customer_id=seven`  | **422**, with a message saying it isn't an integer    |
| `/customers`                    | **422**: a parameter without a default is required    |

A parameter with a default is optional:

```python
def q02_products(limit: int = 50, offset: int = 0, ...):
```

`Query(...)` adds rules beyond the type:

```python
offset: int = Query(0, ge=0)                 # default 0, must be >= 0
db: str = Query("idx_100k", pattern=r"...")  # must match a regular expression
```

`datetime.date` works too. `?start=2025-03-01` arrives as a `date`, and
`?start=March 1` gets a 422.

## Query parameters vs. a JSON body

A `GET` sends its values in the query string. A `POST` that creates something
sends a **JSON body** instead. In FastAPI, a parameter whose type is a
Pydantic model is read from the body:

```python
class NewPurchase(BaseModel):          # app/models.py
    customer_id: int
    amount: float
    purchase_date: date
    ...

@app.post("/purchases", status_code=201)
def q15_insert_purchase(purchase: NewPurchase, ...):
```

The model validates the body the same way type hints validate query
parameters: a missing field or `"amount": "lots"` gets a 422.

> **Path parameters** (`/customers/{customer_id}`) are the other common
> style. This course doesn't use them; the
> [route contract](../02_route_contract/README.md) puts every value in the
> query string, so every engine's routes look the same.

## Status codes we use

| Code    | Meaning here                                                                  |
| ------- | ----------------------------------------------------------------------------- |
| **200** | It worked; here are the rows (maybe zero of them)                             |
| **201** | It worked, and something was created (Q15)                                   |
| **404** | The database file named in `?db=` hasn't been built                          |
| **422** | The request is wrong: a missing parameter, a bad type, or a broken rule       |
| **503** | The database refused, e.g. `database is locked`. The message is the engine's own. |

## Sync routes

Our routes are plain `def`, not `async def`. FastAPI runs a plain `def` route
in a thread pool, so a slow query doesn't freeze the server. The `sqlite3`
module isn't async anyway; an `async def` route that calls it would block
every other request while it waits.

## Exercise

Write the three routes marked `TODO` in
[starter_code/app/main.py](../starter_code/app/main.py): Q03, Q08, and Q15.
Each one uses something from this page that the others don't. They're done
when `pytest tests/test_your_routes.py` passes.
