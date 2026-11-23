# 00 — Foundations

Vocabulary and first SQL — what every engine unit assumes. Not an engine unit,
so it does not use the nine-section layout.

| File                           | What it is                                                                |
| ------------------------------ | ------------------------------------------------------------------------- |
| [glossary.md](glossary.md)     | Data-modeling terms with relational, document, and key-value counterparts |
| [sql_basics.md](sql_basics.md) | First hands-on SQL walkthrough                                            |
| [joins.md](joins.md)           | Join types, visually                                                      |

[sql_basics.md](sql_basics.md) is the walkthrough; [glossary.md](glossary.md)
is for looking things up, not reading start to finish.

## Data

[data/students.sql](data/students.sql) creates a `students` table with 1,000
rows for the `sql_basics.md` examples. From this folder:

```bash
sqlite3 week01.db ".read data/students.sql"
```
