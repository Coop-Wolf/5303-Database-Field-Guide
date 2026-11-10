# 14 – Redis caching, and the complete app

This is the finished application: choose a customer and card, search for a
product as you type, buy it, see the history, and register customers.
The one new idea is a **cache** in front of product searches.

> This lesson **writes to the database** (purchases, customers, and the
> developer price tool). Consider running it against a copy.

## Run it

Redis is optional. Without it, the app works and the indicator says
*Redis unavailable*. To see hits and misses, start Redis first:

```bash
brew install redis && brew services start redis     # macOS
# or: docker run -p 6379:6379 redis

cd lessons/14-redis-cache
python api.py
```

| Setting         | Default                    |
| --------------- | -------------------------- |
| `REDIS_URL`     | `redis://localhost:6379/0` |
| `CACHE_SECONDS` | `30`                       |

## Cache-aside

```text
GET /api/products?q=lamp…
        ↓
   check Redis for this exact search
        ├── HIT  → return the cached JSON            (MongoDB not touched)
        └── MISS → query MongoDB → store in Redis for 30 s → return
```

The application, not Redis, does all the work: it *asides* to the cache
before going to the database, and fills the cache after a miss.

```python
version = products_version()
key = f"products:v{version}:q={term.lower()}:min={min_price}:max={max_price}:sort={sort}:limit={limit}"

if version is not None:
    cached = cache_get(key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return json.loads(cached)

# … the lesson 13 MongoDB query, unchanged …

cache_set(key, json.dumps(results))
response.headers["X-Cache"] = "MISS"
return results
```

### The cache key

The key must contain **every parameter that changes the results**:

```text
products:v0:q=lamp:min=None:max=200:sort=price_asc:limit=25
```

Leave out `sort` and a price-ascending search would return a cached
price-descending answer. `term.lower()` is safe to include *because* the
regex ignores case: `LAMP` and `lamp` give identical results, so they share one
entry. If the search were case-sensitive, lowercasing the key would be a bug.

### JSON serialization

Redis stores strings. `json.dumps(results)` turns the list into JSON text on
the way in; `json.loads(cached)` turns it back on the way out. The `_out`
converters already made everything JSON-friendly (prices are strings).

### Expiration

```python
cache.set(key, value, ex=CACHE_SECONDS)
```

`ex=30`: Redis deletes the key by itself after 30 seconds. So a cached answer
can be **at most 30 seconds stale**, even if nothing else invalidates it.
Shorter = fresher but more misses; longer = faster but staler.

### When Redis is unavailable

```python
def cache_get(key):
    try:
        return cache.get(key)
    except redis.RedisError:
        return None
```

Every Redis call is wrapped, and a failure is treated as a miss. The
connection timeouts are 0.3 s, so a dead Redis costs almost nothing. The
cache is an **optimization**: losing it should make the app slower, never
broken. The header says `OFF` so you can tell.

### Invalidation

When a product changes, cached searches containing it are wrong until they
expire. Deleting "every key that might contain product 11" is hard, so this
app uses a **version number** in every key:

```python
def invalidate_product_searches():
    cache.incr("products:version")    # v0 → v1
```

After the bump, every new search builds a `v1` key, misses, and goes to
MongoDB. The old `v0` entries are never read again and expire on their own.

The **Developer** panel at the bottom of the page calls
`PATCH /api/products/{id}/price`, which updates MongoDB and bumps the version.

### What is *not* cached

`GET /api/products/{id}` (the details shown before buying) and the whole
purchase route always read MongoDB. A search result may be up to 30 seconds
old, but **the price you're charged never is**: `create_purchase` looks it up
fresh, as in lesson 10.

## Reading a response header in the browser

```js
const response = await fetch(url);
response.headers.get('X-Cache');   // "HIT", "MISS" or "OFF"
```

The cache status travels in a **header** instead of the JSON body, so the
response shape stays `[{id, name, price}, …]` and nothing else that calls
`/api/products` has to change. The page's `request()` helper returns both
`data` and `response` so the search can read it.

Other page details:

| Code                                                      | Meaning                                                                          |
| --------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `init()` in the `x-data` object                           | Alpine calls a method named `init` automatically; no `x-init` needed             |
| `:class="{ 'bg-green-100 …': cacheStatus === 'HIT', … }"` | Object form of `:class`: each class string is applied when its condition is true |
| `<details><summary>…</summary>…</details>`                | Built-in HTML collapsible section                                                |
| `max-h-64 overflow-auto`                                  | A scrolling results box at most 16rem tall                                       |
| `request(method, url, body)`                              | One fetch helper for GET, POST and PATCH                                         |

## Watch it in `redis-cli`

```bash
redis-cli KEYS 'products:*'
redis-cli TTL 'products:v0:q=lamp:min=None:max=None:sort=name:limit=25'   # seconds left
redis-cli GET products:version
redis-cli MONITOR      # every command the API sends, live (Ctrl+C to stop)
```

## Activity

1. Search `lamp`: **MISS**. Search it again: **HIT**. Wait 30 seconds and
   search again: **MISS**.
2. Stop Redis (`brew services stop redis`) and search. The page keeps working,
   and the indicator says *Redis unavailable*.
3. Add `X-Cache-Key` as a second header so the page can show which key was used.

## Checkpoint

Comment out the `invalidate_product_searches()` call in `change_price`. Search
for `premium`, change the price of *Premium Lamp 10* with the developer panel,
and search again. **Explain what the user sees and why.** Then explain how
expiration and invalidation each change that behavior, and why the purchase
total is still correct either way.