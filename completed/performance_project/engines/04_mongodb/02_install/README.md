# 02 — Install & verify: MongoDB

> **Fixed question:** Can I run it and prove it's running?
>
> **Student artifact:** Output of the verify commands below

MongoDB is a **server**, like PostgreSQL: the server runs in Docker, and
client tools on your machine talk to it. If Docker is new to you, read
[setup/docker.md](../../../setup/docker.md) first.

## 1. The server, in Docker

[compose.yml](compose.yml) describes it: the `mongo:9` image, port 27017, a
volume for your data, and one setting that matters:

> **It runs as a one-member *replica set*.** A replica set is a group of
> MongoDB servers that keep copies of the same data. Ours has one member,
> which sounds pointless, but MongoDB only allows multi-document
> transactions on a replica set, and §8 uses them. The health check sets it
> up the first time the container starts.

```bash
cd engines/04_mongodb/02_install
docker compose up -d          # the first run downloads the image (~300 MB)
docker compose ps             # wait for STATUS to say "healthy" (about 15 s)
```

> **This server has no password.** It only listens on your own machine, and
> leaving authentication off keeps a one-member replica set simple. A real
> deployment turns it on; [§4](../04_model/) and the concept answers explain
> MongoDB's users and roles.

Every connection in this unit uses:

```
mongodb://localhost:27017/?directConnection=true
```

`directConnection=true` tells the driver to talk to this server and not go
looking for other replica-set members. Leave it on.

## 2. The client tools

| Tool | Install | Used for |
| ---- | ------- | -------- |
| `mongosh`, MongoDB's shell | macOS: `brew install mongosh` · Windows / Linux: [download](https://www.mongodb.com/try/download/shell) | §3 onward |
| `pymongo`, the Python driver | `pip install pymongo` in your venv | build scripts, the API |
| MongoDB Compass (optional) | [download](https://www.mongodb.com/try/download/compass) | browsing documents and plans in a GUI |

The [measurement API](../../../lab/api/starter_code/README.md) installs
`pymongo` for you. Don't want to install `mongosh`? It's inside the
container: `docker compose exec mongodb mongosh`.

## 3. Verify

```bash
docker compose ps
mongosh "mongodb://localhost:27017/?directConnection=true" --eval "db.version() + ' ' + rs.status().members[0].stateStr"
python3 -c "from pymongo import MongoClient; print(MongoClient('mongodb://localhost:27017/?directConnection=true').admin.command('ping'))"
```

All three should answer: a healthy container, `9.x.x PRIMARY`, and
`{'ok': 1.0}`. If the second one says `SECONDARY` or errors, wait ten seconds
for the health check to finish setting up the replica set.

## 4. Then build the experiment databases

The same rows as the other engines, built from the SQLite files. From the
repo root:

```bash
python3 datasets/store/generator/make_dbs.py             # if you haven't already
python3 engines/04_mongodb/05_load/build_mongo.py        # ~45 s for 10k, 100k, 1m
```

[§5](../05_load/) explains what it builds.
