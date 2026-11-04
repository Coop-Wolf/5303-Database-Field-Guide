# FINDINGS — Assignment 01

> Copy this to `starter_code/FINDINGS.md` and fill it in. Keep answers
> short: one to three sentences each, and every answer should point at a
> **number** from `results.md` or a **plan line** from `results.csv`.

## Environment

- SQLite version (`sqlite3 --version`): 3.45.1
- Python version (`python --version`): 3.11.9
- Machine (CPU, RAM, SSD or spinning disk): Intel Core i7-10750H, 32 GB, 1 TB
- Row counts (copy from the `make_dbs.py` output):

| Size | purchases | customers | products |
| :--- | --------: | --------: | -------: |
| 10k  |   10k     |    500    |    100   |
| 100k |    100k   |     5k    |    500   |
| 1m   |    1m     |      50k  |     5k   |

- Indexes in `idx_1m.db` (paste the output of `sqlite3 data/idx_1m.db ".indexes"`):

Had to run this instead:

`python`
`import sqlite3`
`c = sqlite3.connect("data/idx_1m.db")`
`c.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()`

```
[('sqlite_autoindex_states_1',), ('sqlite_autoindex_card_types_1',), ('sqlite_autoindex_departments_1',), ('sqlite_autoindex_zipcodes_1',), ('sqlite_autoindex_customers_1',), ('sqlite_autoindex_cards_1',), ('sqlite_autoindex_products_1',), ('idx_zipcodes_state',), ('idx_customers_zipcode',), ('idx_cards_customer',), ('idx_purchases_customer',), ('idx_purchases_product',), ('idx_purchases_department',), ('idx_purchases_date',), ('sqlite_autoindex_monthly_sales_1',), ('idx_purchases_cust_amount',), ('idx_purchases_prod_amount',), ('idx_purchases_date_cust_amount',)]
```

## Results

Paste your whole `results.md` here. All times are median milliseconds.

| Query | noidx_10k | idx_10k | noidx_100k | idx_100k | noidx_1m | idx_1m |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q01 | 0.06 | 0.08 | 0.09 | 0.08 | 0.08 | 0.06 |
| Q02 | 0.08 | 0.09 | 0.09 | 0.09 | 0.09 | 0.09 |
| Q03 | 1.13 | 0.69 | 10.72 | 0.76 | 110.89 | 0.86 |
| Q04 | 1.26 | 1.17 | 9.89 | 23.38 | 90.57 | 65.68 |
| Q05 | 0.96 | 0.06 | 9.63 | 0.32 | 91.23 | 2.66 |
| Q06 | 2.30 | 2.86 | 11.09 | 26.81 | 84.54 | 67.24 |
| Q07 | 1.73 | 0.82 | 16.21 | 7.82 | 165.74 | 84.78 |
| Q08 | 17.95 | 3.68 | 120.99 | 22.72 | 7333.83 | 109.23 |
| Q09 | 8.49 | 1.53 | 103.52 | 13.12 | 3213.31 | 403.47 |
| Q10 | 3.98 | 1.05 | 59.83 | 10.44 | 802.94 | 102.96 |
| Q11 | 0.47 | 0.50 | 4.54 | 4.83 | 43.02 | 46.50 |
| Q11-fast | 0.10 | 0.13 | 0.11 | 0.11 | 0.12 | 0.12 |
| Q12 | 1.40 | 1.21 | 12.38 | 12.46 | 122.75 | 126.17 |
| Q12-fast | 0.10 | 0.10 | 0.13 | 0.14 | 0.17 | 0.17 |
| Q13 | 4.22 | 2.88 | 55.98 | 40.29 | 663.18 | 507.75 |
| Q13-fast | 1.76 | 1.45 | 6.15 | 6.36 | 7.29 | 6.52 |
| Q14 | 6.55 | 6.38 | 72.31 | 225.96 | 1634.95 | 3943.05 |
| Q14-fast | 0.47 | 0.56 | 1.94 | 1.97 | 8.38 | 8.16 |

---

## Phase 1 — Simple reads (Q01–Q03)

| Query | Plan summary in `noidx_1m` | Plan summary in `idx_1m` |
| :---- | :------------------------- | :----------------------- |
| Q01   | SEARCH c USING INTEGER PRIMARY KEY (rowid=?) | SEARCH z USING INDEX sqlite_autoindex_zipcodes_1 (zipcode=?)   | SEARCH c USING INTEGER PRIMARY KEY (rowid=?) | SEARCH z USING INDEX sqlite_autoindex_zipcodes_1 (zipcode=?) |
| Q03   | SCAN purchases | USE TEMP B-TREE FOR ORDER BY | SEARCH purchases USING INDEX idx_purchases_date (purchase_date>? AND purchase_date<?) |

*A plan summary is the one or two `SCAN` / `SEARCH` lines that matter, e.g. `SCAN purchases + TEMP B-TREE FOR ORDER BY`.*

