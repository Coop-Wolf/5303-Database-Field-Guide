-- Q08 — Products never bought in a state (anti-join)
--
-- What it answers: "Which products has nobody in Texas ever bought?"
-- Route:           GET /products/dead   (params: state; every route also takes db=)
-- Pattern:         anti_joins
-- Engine:          PostgreSQL
--
-- Think about it:
-- In SQLite, noidx_* ran this NOT EXISTS once per product and took over a
-- second at 1m. Find the join type in PostgreSQL's plan. How does it change
-- the noidx_* time, and does the index still matter?

SELECT pr.product_id, pr.product_name
FROM products pr
WHERE NOT EXISTS (
    SELECT 1
    FROM purchases pu
    JOIN customers c ON c.customer_id = pu.customer_id
    JOIN zipcodes  z ON z.zipcode     = c.zipcode
    WHERE pu.product_id = pr.product_id
      AND z.state_code  = %(state)s
)
ORDER BY pr.product_id
LIMIT 100;
