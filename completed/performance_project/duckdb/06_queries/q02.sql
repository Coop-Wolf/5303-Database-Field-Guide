-- Q02 — One page of products
--
-- What it answers: "Show me the first page of the product catalog."
-- Route:           GET /products   (params: limit, offset; every route also takes db=)
-- Pattern:         keyset_pagination
-- Engine:          DuckDB
--
-- Think about it:
-- Compare this query's time with Q09's, which reads every purchase. If DuckDB
-- needs about as long to return 50 products as to total a million rows, where
-- is the time going?

SELECT product_id, product_name, unit_price
FROM products
ORDER BY product_id
LIMIT $limit OFFSET $offset;
