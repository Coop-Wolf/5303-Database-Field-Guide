-- Q11 — Deep pagination: `OFFSET` vs. keyset
--
-- What it answers: "Show me page 18,001 of all purchases (50 per page)."
-- Route:           GET /purchases/page   (params: offset; every route also takes db=)
-- Pattern:         keyset_pagination
-- Engine:          PostgreSQL
--
-- Think about it:
-- OFFSET 900000 is slower here than in SQLite, even though both walk the
-- primary key. Look at the Index Scan's row count and Buffers. What does
-- PostgreSQL do for each row it skips that SQLite doesn't?

SELECT purchase_id, customer_id, product_id, amount, purchase_date
FROM purchases
ORDER BY purchase_id
LIMIT 50 OFFSET %(offset)s;
