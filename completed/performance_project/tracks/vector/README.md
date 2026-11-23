# Vector Track (proposed)

Similarity search over embeddings across engines. Needs a text table to embed (e.g. `reviews`).

**Engines compared:** pgvector, Redis (query engine), DuckDB (vss), SQLite (sqlite-vec), MongoDB ($vectorSearch)

Every track in the field guide has the same nine sections, in the same order.
If a section doesn't apply, it stays and says why — that *is* the content.

| # | Section | Fixed question |
| - | ------- | -------------- |
| 01 | [Why it exists](01_why/) | What problem was this built for, and what does it give up? |
| 02 | [Install & verify](02_install/) | Can I run it and prove it's running? |
| 03 | [Connect three ways](03_connect/) | The same "hello" query from the CLI, QueryMux, and Python. |
| 04 | [Model the data](04_model/) | How does this track's data *want* to look in each engine? |
| 05 | [Load it](05_load/) | Get this track's data into each engine, reproducibly. |
| 06 | [Run the query catalog](06_queries/) | Run the track's queries in each engine — or say why one can't. |
| 07 | [Explain & measure](07_explain/) | What does the engine say it did, and how long did it take? |
| 08 | [Concurrency & load](08_concurrency/) | How does it behave under the load scenarios that apply to it? |
| 09 | [When to choose it](09_when/) | Yes or no on the standard scenarios — citing your own numbers. |

_Status: stub — content to be added._
