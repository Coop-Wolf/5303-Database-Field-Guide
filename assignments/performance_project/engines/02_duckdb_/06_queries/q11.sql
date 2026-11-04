-- Q11 — Deep pagination: `OFFSET` vs. keyset
--
-- What it answers: "Show me page 18,001 of all purchases (50 per page)."
-- Route:           GET /purchases/page   (params: offset; every route also takes db=)
-- Pattern:         keyset_pagination
-- Engine:          DuckDB
--
-- Think about it:
-- OFFSET still produces and throws away every skipped row. Is the gap
-- between this and the fast version bigger or smaller than it was in SQLite?
-- Explain it from the two plans. Remember Q02.

SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
ORDER BY purchase_id
LIMIT 50 OFFSET $offset;
