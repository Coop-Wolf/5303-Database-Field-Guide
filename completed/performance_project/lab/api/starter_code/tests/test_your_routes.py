"""
Tests for the three routes you write: Q03, Q08, Q15.

These fail until your routes exist. When all of them pass, you're done:

    pytest tests/test_your_routes.py -v

The `client` fixture (a small temp database) is in conftest.py.
"""

from __future__ import annotations

DB = {"db": "idx_10k"}


# Q03  GET /purchases?start=&end=

def test_q03_date_range(client):
    r = client.get("/purchases", params={"start": "2025-03-01", "end": "2025-03-08"} | DB)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query_id"] == "Q03"
    assert body["row_count"] > 0
    assert all("2025-03-01" <= row["purchase_date"] < "2025-03-08" for row in body["rows"])


def test_q03_requires_both_dates(client):
    assert client.get("/purchases", params={"start": "2025-03-01"} | DB).status_code == 422


def test_q03_rejects_a_non_date(client):
    r = client.get("/purchases", params={"start": "March 1", "end": "2025-03-08"} | DB)
    assert r.status_code == 422


# Q08  GET /products/dead?state=

def test_q08_dead_products(client):
    r = client.get("/products/dead", params={"state": "TX"} | DB)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query_id"] == "Q08"
    assert body["row_count"] > 0


def test_q08_rejects_a_bad_state(client):
    assert client.get("/products/dead", params={"state": "Texas"} | DB).status_code == 422


# Q15  POST /purchases  (JSON body)

NEW = {"customer_id": 1, "card_id": 1, "product_id": 1, "department": "Games",
       "amount": 9.99, "purchase_date": "2026-01-15"}


def test_q15_insert_returns_201_and_the_row(client):
    r = client.post("/purchases", params=DB, json=NEW)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["query_id"] == "Q15"
    assert body["row_count"] == 1
    row = body["rows"][0]
    assert row["customer_id"] == 1 and row["purchase_date"] == "2026-01-15"


def test_q15_rejects_a_bad_body(client):
    bad = NEW | {"amount": "lots"}
    assert client.post("/purchases", params=DB, json=bad).status_code == 422
