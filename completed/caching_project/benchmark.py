# benchmark.py  (required in some form: see README variations)
#
# Sends a controlled number of requests to one endpoint and records, per run:
#   average, min, max, and p95 latency; requests per second; hits and misses.
#
# Writes one CSV per lab part into results/. Control the request rate and
# duration (handout 5.2): a TTL alone doesn't determine the hit rate.


import argparse
import csv
import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import redis


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_URL = "http://localhost:8000"
OUTPUT_DIR = Path("results")

REDIS_HOST = "localhost"
REDIS_PORT = 6379

REDIS_CLIENT = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)


# --------------------------------------------------
# HTTP helpers
# --------------------------------------------------

def send_request(endpoint, method="GET"):
    """Send an HTTP request and return its latency and success status."""

    url = f"{BASE_URL}{endpoint}"

    request = urllib.request.Request(
        url,
        method=method
    )

    start = time.perf_counter()

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()

            latency = time.perf_counter() - start

            return latency, response.status < 400

    except urllib.error.HTTPError:
        latency = time.perf_counter() - start
        return latency, False

    except (urllib.error.URLError, TimeoutError, OSError):
        latency = time.perf_counter() - start
        return latency, False


def get_cache_stats():
    """Retrieve current cache statistics from FastAPI."""

    url = f"{BASE_URL}/cache/stats"

    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


# --------------------------------------------------
# Cache preparation
# --------------------------------------------------

def clear_redis_cache(key):
    """Remove a specific Redis cache entry."""
    REDIS_CLIENT.delete(key)


def clear_dictionary_cache():
    """Clear the application's Python dictionary cache."""
    send_request("/cache/dict", method="DELETE")


# --------------------------------------------------
# Benchmark helpers
# --------------------------------------------------

def percentile_95(values):
    """Calculate the 95th percentile using nearest-rank."""

    sorted_values = sorted(values)

    index = math.ceil(0.95 * len(sorted_values)) - 1

    return sorted_values[index]


def get_stat_difference(before, after, name):
    """Calculate the change in a cache statistic."""

    return after.get(name, 0) - before.get(name, 0)


def run_benchmark(
    test_name,
    endpoint,
    requests_count,
    target_rps,
    ttl=None,
    cache_type="none",
    redis_key=None,
    before_each=None
):
    """
    Run a controlled benchmark against one endpoint.

    Requests are spaced according to the target requests per second.
    """

    print(f"Running {test_name}...")

    # Start with an empty cache for normal cache tests.
    if redis_key:
        clear_redis_cache(redis_key)

    if cache_type == "dictionary":
        clear_dictionary_cache()

    # Record cache statistics before the test.
    stats_before = get_cache_stats()

    latencies = []
    errors = []

    start_time = time.perf_counter()

    for i in range(requests_count):

        # Maintain the requested request rate.
        scheduled_time = start_time + (i / target_rps)

        wait_time = scheduled_time - time.perf_counter()

        if wait_time > 0:
            time.sleep(wait_time)

        # Optionally clear the cache before every request.
        if before_each:
            before_each()

        latency, success = send_request(endpoint)

        latencies.append(latency)

        if not success:
            errors.append(latency)

    elapsed = time.perf_counter() - start_time

    # Record cache statistics after the test.
    stats_after = get_cache_stats()

    # Calculate cache statistics for this benchmark only.
    redis_hits = get_stat_difference(
        stats_before, stats_after, "redis_hits"
    )

    redis_misses = get_stat_difference(
        stats_before, stats_after, "redis_misses"
    )

    dict_hits = get_stat_difference(
        stats_before, stats_after, "dict_hits"
    )

    dict_misses = get_stat_difference(
        stats_before, stats_after, "dict_misses"
    )

    redis_errors = get_stat_difference(
        stats_before, stats_after, "redis_errors"
    )

    # Combine hits and misses from the applicable cache.
    if cache_type == "redis":
        hits = redis_hits
        misses = redis_misses

    elif cache_type == "dictionary":
        hits = dict_hits
        misses = dict_misses

    else:
        hits = 0
        misses = 0

    successful_requests = requests_count - len(errors)

    results = {
        "test": test_name,
        "endpoint": endpoint,
        "ttl_seconds": ttl if ttl is not None else "",
        "requests": requests_count,
        "target_requests_per_second": target_rps,
        "elapsed_seconds": round(elapsed, 4),
        "average_latency_ms": round(
            (sum(latencies) / len(latencies)) * 1000, 4
        ),
        "minimum_latency_ms": round(
            min(latencies) * 1000, 4
        ),
        "maximum_latency_ms": round(
            max(latencies) * 1000, 4
        ),
        "p95_latency_ms": round(
            percentile_95(latencies) * 1000, 4
        ),
        "actual_requests_per_second": round(
            successful_requests / elapsed, 4
        ),
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_errors": redis_errors,
        "http_errors": len(errors)
    }

    print(
        f"  Average: {results['average_latency_ms']} ms | "
        f"P95: {results['p95_latency_ms']} ms | "
        f"Hits: {hits} | Misses: {misses}"
    )

    return results


# --------------------------------------------------
# CSV output
# --------------------------------------------------

