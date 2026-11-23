-- Q01 — One customer by id
--
-- What it answers: "Show me customer 42."
-- Route:           GET /customers   (params: customer_id; every route also takes db=)
-- Pattern:         plan basics (see 07_explain/)
-- Engine:          PostgreSQL
--
-- Think about it:
-- Compare the API's elapsed_ms with the "Execution Time" at the bottom of
-- the plan. Where does the rest of the time go, and why does SQLite never pay
-- it?

SELECT c.customer_id, c.first_name, c.last_name, c.email, c.zipcode, z.state_code
FROM customers c
JOIN zipcodes z ON z.zipcode = c.zipcode
WHERE c.customer_id = %(customer_id)s;
