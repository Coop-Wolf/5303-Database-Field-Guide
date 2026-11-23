# Docker

SQLite and DuckDB are libraries inside your program. PostgreSQL, MongoDB, and
Redis are **servers**: programs that run in the background and listen on a
network port. Docker runs each server in a **container**, an isolated box
with the server already installed, so you don't install three databases
directly on your machine.

You don't need Docker until [03_postgres](../engines/03_postgres/README.md).

## 1. Install

| OS      | Install                                                                                                        |
| ------- | -------------------------------------------------------------------------------------------------------------- |
| macOS   | [Docker Desktop](https://www.docker.com/products/docker-desktop/). Pick **Apple Silicon** or **Intel** to match your Mac. |
| Windows | [Docker Desktop](https://www.docker.com/products/docker-desktop/), with the **WSL 2** option. Restart when it asks. |
| Linux   | Docker Engine from your distribution, plus the Compose plugin                                                  |

Docker Desktop is free for education. Start it once from your applications
and leave it running whenever you're using a server engine.

## 2. The vocabulary

| Term          | Meaning                                                                         |
| ------------- | ------------------------------------------------------------------------------- |
| **Image**     | A packaged server, ready to run: `postgres:18`, `mongo:9`, `redis:7`           |
| **Container** | One running copy of an image                                                    |
| **Port**      | `5432:5432` connects your machine's port (left) to the container's (right)      |
| **Volume**    | Storage that outlives the container, so stopping it doesn't erase your data    |
| **Compose**   | A `compose.yml` file that describes a container, so one command starts it      |

## 3. One `compose.yml` per engine

Each server unit's `02_install/` has a `compose.yml`. Every one of them works
the same way, from that folder:

```bash
docker compose up -d       # start (the first run downloads the image)
docker compose ps          # is it running? is it healthy?
docker compose logs -f     # watch its output (Ctrl+C to stop watching)
docker compose down        # stop; data is kept in the volume
docker compose down -v     # stop AND delete the data: a fresh start
```

| Engine   | Image                     | Port  | Unit                                          |
| -------- | ------------------------- | ----- | --------------------------------------------- |
| Postgres | `postgres:18`             | 5432  | [03_postgres](../engines/03_postgres/README.md) |
| MongoDB  | `mongo:9`                 | 27017 | [04_mongodb](../engines/04_mongodb/README.md)   |
| Redis    | `redis`                   | 6379  | [05_redis](../engines/05_redis/README.md)       |

The [spatial track](../tracks/spatial/) needs PostGIS, which comes in its own
image, `postgis/postgis:18-3.6`. That image is built for Intel only, so on an
Apple Silicon Mac it runs under emulation: it works, but it's slower, so don't
time engine experiments in it.

## 4. When things go wrong

| Symptom                                           | Likely cause and fix                                                                    |
| ------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `Cannot connect to the Docker daemon`             | Docker Desktop isn't running. Start it and wait for it to say "running."               |
| `port is already allocated` / `address already in use` | Something else uses that port, often a database installed directly. Stop it, or change the **left** number in `ports:` (e.g. `"5433:5432"`) and connect to 5433. |
| A platform warning on Apple Silicon               | The image is built for Intel; Docker runs it under emulation. It works, a bit slower.  |
| The container keeps restarting                    | `docker compose logs` shows why. Usually a bad setting, or a full disk.                 |
| Disk filling up                                   | `docker system df` shows usage; `docker system prune` removes stopped containers and unused images. |

> **Docker adds overhead.** On macOS and Windows, containers run inside a
> small Linux virtual machine. When you compare a server engine with SQLite
> or DuckDB, say so in your FINDINGS (see [fairness rule 8](../lab/fairness.md)).

## Check

```bash
docker --version
docker compose version
docker run --rm hello-world       # prints "Hello from Docker!"
```
