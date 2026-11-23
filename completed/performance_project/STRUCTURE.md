# Repository Structure & Conventions

```
5303-Database-Field-Guide/
├── README.md               course front door
├── STRUCTURE.md            this file
├── setup/                  install once: git, Python, Docker, QueryMux, editor
├── engines/                one folder per engine, nine fixed sections each
│   ├── 00_foundations/     vocabulary + first SQL (own layout)
│   ├── 01_sqlite/
│   ├── 02_duckdb/
│   ├── 03_postgres/
│   ├── 04_mongodb/
│   └── 05_redis/
├── tracks/                 cross-engine comparisons (same nine sections, one part per engine)
│   ├── spatial/
│   ├── vector/
│   └── distributed/
├── lab/                    measurement ladder, fairness, load scenarios, FINDINGS template
│   ├── api/                FastAPI basics, route contract, experiment.py, driver
│   │   └── starter_code/   the runnable measurement API
│   └── loadtest/           loadtest.py
├── datasets/               shared data: store (course-wide), people_products, armageddon (spatial)
├── reference/              look-it-up material, read in any order
│   ├── concept_map.md      same questions × every engine
│   ├── naming_conventions.md
│   ├── patterns/           engine-independent query techniques
│   └── topics/             one concept compared across engines (users, locking, ...)
└── assignments/
```

## The nine sections (every unit and track)

| Folder            | Fixed question                                   |
| ----------------- | ------------------------------------------------ |
| `01_why/`         | What was it built for, and what does it give up? |
| `02_install/`     | Can I run it and prove it's running?             |
| `03_connect/`     | Same "hello" from CLI, QueryMux, Python          |
| `04_model/`       | How does `store` want to look here?              |
| `05_load/`        | Get the data in, reproducibly                    |
| `06_queries/`     | Q01–Q15 in this engine's language                |
| `07_explain/`     | What did it do, and how long did it take?        |
| `08_concurrency/` | How does it behave under load?                   |
| `09_when/`        | When should you choose it?                       |

## Give them the work, keep the verdict

Students get the setup, the code, and the queries. Writing those isn't the
lesson (yet). What they hand in is always a **judgment**, using one of four
verbs:

| Verb        | The student…                                          | Example                                           |
| ----------- | ----------------------------------------------------- | ------------------------------------------------- |
| **Predict** | commits to an outcome *before* running anything       | "This check will return no rows."                 |
| **Explain** | says *why* a result happened, from the evidence       | Why `q07_fast.sql` beats `q07.sql`, from `EXPLAIN` |
| **Compare** | sets two queries, designs, or engines side by side    | Do these two queries return the same rows and plan? |
| **Choose**  | makes a call and cites their own number               | Yes or no on a §9 scenario                        |

Rules that follow from it:

- **Sections 02, 03, and 05 hand over commands.** Setup should be painless, so
  attention goes where the learning is.
- **Never print the verdict.** Give the query, but leave out its result and what
  it means: no "(181!)" comments, no filled-in verdict columns, no "why" comments
  that answer the section's question. Answer keys go in `.profzone/`, which is
  git-ignored.
- **Worked examples are the exception.** A walkthrough shows every answer so
  students learn the method, like 04_model Part A. It always comes before an
  exercise where students apply the method themselves and see no answers
  (Part B). Inside a walkthrough, ask for a prediction before showing the
  answer, and hide the answer in a `<details>` block.
- **Engine facts are not verdicts.** "SQLite doesn't enforce foreign keys
  unless you turn them on" is reference material. State it plainly.
- **Check each artifact:** if pasting could produce it, rewrite the artifact.
  Don't strip out the scaffolding.

## Naming conventions

Consistency over cleverness: when in doubt, copy the pattern below.

| Thing                                             | Convention                                                                 | Example                                                                |
| ------------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Folders and files                                 | lowercase, `_` between words, zero-padded numeric prefix                   | `04_mongodb/`, `05_load/`                                              |
| Engine slugs (folders, filenames, `engine` field) | `sqlite` · `duckdb` · `postgres` · `mongodb` · `redis`                     | `engines/03_postgres/`, `postgres.sql`                                   |
| Numbered sections and pages                       | always a folder with a `README.md`                                         | `07_explain/README.md`, `lab/api/02_route_contract/README.md`          |
| Unit / track / folder `README.md`                 | the index for that folder, not the lecture itself                          | `engines/01_sqlite/README.md`                                            |
| Query IDs                                         | `Q` + two digits, uppercase in prose                                       | Q07                                                                    |
| Query files in `06_queries/`                      | `qNN` + engine extension; `_fast` for the rewrite                          | `q07.sql`, `q11_fast.sql`, `q07.json` (Mongo command doc), `q07.redis` |
| Pattern folders                                   | the pattern name from the [query catalog](datasets/store/query_catalog.md) | `reference/patterns/anti_joins/`                                                 |
| Dataset sizes                                     | `classroom` · `10k` · `100k` · `1m`                                        | `idx_1m`                                                               |
| Database variants                                 | `idx` · `noidx` (+ `writes` scratch copy)                                  | `noidx_100k`                                                           |
| API routes                                        | see the [route contract](lab/api/02_route_contract/)                       | `/customers?customer_id=7`                                             |
| Tables, collections, keys                         | see [reference/naming_conventions.md](reference/naming_conventions.md)     | `purchases`, `customer:7`                                              |

Lowercase is deliberate: a case-only rename (`02_Sqlite` → `02_sqlite`) is
invisible on macOS but creates a *second* folder on Linux/GitHub.

## Where things go

| Kind of file                           | Location                               |
| -------------------------------------- | -------------------------------------- |
| Engine-specific prose and scripts      | `engines/<nn_engine>/`                 |
| Cross-engine comparisons               | `tracks/<topic>/`                      |
| One concept across engines, one page   | `reference/topics/<topic>.md`          |
| Data used by 2+ engines or tracks      | `datasets/`                            |
| A query technique, any engine          | `reference/patterns/<pattern>/`        |
| Generated databases (`.db`, `.duckdb`) | never committed — rebuild from loaders |
