"""Benchmark profiling helpers."""

from __future__ import annotations

import math
from statistics import median


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    sorted_vals = sorted(values)
    rank = (len(sorted_vals) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(sorted_vals[low])
    weight = rank - low
    return float(sorted_vals[low] * (1.0 - weight) + sorted_vals[high] * weight)


def summarize_latency(latencies_sec: list[float]) -> dict[str, float]:
    if not latencies_sec:
        return {"p50_sec": 0.0, "p95_sec": 0.0, "mean_sec": 0.0}
    mean_sec = sum(latencies_sec) / len(latencies_sec)
    return {
        "p50_sec": round(percentile(latencies_sec, 50), 6),
        "p95_sec": round(percentile(latencies_sec, 95), 6),
        "mean_sec": round(mean_sec, 6),
        "median_sec": round(float(median(latencies_sec)), 6),
    }