def write_csv(filename, results):
    """Write benchmark results to a CSV file."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not results:
        return

    filepath = OUTPUT_DIR / filename

    with open(filepath, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=results[0].keys()
        )

        writer.writeheader()
        writer.writerows(results)

    print(f"Saved: {filepath}")


# --------------------------------------------------
# Part A: Baseline
# --------------------------------------------------

def benchmark_part_a(count, rps):

    results = [
        run_benchmark(
            test_name="A - Database Baseline",
            endpoint="/leaderboard/no-cache",
            requests_count=count,
            target_rps=rps
        )
    ]

    write_csv("part_a_baseline.csv", results)


# --------------------------------------------------
# Part B: Redis cache
# --------------------------------------------------

def benchmark_part_b(count, rps):

    results = [
        run_benchmark(
            test_name="B - Redis Cache",
            endpoint="/leaderboard/cached?ttl=30",
            requests_count=count,
            target_rps=rps,
            ttl=30,
            cache_type="redis",
            redis_key="leaderboard:top10:ttl:30"
        )
    ]

    write_csv("part_b_redis.csv", results)


# --------------------------------------------------
# Part C: TTL comparison and frequent misses
# --------------------------------------------------

def benchmark_part_c(count, rps):

    results = []

    # Compare 5, 30, and 60 second TTLs.
    for ttl in (5, 30, 60):

        results.append(
            run_benchmark(
                test_name=f"C - Redis TTL {ttl}s",
                endpoint=f"/leaderboard/cached?ttl={ttl}",
                requests_count=count,
                target_rps=rps,
                ttl=ttl,
                cache_type="redis",
                redis_key=f"leaderboard:top10:ttl:{ttl}"
            )
        )

    # Test E: Force a cache miss before every request.
    results.append(
        run_benchmark(
            test_name="E - Redis Frequent Misses",
            endpoint="/leaderboard/cached?ttl=30",
            requests_count=count,
            target_rps=rps,
            ttl=30,
            cache_type="redis",
            redis_key="leaderboard:top10:ttl:30",
            before_each=lambda: clear_redis_cache(
                "leaderboard:top10:ttl:30"
            )
        )
    )

    write_csv("part_c_ttl.csv", results)


# --------------------------------------------------
# Part D: Dictionary vs Redis
# --------------------------------------------------

def benchmark_part_d(count, rps):

    results = []

    results.append(
        run_benchmark(
            test_name="D - Redis Cache",
            endpoint="/leaderboard/cached?ttl=30",
            requests_count=count,
            target_rps=rps,
            ttl=30,
            cache_type="redis",
            redis_key="leaderboard:top10:ttl:30"
        )
    )

    results.append(
        run_benchmark(
            test_name="D - Dictionary Cache",
            endpoint="/leaderboard/dict-cache?ttl=30",
            requests_count=count,
            target_rps=rps,
            ttl=30,
            cache_type="dictionary"
        )
    )

    write_csv("part_d_dict_vs_redis.csv", results)


# --------------------------------------------------
# Part E: Query complexity
# --------------------------------------------------

def benchmark_part_e(count, rps, purchase_id):

    results = []

    tests = [
        {
            "name": "E - Aggregation Without Cache",
            "endpoint": "/leaderboard/no-cache",
            "cache_type": "none"
        },
        {
            "name": "E - Aggregation With Redis",
            "endpoint": "/leaderboard/cached?ttl=30",
            "cache_type": "redis",
            "redis_key": "leaderboard:top10:ttl:30"
        },
        {
            "name": "E - Indexed Lookup Without Cache",
            "endpoint": f"/purchases/{purchase_id}/no-cache",
            "cache_type": "none"
        },
        {
            "name": "E - Indexed Lookup With Redis",
            "endpoint": f"/purchases/{purchase_id}/cached?ttl=30",
            "cache_type": "redis",
            "redis_key": f"purchase:{purchase_id}:ttl:30"
        }
    ]

    for test in tests:

        results.append(
            run_benchmark(
                test_name=test["name"],
                endpoint=test["endpoint"],
                requests_count=count,
                target_rps=rps,
                ttl=30 if test["cache_type"] == "redis" else None,
                cache_type=test["cache_type"],
                redis_key=test.get("redis_key")
            )
        )

    write_csv("part_e_query_complexity.csv", results)


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Benchmark the database caching endpoints."
    )

    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Number of requests per test (default: 100)"
    )

    parser.add_argument(
        "--rps",
        type=float,
        default=10,
        help="Target requests per second (default: 10)"
    )

    parser.add_argument(
        "--purchase-id",
        type=int,
        default=1,
        help="Purchase ID used for indexed lookup (default: 1)"
    )

    args = parser.parse_args()

    if args.requests < 1 or args.rps <= 0:
        parser.error("Requests and requests per second must be positive.")

    print("\nStarting database benchmarks")
    print(f"Requests per test: {args.requests}")
    print(f"Target request rate: {args.rps} requests/second")
    print(f"Purchase ID: {args.purchase_id}")
    print(f"Output directory: {OUTPUT_DIR}\n")

    benchmark_part_a(args.requests, args.rps)
    benchmark_part_b(args.requests, args.rps)
    benchmark_part_c(args.requests, args.rps)
    benchmark_part_d(args.requests, args.rps)
    benchmark_part_e(
        args.requests,
        args.rps,
        args.purchase_id
    )

    print("\nAll benchmarks completed.")


if __name__ == "__main__":
    main()