1. Why is Q01 fast even in `noidx_*`?
- Becuase we are given the id to look for
2. What does SQLite do differently for Q03 in the two databases?
- For the database that has no indexes, it has to create a temp B-TREE

## Phase 2 — Where indexes matter (Q04–Q10)

| Query | `noidx_1m` ms | `idx_1m` ms | Speedup (noidx ÷ idx) |
| :---- | ------------: | ----------: | --------------------: |
| Q04   | 90.57         | 65.68       | 1.38×                 |
| Q05   | 91.23         | 2.66        | 34.30×                |
| Q06   | 84.54         | 67.24       | 1.26×                 |
| Q07   | 165.74        | 84.78       | 1.95×                 |
| Q08   | 7333.83       | 109.23      | 67.14×                |
| Q09   | 3213.31       | 403.47      | 7.96×                 |
| Q10   | 802.94        | 102.96      | 7.80×                 |

1. Which query had the largest speedup? Quote its two plan summaries and explain the difference.
- Q05 had the largest speed up
- Plan summaries for Q05:
- - SCAN purchases
- - SEARCH purchases USING COVERING INDEX idx_purchases_department (department=?)
- The reason there is such a great difference in time is becuase with no indexes, its forced to look through every row in purchaces (1m rows), where as with indexes, its able to get the department index and get all purchases with that index ID.
2. Q09 reads every purchase in both databases. Which word in its `idx_1m` plan explains why it's still faster?
- SCAN pu | SEARCH c USING INTEGER PRIMARY KEY (rowid=?) | SEARCH z USING INDEX sqlite_autoindex_zipcodes_1 (zipcode=?) | USE TEMP B-TREE FOR GROUP BY | USE TEMP B-TREE FOR ORDER BY
- SCAN z USING INDEX idx_zipcodes_state | SEARCH c USING COVERING INDEX idx_customers_zipcode (zipcode=?) | SEARCH pu USING COVERING INDEX idx_purchases_cust_amount (customer_id=?) | USE TEMP B-TREE FOR ORDER BY
- Scan z. One query has to scan purchases (1m), while the other has to scan zipcodes (700). Also uses covering index
3. Why did Q07 only get about 2× faster?
- CO-ROUTINE (subquery-3) | CO-ROUTINE spend | SCAN purchases | USE TEMP B-TREE FOR GROUP BY | SCAN spend | USE TEMP B-TREE FOR ORDER BY | SCAN (subquery-3) | USE TEMP B-TREE FOR ORDER BY
- CO-ROUTINE (subquery-3) | CO-ROUTINE spend | SEARCH purchases USING COVERING INDEX idx_purchases_date_cust_amount (purchase_date>? AND purchase_date<?) | USE TEMP B-TREE FOR GROUP BY | SCAN spend | USE TEMP B-TREE FOR ORDER BY | SCAN (subquery-3) | USE TEMP B-TREE FOR ORDER BY
- The only difference between the PLANS is that the first query is scanning all of purchaces, while the second one is searching for a certain condition (Which could result in scanning all of it worst case)

## Phase 3 — When an index can't save you (Q11–Q14)

| Query | slow, `noidx_1m` | Time (ms) | slow, `idx_1m` | Time (ms) | `/fast`, `idx_1m` | Time (ms) |
| :--- | --- | ---: | --- | ---: | --- | ---: |
| Q11 offset → keyset | SCAN purchases | 43.02 | SCAN purchases | 46.50 | SEARCH purchases USING INTEGER PRIMARY KEY (rowid>?) | 0.12 |
| Q12 random sort → random ids | SCAN purchases | 122.75 | USE TEMP B-TREE FOR ORDER BY | 126.17 | SEARCH purchases USING INTEGER PRIMARY KEY (rowid=?) | 0.17 |
| Q13 revenue by month → summary | SCAN purchases<br>USE TEMP B-TREE FOR GROUP BY | 663.18 | SCAN purchases USING COVERING INDEX idx_purchases_date_cust_amount<br>USE TEMP B-TREE FOR GROUP BY | 507.75 | SCAN monthly_sales USING INDEX sqlite_autoindex_monthly_sales_1 | 6.52 |
| Q14 cube → summary | CO-ROUTINE cube<br>SCAN pu<br>SEARCH c USING INTEGER PRIMARY KEY (rowid=?)<br>SEARCH z USING INDEX sqlite_autoindex_zipcodes_1 (zipcode=?)<br>USE TEMP B-TREE FOR GROUP BY<br>SCAN cube<br>USE TEMP B-TREE FOR ORDER BY | 1634.95 | CO-ROUTINE cube<br>SEARCH pu USING INDEX idx_purchases_date (purchase_date>? AND purchase_date<?)<br>SEARCH c USING INTEGER PRIMARY KEY (rowid=?)<br>SEARCH z USING INDEX sqlite_autoindex_zipcodes_1 (zipcode=?)<br>USE TEMP B-TREE FOR GROUP BY<br>SCAN cube<br>USE TEMP B-TREE FOR ORDER BY | 3943.05 | SEARCH monthly_sales USING INDEX sqlite_autoindex_monthly_sales_1 (month>? AND month<?)<br>USE TEMP B-TREE FOR ORDER BY | 8.16 |

