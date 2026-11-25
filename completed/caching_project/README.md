# Redis Caching

## Environment

Windows, Python 3.11.9, Redis 8.1.0, Docker 29.0.1


## Caching Strategies Implemented

### No cache
The /leaderboard/no-cache endpoint runs the top-10 aggregation (GROUP BY customer_id with SUM(amount)) against the SQLite database on every request and returns the result with "source": "database". Nothing is stored between requests, so the data is always fresh, but each request pays the full cost of the query. This is the baseline for the other two strategies. Part E also has a no-cache indexed lookup by primary key, /purchases/{id}/no-cache.

### Redis cache-aside
The /leaderboard/cached endpoint uses the cache-aside pattern. The app checks Redis for a key that includes the TTL (for example leaderboard:top10:ttl:30). On a hit, it returns the stored JSON with "source": "redis". On a miss, it queries the database, stores the result with SETEX so it expires after the TTL, and returns it with "source": "database". The TTL is set with a ttl query parameter and restricted to 5, 30 or 60 seconds. Hits, misses and Redis errors are counted and exposed at /cache/stats. If Redis is unavailable, the app falls back to querying the database instead of failing.

### Dictionary cache with expiration
The /leaderboard/dict-cache endpoint stores results in a Python dictionary inside the app process. Each entry holds an expiry time (time.monotonic() + ttl) along with the data. A request returns the entry if it hasn't expired. Otherwise the app deletes the stale entry, queries the database, and stores a fresh one. A lock protects the dictionary from concurrent access, and expired entries are only removed when they are next requested. It follows the same TTL rules and hit/miss counting as the Redis version, so the two are comparable. It avoids a network call, but the cache belongs to a single process and is lost on restart.


## Was it beneficial?

Using Redis was beneficial under certain conditions. It worked well when the queries were expensive and the TTL was 30 or 60 seconds. It was near meaningless when the queries was simple.


## How to Run

### 1. Go to the project folder

```bash
cd caching_project
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Make sure Redis is running on `localhost:6379`, since the app and benchmark both connect to it.

### 3. Set up the database

```bash
python setup_db.py
```

### 4. Start the app

```bash
uvicorn main:app --port 8000
```

Leave this running in its own terminal.

### 5. Run the benchmark

In a second terminal:

```bash
python benchmark.py
```

Results are saved as CSV files in `results/`.

### 6. Generate the graphs

```bash
python make_graphs.py
```

Graphs are saved as PNG files in `graphs/`.



## Discussion Questions

1. Why might Redis improve the performance of an expensive aggregation but not an indexed database lookup?

Because caching really only matters when it stores data that can easily be retrievable compared to constantly running expensive queries.

2. Does caching become beneficial only after a system reaches a certain number of users? Explain.

Benefit depends less on user count than on how expensive the query is and how often the same data is requested.

3. Why might a Python dictionary outperform Redis in a single-process application?

A dictionary avoids a network hop and serialization

4. What advantages does Redis offer when an application uses multiple workers or servers?

A python dictionary lives inside one process, so each worker has its own copy. Redis is shared, so every worker sees the same cache.

5. What happens when the database changes but the cached result has not expired?

Users keep getting old values until the TTL expires.

6. How does TTL influence the tradeoff between performance and data freshness?

A TTL of 5 seconds ensures less chance of stale data, but increases the likelyhood of a cache miss, while a TTL of 60 seconds generates a lot of cache hits while also increases the likelyhood of stale data.

7. What is a cache stampede, and how might it be prevented?

A cache stampede is when a popular key expires, many requests mess at once and all hit the database together. Common fixes are a lock so only one request rebuilds the value.

8. Can caching reduce database load without significantly improving user-visible latency?

Yes, even when latency barely changes. The cache_hits and cache_misses columns show the load reduction, and the latency columns show whether users would notice.

9. Why should benchmarks include p95 latency rather than only average latency?

An average can hide a slow tail, such as the occasional cache miss. The graphs showing the complexity shows this.

10. Under what circumstances would adding Redis be an unnecessary complication?

It would be unnecessary when queries are cheap, and the data must always be fresh.


## Results

| Strategy          | Avg. Latency | p95 Latency | Requests/sec | Hit Rate |
| ----------------- | ------------ | ----------- | ------------ | -------- |
| No cache          |  2278.948    | 2306.815    |  0.4388      |   N/A    |
| Python dictionary |  2076.2967   | 264.7877    |  0.4816      |   93%    |
| Redis, 5s TTL     |  2135.1083   | 2294.6718   |  0.4683      |   66%    |
| Redis, 30s TTL    |  2071.1981   | 2266.8327   |  0.4828      |   93%    |
| Redis, 60s TTL    |  2065.3569   | 2085.8376   |  0.4842      |   96%    |