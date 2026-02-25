from __future__ import annotations

from pathlib import Path

from pptcopilot.eval.harness import load_scenarios, run_eval_suite


def test_smoke_suite_has_five_scenarios() -> None:
    scenarios = load_scenarios(suite="smoke")
    assert len(scenarios) >= 5


def test_run_eval_suite_writes_latest_reports(tmp_path: Path) -> None:
    report = run_eval_suite(suite="smoke", models=["mock"], outdir=tmp_path / "eval")
    outdir = tmp_path / "eval"

    assert report["summary"]["total_scenarios"] >= 5
    assert (outdir / "latest_report.json").exists()
    assert (outdir / "latest_report.md").exists()
