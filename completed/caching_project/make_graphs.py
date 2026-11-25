# make_graphs.py  (recommended)
#
# Reads the CSVs in results/ (written by benchmark.py) and writes comparison
# graphs to graphs/. Missing CSVs are skipped with a warning, so you can run
# this after any subset of the lab parts.
#
# Usage:
#   python make_graphs.py
#   python make_graphs.py --results results --graphs graphs

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display needed; write straight to files
import matplotlib.pyplot as plt


# --------------------------------------------------
# Configuration
# --------------------------------------------------

RESULTS_DIR = Path("results")
GRAPHS_DIR = Path("graphs")

COLORS = {
    "avg": "#4C72B0",
    "p95": "#DD8452",
    "hit": "#55A868",
    "miss": "#C44E52",
}

NUMERIC_FIELDS = {
    "ttl_seconds",
    "requests",
    "target_requests_per_second",
    "elapsed_seconds",
    "average_latency_ms",
    "minimum_latency_ms",
    "maximum_latency_ms",
    "p95_latency_ms",
    "actual_requests_per_second",
    "cache_hits",
    "cache_misses",
    "cache_errors",
    "http_errors",
}


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def read_csv(filename):
    """Read one results CSV into a list of dicts with numeric fields parsed."""

    path = RESULTS_DIR / filename

    if not path.exists():
        print(f"Skipping {filename}: not found in {RESULTS_DIR}/")
        return []

    rows = []

    with open(path, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            for field in NUMERIC_FIELDS:
                value = row.get(field, "")
                row[field] = float(value) if value not in ("", None) else None
            rows.append(row)

    if not rows:
        print(f"Skipping {filename}: file is empty")

    return rows


def hit_rate(row):
    """Return the cache hit rate as a percentage, or None if no cache used."""

    hits = row["cache_hits"] or 0
    misses = row["cache_misses"] or 0
    total = hits + misses

    if total == 0:
        return None

    return 100 * hits / total


def label_bars(ax, bars, fmt="{:.1f}"):
    """Write each bar's value above it."""

    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            fmt.format(height),
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def latency_bar_chart(rows, labels, title, filename, log_scale=False):
    """Grouped bar chart of average and p95 latency for a list of rows."""

    if not rows:
        return

    positions = range(len(rows))
    width = 0.38

    fig, ax = plt.subplots(figsize=(max(7, 1.8 * len(rows) + 3), 5))

    avg_bars = ax.bar(
        [p - width / 2 for p in positions],
        [r["average_latency_ms"] for r in rows],
        width,
        label="Average",
        color=COLORS["avg"],
    )
    p95_bars = ax.bar(
        [p + width / 2 for p in positions],
        [r["p95_latency_ms"] for r in rows],
        width,
        label="p95",
        color=COLORS["p95"],
    )

    label_bars(ax, avg_bars)
    label_bars(ax, p95_bars)

    ax.set_xticks(list(positions))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(title)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    if log_scale:
        ax.set_yscale("log")
        ax.set_ylabel("Latency (ms, log scale)")

    save(fig, filename)


def save(fig, filename):
    """Save a figure into the graphs folder and close it."""

    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

    path = GRAPHS_DIR / filename

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

    print(f"Saved: {path}")


# --------------------------------------------------
# Graphs
# --------------------------------------------------

def graph_baseline_vs_redis():
    """Part A vs Part B: database baseline against Redis cache."""

    rows = read_csv("part_a_baseline.csv") + read_csv("part_b_redis.csv")

    latency_bar_chart(
        rows,
        labels=["Database (no cache)" if i == 0 else "Redis (TTL 30s)"
                for i in range(len(rows))] if len(rows) == 2
        else [r["test"] for r in rows],
        title="Baseline vs Redis Cache: Latency",
        filename="a_vs_b_baseline_vs_redis.png",
    )


def graph_ttl():
    """Part C: effect of TTL on latency and hit rate, plus forced misses."""

    rows = read_csv("part_c_ttl.csv")

    if not rows:
        return

    ttl_rows = [r for r in rows if r["test"].startswith("C -")]
    miss_rows = [r for r in rows if "Frequent Misses" in r["test"]]

    ttl_rows.sort(key=lambda r: r["ttl_seconds"] or 0)

    # Latency by TTL
    latency_bar_chart(
        ttl_rows,
        labels=[f"TTL {int(r['ttl_seconds'])}s" for r in ttl_rows],
        title="Redis TTL Comparison: Latency",
        filename="c_ttl_latency.png",
    )

    # Hit rate by TTL, with the frequent-misses run alongside for contrast
    shown = ttl_rows + miss_rows

    if not shown:
        return

    labels = [f"TTL {int(r['ttl_seconds'])}s" for r in ttl_rows]
    labels += ["Forced misses" for _ in miss_rows]

    hits = [r["cache_hits"] or 0 for r in shown]
    misses = [r["cache_misses"] or 0 for r in shown]

    fig, ax = plt.subplots(figsize=(max(7, 1.6 * len(shown) + 3), 5))

    hit_bars = ax.bar(labels, hits, label="Hits", color=COLORS["hit"])
    miss_bars = ax.bar(
        labels, misses, bottom=hits, label="Misses", color=COLORS["miss"]
    )

    for i, row in enumerate(shown):
        rate = hit_rate(row)
        if rate is not None:
            ax.annotate(
                f"{rate:.0f}% hit",
                xy=(i, hits[i] + misses[i]),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )

    ax.set_ylabel("Requests")
    ax.set_title("Cache Hits and Misses by TTL")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    save(fig, "c_ttl_hit_miss.png")


def graph_dict_vs_redis():
    """Part D: Python dictionary cache against Redis."""

    rows = read_csv("part_d_dict_vs_redis.csv")

    latency_bar_chart(
        rows,
        labels=[r["test"].replace("D - ", "") for r in rows],
        title="Dictionary Cache vs Redis: Latency",
        filename="d_dict_vs_redis.png",
    )


def graph_query_complexity():
    """Part E: caching benefit for an aggregation vs an indexed lookup."""

    rows = read_csv("part_e_query_complexity.csv")

    if not rows:
        return

    # Log scale: indexed lookups are far faster than the aggregation.
    latency_bar_chart(
        rows,
        labels=[r["test"].replace("E - ", "") for r in rows],
        title="Query Complexity: Latency With and Without Cache",
        filename="e_query_complexity.png",
        log_scale=True,
    )


def graph_summary():
    """One overview chart: average latency of every test across all parts."""

    files = [
        "part_a_baseline.csv",
        "part_b_redis.csv",
        "part_c_ttl.csv",
        "part_d_dict_vs_redis.csv",
        "part_e_query_complexity.csv",
    ]

    rows = []
    for name in files:
        rows.extend(read_csv(name))

    if not rows:
        return

    fig, ax = plt.subplots(figsize=(10, max(4, 0.45 * len(rows) + 1.5)))

    labels = [r["test"] for r in rows][::-1]
    values = [r["average_latency_ms"] for r in rows][::-1]

    bars = ax.barh(labels, values, color=COLORS["avg"])

    for bar in bars:
        ax.annotate(
            f"{bar.get_width():.1f}",
            xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
            xytext=(3, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
        )

    ax.set_xlabel("Average latency (ms, log scale)")
    ax.set_xscale("log")
    ax.set_title("Average Latency Across All Benchmarks")
    ax.grid(axis="x", alpha=0.3)

    save(fig, "summary_average_latency.png")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    global RESULTS_DIR, GRAPHS_DIR

    parser = argparse.ArgumentParser(
        description="Create graphs from the benchmark CSV files."
    )
    parser.add_argument("--results", default="results",
                        help="Folder with the CSV files (default: results)")
    parser.add_argument("--graphs", default="graphs",
                        help="Folder to write graphs to (default: graphs)")
    args = parser.parse_args()

    RESULTS_DIR = Path(args.results)
    GRAPHS_DIR = Path(args.graphs)

    print(f"\nReading CSVs from {RESULTS_DIR}/")
    print(f"Writing graphs to {GRAPHS_DIR}/\n")

    graph_baseline_vs_redis()
    graph_ttl()
    graph_dict_vs_redis()
    graph_query_complexity()
    graph_summary()

    print("\nDone.")


if __name__ == "__main__":
    main()