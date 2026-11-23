-- Q08 — Products never bought in a state (anti-join)
--
-- What it answers: "Which products has nobody in Texas ever bought?"
-- Route:           GET /products/dead   (params: state; every route also takes db=)
-- Pattern:         anti_joins
-- Engine:          DuckDB
--
-- Think about it:
-- In SQLite, noidx_* ran the NOT EXISTS once per product, and the time grew
-- fast. Read DuckDB's plan for the join under products: is it a per-product
-- loop, or something else? Look at the join type. How does that change the
-- way the time grows from 100k to 1m?

SELECT pr.product_id, pr.product_name
FROM products pr
WHERE NOT EXISTS (
    SELECT 1
    FROM purchases pu
    JOIN customers c ON c.customer_id = pu.customer_id
    JOIN zipcodes  z ON z.zipcode     = c.zipcode
    WHERE pu.product_id = pr.product_id
      AND z.state_code  = $state
)
ORDER BY pr.product_id
LIMIT 100;
