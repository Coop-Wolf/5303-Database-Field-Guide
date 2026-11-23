"""
Smoke tests: prove the wiring works. These pass before you write a line.
The `client` fixture (a small temp database) is in conftest.py.
"""

from __future__ import annotations

import pytest

DB = {"db": "idx_10k"}


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_q01_envelope(client):
    r = client.get("/customers", params={"customer_id": 1} | DB)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"engine", "dataset", "size", "variant", "query_id",
                         "elapsed_ms", "row_count", "plan", "rows"}
    assert (body["engine"], body["size"], body["variant"], body["query_id"]) == \
           ("sqlite", "10k", "idx", "Q01")
    assert body["row_count"] == 1
    assert body["rows"][0]["customer_id"] == 1
    assert any("PRIMARY KEY" in line for line in body["plan"])


def test_q01_missing_customer_is_empty(client):
    r = client.get("/customers", params={"customer_id": 999999} | DB)
    assert r.status_code == 200
    assert r.json()["row_count"] == 0


def test_bad_parameter_is_422(client):
    assert client.get("/customers", params={"customer_id": "seven"} | DB).status_code == 422


def test_unknown_db_name_rejected(client):
    assert client.get("/customers", params={"customer_id": 1, "db": "store"}).status_code == 422


def test_db_file_not_built(client):
    # valid name, but make_dbs.py hasn't built it in the temp folder
    r = client.get("/customers", params={"customer_id": 1, "db": "noidx_1m"})
    assert r.status_code == 404


@pytest.mark.parametrize("path, params", [
    ("/products", {}),
    ("/customers/purchases", {"customer_id": 1}),
    ("/stats/department_count", {"department": "Games"}),
    ("/customers/streaks", {"customer_id": 1}),
    ("/stats/leaderboard", {"start": "2026-06-02", "end": "2026-09-01"}),
    ("/stats/revenue_by_state", {}),
    ("/products/top", {}),
    ("/purchases/page", {"offset": 100}),
    ("/purchases/page/fast", {"after_id": 100}),
    ("/purchases/sample", {}),
    ("/purchases/sample/fast", {}),
    ("/stats/revenue_by_month", {}),
    ("/stats/revenue_by_month/fast", {}),
    ("/reports/cube", {"start": "2025-01-01", "end": "2026-01-01", "min_purchases": 2}),
    ("/reports/cube/fast", {"start": "2025-01-01", "end": "2026-01-01", "min_purchases": 2}),
])
def test_given_routes_answer(client, path, params):
    r = client.get(path, params=params | DB)
    assert r.status_code == 200, r.text
    if path != "/customers/streaks":  # a customer may have no streaks
        assert r.json()["row_count"] > 0


@pytest.mark.parametrize("slow, fast, params", [
    ("/purchases/page", "/purchases/page/fast", ({"offset": 100}, {"after_id": 100})),
    ("/stats/revenue_by_month", "/stats/revenue_by_month/fast", ({}, {})),
    ("/reports/cube", "/reports/cube/fast",
     ({"start": "2025-01-01", "end": "2026-01-01", "min_purchases": 2},) * 2),
])
def test_fast_twin_returns_same_rows(client, slow, fast, params):
    a = client.get(slow, params=params[0] | DB).json()["rows"]
    b = client.get(fast, params=params[1] | DB).json()["rows"]
    assert a == b


def test_q15_fast_writes_a_batch_in_one_request(client):
    one = {"customer_id": 1, "card_id": 1, "product_id": 1, "department": "Games",
           "amount": 9.99, "purchase_date": "2026-01-15"}
    r = client.post("/purchases/fast", params=DB, json=[one] * 5)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["query_id"] == "Q15-fast" and body["row_count"] == 5
    ids = [row["purchase_id"] for row in body["rows"]]
    assert len(set(ids)) == 5
