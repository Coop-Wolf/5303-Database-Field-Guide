# Fairness: Rules for Honest Comparisons

Comparing databases is easy to do badly. Each rule below exists because
breaking it produces a number that looks meaningful and isn't.

## Same work

1. **Same rows.** Every engine loads the same generated data, from the same
   seed, at the same sizes.
2. **Same question.** A query ported to another engine must return the same
   rows. Check `row_count`, and spot-check the rows. A "faster" query that
   answers a different question isn't faster.
3. **Same definition of done.** `elapsed_ms` stops when **every row is in
   Python**, in every engine (see the
   [route contract](api/02_route_contract/README.md#what-elapsed_ms-measures)).

## Same conditions

4. **Same machine, same session.** Compare numbers you measured yourself,
   back to back. Not your laptop against a classmate's, and not today
   against last week.
5. **Quiet machine.** Plugged in, not on battery saver, with nothing heavy
   running: no video calls, no builds, no 40 browser tabs.
6. **Warm cache, stated.** The driver's median-of-5 measures warm
   performance. That's fair as long as every engine gets the same treatment
   and your FINDINGS say "warm."
7. **Connections set up once** for server engines (Postgres, MongoDB, Redis).
   A pool opened at startup means you time the query, not the handshake.

## Say what isn't equal

Some differences can't be removed. Name them instead of hiding them.

8. **Docker.** On macOS and Windows, server engines run inside a Linux VM,
   while SQLite and DuckDB run directly on your machine. That adds overhead
   to the servers. Note it.
9. **Durability settings.** SQLite with `synchronous = NORMAL` and Postgres
   with `synchronous_commit = on` promise different things after a crash.
   Faster writes often mean weaker promises. Report the settings.
10. **Indexes.** Each engine gets the indexes it naturally needs for the
    catalog, and you list them. "Postgres was faster" means nothing if
    Postgres had an index SQLite didn't.

## Under load

11. **Latency in a load test includes waiting in line.** With hundreds of
    requests at once, most of a request's time can be spent queued in the
    API server before the database sees it. Compare load-test latencies
    between runs of the *same* setup, and use the driver's `elapsed_ms` for
    the database's own time.
12. **Never load-test the experiment databases.** Write into a scratch copy
    (`writes`), so later timings run against the same rows as earlier ones.

## Report enough to reproduce

13. Engine version, Python version, machine (CPU, RAM, disk), dataset sizes,
    and the exact commands. The
    [FINDINGS template](findings_template.md) has a place for each.
