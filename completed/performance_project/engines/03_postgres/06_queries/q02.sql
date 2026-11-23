-- Q02 — One page of products
--
-- What it answers: "Show me the first page of the product catalog."
-- Route:           GET /products   (params: limit, offset; every route also takes db=)
-- Pattern:         keyset_pagination
-- Engine:          PostgreSQL
--
-- Think about it:
-- The plan reads 50 rows from products_pkey and stops. Compare elapsed_ms
-- with SQLite's for this query. For a query this small, what dominates the
-- time?

SELECT product_id, product_name, unit_price
FROM products
ORDER BY product_id
LIMIT %(limit)s OFFSET %(offset)s;
