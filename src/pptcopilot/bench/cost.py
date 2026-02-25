"""Cost estimation from latency benchmark outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pptcopilot.config import get_bench_defaults


def _estimate_cost_per_1k_requests(
    *,
    latency_sec: float,
    cost_per_gpu_hour_usd: float,
    utilization: float,
) -> float:
    effective_cost_per_sec = (cost_per_gpu_hour_usd / 3600.0) / max(utilization, 1e-9)
    return effective_cost_per_sec * latency_sec * 1000.0


def run_cost_estimate(
    *,
    latency_report_path: str | Path,
    out_path: str | Path,
    cost_per_gpu_hour_usd: float | None = None,
    utilization: float | None = None,
) -> dict[str, object]:
    defaults = get_bench_defaults()
    cost_per_gpu_hour_usd = (
        defaults.cost_per_gpu_hour_usd if cost_per_gpu_hour_usd is None else cost_per_gpu_hour_usd
    )
    utilization = defaults.target_utilization if utilization is None else utilization
    if utilization <= 0 or utilization > 1:
        raise ValueError("utilization must be in (0, 1]")

    latency_payload = json.loads(Path(latency_report_path).read_text(encoding="utf-8"))
    rows = []
    for row in latency_payload["results"]:
        s = row["summarize"]
        q = row["qa"]
        s_cost = _estimate_cost_per_1k_requests(
            latency_sec=float(s["p95_sec"]),
            cost_per_gpu_hour_usd=cost_per_gpu_hour_usd,
            utilization=utilization,
        )
        q_cost = _estimate_cost_per_1k_requests(
            latency_sec=float(q["p95_sec"]),
            cost_per_gpu_hour_usd=cost_per_gpu_hour_usd,
            utilization=utilization,
        )
        rows.append(
            {
                "variant": row["variant"],
                "summarize_usd_per_1k_req_p95": round(s_cost, 4),
                "qa_usd_per_1k_req_p95": round(q_cost, 4),
                "blended_usd_per_1k_req_p95": round((s_cost + q_cost) / 2.0, 4),
            }
        )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_latency_report": str(Path(latency_report_path).resolve()),
        "assumptions": {
            "cost_per_gpu_hour_usd": cost_per_gpu_hour_usd,
            "utilization": utilization,
            "uses_p95_latency": True,
            "formula": "(gpu_hour_cost/3600/utilization) * latency_sec * 1000",
        },
        "results": rows,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return report


def write_bench_summary_markdown(
    *,
    latency_report: dict[str, object],
    cost_report: dict[str, object],
    out_path: str | Path,
) -> Path:
    cost_index = {row["variant"]: row for row in cost_report["results"]}
    lines = [
        "# Benchmark Summary",
        "",
        f"- suite: `{latency_report['suite']}`",
        f"- generated_at: `{latency_report['generated_at_utc']}`",
        "",
        "## Latency And Throughput",
        "",
        "| variant | summarize p50 (s) | summarize p95 (s) | summarize tok/s | qa p50 (s) | qa p95 (s) | qa tok/s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in latency_report["results"]:
        s = row["summarize"]
        q = row["qa"]
        lines.append(
            f"| {row['variant']} | {s['p50_sec']:.6f} | {s['p95_sec']:.6f} | {s['tokens_per_sec']:.3f} "
            f"| {q['p50_sec']:.6f} | {q['p95_sec']:.6f} | {q['tokens_per_sec']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Cost Estimate (USD per 1k requests, p95 latency-based)",
            "",
            "| variant | summarize | qa | blended |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in latency_report["results"]:
        c = cost_index[row["variant"]]
        lines.append(
            f"| {row['variant']} | {c['summarize_usd_per_1k_req_p95']:.4f} "
            f"| {c['qa_usd_per_1k_req_p95']:.4f} | {c['blended_usd_per_1k_req_p95']:.4f} |"
        )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
