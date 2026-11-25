# main.py  (required: "application source code")
#
# The FastAPI app (handout section 4.3), grown to cover every lab part:
#
#   Part A  an endpoint with no cache
#   Part B  a Redis cache-aside endpoint that reports whether each response
#           came from redis or the database
#   Part C  a way to change the TTL (5, 30, 60 s) without editing code,
#           e.g. a query parameter or an environment variable
#   Part D  a Python dictionary cache WITH expiration comparable to Redis
#   Part E  a simple indexed lookup and the expensive aggregation, each with
#           and without caching, and the time.sleep() delay removed
#
# You also need some way to count hits and misses: counters in the app, an
# endpoint that reports them, or the "source" field tallied by benchmark.py.


import json
import os
import sqlite3
import time
from threading import Lock

import redis
from fastapi import FastAPI, HTTPException, Query

app = FastAPI()

# Database configuration
DB_PATH = os.getenv("DB_PATH", "shop.db")

# Redis configuration
cache = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=0.5,
    socket_timeout=0.5
)

# Cache statistics
stats = {
    "redis_hits": 0,
    "redis_misses": 0,
    "redis_errors": 0,
    "dict_hits": 0,
    "dict_misses": 0
}

stats_lock = Lock()


def update_stat(name):
    """Safely update a cache statistic."""
    with stats_lock:
        stats[name] += 1


def validate_ttl(ttl):
    """Only allow TTL values of 5, 30, or 60 seconds."""
    if ttl not in (5, 30, 60):
        raise HTTPException(
            status_code=400,
            detail="TTL must be 5, 30, or 60 seconds"
        )


# --------------------------------------------------
# Database queries
# --------------------------------------------------

def expensive_query():
    """Return the top 10 customers by total purchase amount."""
    with sqlite3.connect(DB_PATH) as db:
        return [
            list(row)
            for row in db.execute("""
                SELECT customer_id, SUM(amount)
                FROM purchases
                GROUP BY customer_id
                ORDER BY SUM(amount) DESC
                LIMIT 10
            """).fetchall()
        ]



def indexed_lookup(purchase_id):
    """Retrieve one purchase using its primary key."""
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row

        result = db.execute("""
            SELECT purchase_id, customer_id, amount
            FROM purchases
            WHERE purchase_id = ?
        """, (purchase_id,)).fetchone()

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Purchase {purchase_id} not found"
            )

        return dict(result)



# --------------------------------------------------
# Redis cache
# --------------------------------------------------

def redis_cached(key, query_function, ttl):
    """Retrieve data from Redis or query the database on a cache miss."""

    try:
        result = cache.get(key)

        if result is not None:
            update_stat("redis_hits")
            return {
                "source": "redis",
                "data": json.loads(result)
            }

        update_stat("redis_misses")

    except redis.RedisError:
        update_stat("redis_errors")

    # Cache miss or Redis unavailable: query the database.
    result = query_function()

    try:
        cache.setex(key, ttl, json.dumps(result))
    except redis.RedisError:
        update_stat("redis_errors")

    return {
        "source": "database",
        "data": result
    }


# --------------------------------------------------
# Python dictionary cache
# --------------------------------------------------

memory_cache = {}
memory_lock = Lock()


def dict_cached(key, query_function, ttl):
    """Retrieve data from an in-memory dictionary with expiration."""

    with memory_lock:
        entry = memory_cache.get(key)

        if entry is not None:
            expires_at, result = entry

            if time.monotonic() < expires_at:
                update_stat("dict_hits")
                return {
                    "source": "memory",
                    "data": result
                }

            # Remove expired entry.
            del memory_cache[key]

        update_stat("dict_misses")

    # Cache miss: query the database.
    result = query_function()

    with memory_lock:
        memory_cache[key] = (
            time.monotonic() + ttl,
            result
        )

    return {
        "source": "database",
        "data": result
    }


# --------------------------------------------------
# Cache statistics
# --------------------------------------------------

@app.get("/cache/stats")
def cache_stats():
    """Return cache hit, miss, and error counts."""
    with stats_lock:
        return stats.copy()


# --------------------------------------------------
# Part A: Database queries without caching
# --------------------------------------------------

@app.get("/leaderboard/no-cache")
def leaderboard_no_cache():
    return {
        "source": "database",
        "data": expensive_query()
    }


@app.get("/purchases/{purchase_id}/no-cache")
def purchase_no_cache(purchase_id: int):
    return {
        "source": "database",
        "data": indexed_lookup(purchase_id)
    }


# --------------------------------------------------
# Part B and C: Redis cache with configurable TTL
# --------------------------------------------------

@app.get("/leaderboard/cached")
def leaderboard_cached(ttl: int = Query(default=30)):
    validate_ttl(ttl)

    return redis_cached(
        f"leaderboard:top10:ttl:{ttl}",
        expensive_query,
        ttl
    )


@app.get("/purchases/{purchase_id}/cached")
def purchase_cached(
    purchase_id: int,
    ttl: int = Query(default=30)
):
    validate_ttl(ttl)

    return redis_cached(
        f"purchase:{purchase_id}:ttl:{ttl}",
        lambda: indexed_lookup(purchase_id),
        ttl
    )


# --------------------------------------------------
# Part D: Python dictionary cache with expiration
# --------------------------------------------------

@app.get("/leaderboard/dict-cache")
def leaderboard_dict_cache(ttl: int = Query(default=30)):
    validate_ttl(ttl)

    return dict_cached(
        f"leaderboard:top10:ttl:{ttl}",
        expensive_query,
        ttl
    )


@app.get("/purchases/{purchase_id}/dict-cache")
def purchase_dict_cache(
    purchase_id: int,
    ttl: int = Query(default=30)
):
    validate_ttl(ttl)

    return dict_cached(
        f"purchase:{purchase_id}:ttl:{ttl}",
        lambda: indexed_lookup(purchase_id),
        ttl
    )


@app.delete("/cache/dict")
def clear_dict_cache():
    """Clear all entries from the Python dictionary cache."""
    with memory_lock:
        memory_cache.clear()

    return {
        "message": "Dictionary cache cleared"
    }