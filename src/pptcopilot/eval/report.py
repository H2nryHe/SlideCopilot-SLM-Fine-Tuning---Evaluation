"""Evaluation report rendering utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def write_report_json(report: dict[str, object], out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report_markdown(report: dict[str, object]) -> str:
    rows = report["results"]
    lines = [
        "# Evaluation Report",
        "",
        f"- suite: `{report['suite']}`",
        f"- models: `{', '.join(report['models'])}`",
        f"- scenarios: `{report['summary']['total_scenarios']}`",
        f"- pass rate: `{_fmt_pct(report['summary']['pass_rate'])}`",
        f"- duration_sec: `{report['summary']['duration_sec']}`",
        "",
        "## Scenario Results",
        "",
        "| model | scenario_id | task | pass | score |",
        "|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['scenario_id']} | {row['task_type']} | "
            f"{'PASS' if row['passed'] else 'FAIL'} | {row['score']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def write_report_markdown(markdown: str, out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def compare_reports(old_report: dict[str, object], new_report: dict[str, object]) -> dict[str, object]:
    old_index = {(r["model"], r["scenario_id"]): r for r in old_report["results"]}
    deltas = []
    for row in new_report["results"]:
        key = (row["model"], row["scenario_id"])
        prev = old_index.get(key)
        if prev is None:
            deltas.append(
                {
                    "model": row["model"],
                    "scenario_id": row["scenario_id"],
                    "delta_score": None,
                    "delta_passed": None,
                    "status": "new",
                }
            )
            continue
        deltas.append(
            {
                "model": row["model"],
                "scenario_id": row["scenario_id"],
                "delta_score": round(float(row["score"]) - float(prev["score"]), 4),
                "delta_passed": int(bool(row["passed"])) - int(bool(prev["passed"])),
                "status": "existing",
            }
        )
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "old_report_generated_at": old_report.get("generated_at_utc"),
        "new_report_generated_at": new_report.get("generated_at_utc"),
        "deltas": deltas,
    }
