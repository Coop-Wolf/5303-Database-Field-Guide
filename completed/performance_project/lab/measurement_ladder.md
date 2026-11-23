# Measurement Ladder

Four rungs, climbed in order, in every unit. Each rung answers a question the
one below it can't. Skip a rung, and the next one gives you numbers you
can't explain.

| Rung        | Question                                  | Tool                                                    | Unit section      |
| ----------- | ----------------------------------------- | ------------------------------------------------------- | ----------------- |
| 1. **Look** | Is the data what I think it is?           | the engine's CLI, row counts, a few sample rows         | 03, 05            |
| 2. **Ask**  | What does the engine *plan* to do?        | `EXPLAIN` (or that engine's equivalent)                 | 07 §1–2           |
| 3. **Time** | How long does it take, one query at a time? | [driver.py](api/04_driver/README.md): median of N runs | 07 §3             |
| 4. **Stress** | What breaks when many requests arrive at once? | [loadtest.py](loadtest/README.md)                  | 08                |

## 1. Look

Before measuring anything, confirm what you're measuring.

- Row counts match what the loader printed.
- A few sample rows look right: dates are dates, zips kept their zeros.
- The indexes you think exist actually exist.

A query that's "fast" on an empty table, or on the wrong database, teaches
you nothing.

## 2. Ask

The plan is the engine telling you **how** it will find the rows: which
table it scans, which index it seeks, whether it sorts. It's free, because
asking doesn't run the query.

The plan explains the time. A number without a plan is a guess. The
[result envelope](api/02_route_contract/README.md) returns both, so you
never have one without the other.

## 3. Time

- **Median of several runs**, not one run. The first call is often slower
  (cold cache), and an occasional run is slow for reasons unrelated to the
  query.
- **Two or more sizes.** One number says little. How the time *grows* from
  100k to 1m tells you what the engine is doing:

  | 100k → 1m (10× the rows) | Usually means                                   |
  | ------------------------ | ----------------------------------------------- |
  | about the same           | the cost follows the result, not the table: a seek |
  | about 10×                | the cost follows the table: a scan              |
  | more than 10×            | a sort, or a nested loop, is involved           |

- **Two variants** (`idx` and `noidx`) show what an index is worth, and
  sometimes what it costs.

## 4. Stress

One query at a time hides contention. Real applications send many requests
at once, and that's where engines differ most: who waits, who fails, and
with what message. [load_scenarios.md](load_scenarios.md) defines what to
send.

Stress testing reports different things than timing does: success rate,
throughput, p95 latency, and **the exact error text**.

## Climbing it

Every claim in your FINDINGS should rest on a rung: "Q08 is slow" (time)
"because it scans `purchases` for every product" (plan) "and it grows 20×
from 100k to 1m" (time at two sizes). A claim with no rung under it is an
opinion.
