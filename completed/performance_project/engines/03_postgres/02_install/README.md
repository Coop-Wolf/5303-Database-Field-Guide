# 02 — Install & verify: PostgreSQL

> **Fixed question:** Can I run it and prove it's running?
>
> **Student artifact:** Output of the verify commands below

PostgreSQL is a **server**, so there are two halves: the server itself
(in Docker), and the client tools your machine uses to talk to it.
If Docker is new to you, read [setup/docker.md](../../../setup/docker.md) first.

## 1. The server, in Docker

[compose.yml](compose.yml) in this folder describes everything: the
`postgres:18` image, the login `student` / `student`, a database named
`course`, port 5432, and a volume so your data survives restarts.

```bash
cd engines/03_postgres/02_install
docker compose up -d          # the first run downloads the image (~150 MB)
docker compose ps             # wait for STATUS to say "healthy"
```

> **Port 5432 already in use?** Another PostgreSQL is running on your
> machine (Postgres.app, Homebrew, a classmate's container). Stop it, or
> change the left side of `ports:` to `"5433:5432"` and use port 5433 in
> every connection string in this unit.

## 2. The client tools

| Tool | Install | Used for |
| ---- | ------- | -------- |
| `psql`, PostgreSQL's shell | macOS: `brew install libpq` then `brew link --force libpq` · Windows: the [EDB installer](https://www.postgresql.org/download/windows/), "Command Line Tools" only · Linux: `postgresql-client` | §3 and every section after |
| `psycopg`, the Python driver | `pip install "psycopg[binary]" psycopg-pool` in your venv | build scripts, the API |

The [measurement API](../../../lab/api/starter_code/README.md) installs
`psycopg` for you as a dependency. Don't want to install `psql`? Every
command in this unit also works inside the container:
`docker compose exec postgres psql -U student course`.

## 3. Verify

```bash
docker compose ps
psql postgresql://student:student@localhost:5432/course -c "SELECT version();"
python3 -c "import psycopg; print(psycopg.connect('postgresql://student:student@localhost:5432/course').execute('SELECT 42').fetchone())"
```

All three should answer: a healthy container, a version string starting
`PostgreSQL 18`, and `(42,)`.

## 4. Then build the experiment schemas

Like DuckDB's, PostgreSQL's experiment data is built **from the SQLite
files**, so all three engines hold the same rows. From the repo root:

```bash
python3 datasets/store/generator/make_dbs.py               # if you haven't already
python3 engines/03_postgres/05_load/build_postgres.py      # ~40 s for 10k, 100k, 1m
```

[§5](../05_load/) explains what it builds and where.

## Stopping and starting

```bash
docker compose stop           # pause the server; data kept
docker compose start          # resume
docker compose down -v        # delete the container AND the data: a clean slate
```