For each, write one or two sentences: **why the slow version is slow** (point at the plan) and **what the rewrite gives up**.

- **Q11:** It's slow becuase it's scanning all purchases.
- **Q12:** Again, this one is slow because its scanning all purchases.
- **Q13:** Again, this one is slow because its scanning all purchases.
- **Q14:** (also: why is the slow version slower in `idx_1m` than in `noidx_1m`?) Because its having to look through all of purchases. noidx is faster than idx, becuase a large percentage of the rows match the data range, so its having to do a lot of repeated lookups.

- **Faster Versions**
- - Q11 - Only has to search for a single index, not scan.
- - Q12 - Only has to search for a single index, not scan.
- - Q13 - Only has to search on a single index.
- - Q14 - Doesn't have to do cube calculation. Uses already-computed summary table. 

## Phase 4 — Write concurrency (Q15)

| Run | busy_timeout | workers | n | succeeded (201) | failed (503) | seconds | writes/sec |
| :--- | -----------: | ------: | --: | --------------: | -----------: | ------: | ---------: |
| A | 0 | 1 | 200 | 32 | 168 | 2.66 | 12.03 |
| A | 0 | 1 | 500 | 88 | 412 | 14.12 | 6.23 |
| B | 5000 | 1 | 200 | 200 | 0 | 3.95 | 50.63 |
| B | 5000 | 1 | 500 | 500 | 0 | 15.35 | 32.57 |
| C | 0 | 4 | 200 | 39 | 161 | 2.76 | 14.13 |
| C | 0 | 4 | 500 | 104 | 396 | 14.81 | 7.02 |
| D | 5000 | 4 | 200 | 200 | 0 | 5.27 | 37.95 |
| D | 5000 | 4 | 500 | 500 | 0 | 16.25 | 30.77 |


POST http://127.0.0.1:8001/purchases?db=writes  x200  in 2.66s
  201: 32
  503: 168
  --- 503 ---
  {"detail":"database error: database is locked"}

POST http://127.0.0.1:8001/purchases?db=writes  x500  in 14.12s
  201: 88
  503: 412
  --- 503 ---
  {"detail":"database error: database is locked"}

POST http://127.0.0.1:8001/purchases?db=writes  x200  in 3.95s
  201: 200

POST http://127.0.0.1:8001/purchases?db=writes  x500  in 15.35s
  201: 500

POST http://127.0.0.1:8001/purchases?db=writes  x200  in 2.76s
  201: 39
  503: 161
  --- 503 ---
  {"detail":"database error: database is locked"}

POST http://127.0.0.1:8001/purchases?db=writes  x500  in 14.81s
  201: 104
  503: 396
  --- 503 ---
  {"detail":"database error: database is locked"}

POST http://127.0.0.1:8001/purchases?db=writes  x200  in 5.27s
  201: 200

POST http://127.0.0.1:8001/purchases?db=writes  x500  in 16.25s
  201: 500


Exact error text from a failed request:

```
POST http://127.0.0.1:8001/purchases?db=writes  x500  in 14.81s
  201: 104
  503: 396
  --- 503 ---
  {"detail":"database error: database is locked"}
```

Summary-table check (`COUNT(*) FROM purchases` vs. `SUM(num_purchases) FROM monthly_sales`):

```
Purchases: 101663
Monthly sales total: 100000
```

1. What does `busy_timeout` do, and why did B succeed where A failed?
 - Tells SQLite how long to wait when the database is locked before returning a "database is locked" error.

2. Did 4 worker processes make SQLite write faster? Why or why not?
- No. Four workers did not make SQLite write faster because it still allows only one writer at a time

3. Why don't the two summary-check numbers match? What does that cost the `/fast` routes from Phase 3?
- The numbers don't match because the successful writes were added to purchases, but the monthly_sales summary table was not updated for those new purchases. This makes /fast routes faster, but potentially stale. 

## Phase 5 — Conclusions

For each scenario: **SQLite yes or no**, 1–2 sentences, and one number from your results.

1. Internal read-only dashboard, ~10 analysts: yes, its good for a small read-only dashboard because it can efficiently handle concurrent reads without requering a database server. Q13
2. Mobile app offline local storage: yes, its well suited for mobile apps becuase its lightweight, embedded, and works without network connection. Q05
3. Thousands of events per second from many servers: no, its not a good fit for heavy concurrent writes from many servers because it uses a file-based locking and is designed more for local workloads. Q08
4. Fresh throwaway database per automated test: yes, its a strong fit because databases can be created quickly as local files or in memeory, making test setup simple. Q01