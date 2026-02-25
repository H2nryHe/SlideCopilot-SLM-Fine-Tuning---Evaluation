from __future__ import annotations

import json
from pathlib import Path

from pptcopilot.bench.cost import run_cost_estimate, write_bench_summary_markdown
from pptcopilot.bench.latency import run_latency_benchmark


def test_latency_benchmark_reports_p95_and_variants(tmp_path: Path) -> None:
    out = tmp_path / "latency.json"
    report = run_latency_benchmark(
        suite="smoke",
        out_path=out,
        iterations=2,
        warmup=0,
        batch_size=1,
    )
    assert out.exists()
    assert len(report["results"]) >= 2
    for row in report["results"]:
        assert "p95_sec" in row["summarize"]
        assert "p95_sec" in row["qa"]


def test_cost_and_summary_outputs(tmp_path: Path) -> None:
    latency_out = tmp_path / "latency.json"
    run_latency_benchmark(
        suite="smoke",
        out_path=latency_out,
        iterations=2,
        warmup=0,
        batch_size=1,
    )
    cost_out = tmp_path / "cost.json"
    cost = run_cost_estimate(latency_report_path=latency_out, out_path=cost_out)
    assert cost_out.exists()
    assert len(cost["results"]) >= 2

    summary_out = tmp_path / "summary.md"
    latency = json.loads(latency_out.read_text(encoding="utf-8"))
    write_bench_summary_markdown(latency_report=latency, cost_report=cost, out_path=summary_out)
    assert summary_out.exists()
