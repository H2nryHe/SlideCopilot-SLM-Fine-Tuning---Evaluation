"""SPOCK-lite evaluation harness."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pptcopilot.config import get_paths
from pptcopilot.eval.metrics import answer_match, citation_recall, keyword_coverage
from pptcopilot.eval.report import (
    render_report_markdown,
    write_report_json,
    write_report_markdown,
)
from pptcopilot.qa.answer import answer_question
from pptcopilot.retrieval.index_faiss import build_index
from pptcopilot.summarize.baseline import summarize_jsonl


def _scenarios_dir() -> Path:
    return Path(__file__).resolve().parent / "scenarios"


def load_scenarios(*, suite: str) -> list[dict[str, object]]:
    scenarios = []
    for path in sorted(_scenarios_dir().glob("s*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        suites = payload.get("suites", [])
        if suite in suites:
            scenarios.append(payload)
    return scenarios


def _resolve_input_path(scenario: dict[str, object]) -> Path:
    ref = scenario["input"]["path"]
    path = Path(ref)
    if path.is_absolute():
        return path
    return (get_paths().repo_root / path).resolve()


def _evaluate_summary_scenario(scenario: dict[str, object], model: str) -> dict[str, object]:
    input_path = _resolve_input_path(scenario)
    output = summarize_jsonl(input_path, model=model, include_slide_bullets=True)
    summary = str(output["document_summary"])
    required_points = [str(x) for x in scenario["expected"]["required_key_points"]]
    metric = keyword_coverage(summary, required_points)
    threshold = float(scenario["rubric"].get("min_keypoint_coverage", 0.5))
    passed = bool(metric["coverage"] >= threshold)
    return {
        "model": model,
        "scenario_id": scenario["scenario_id"],
        "task_type": "summary",
        "passed": passed,
        "score": float(metric["coverage"]),
        "details": {
            "metric": metric,
            "threshold": threshold,
            "summary_preview": summary[:200],
        },
    }


def _evaluate_qa_scenario(
    scenario: dict[str, object],
    model: str,
    *,
    outdir: Path,
) -> dict[str, object]:
    input_path = _resolve_input_path(scenario)
    index_dir = outdir / "_indices" / model / scenario["scenario_id"]
    build_index(input_path, index_dir)

    question = str(scenario["input"]["question"])
    top_k = int(scenario["input"].get("top_k", 3))
    result = answer_question(index_dir=index_dir, question=question, top_k=top_k, debug=True)

    acceptable_answers = [str(x) for x in scenario["expected"].get("acceptable_answers", [])]
    expected_slide_ids = [str(x) for x in scenario["expected"].get("expected_slide_ids", [])]

    answer_metric = answer_match(str(result["answer"]), acceptable_answers)
    citation_metric = citation_recall(
        [str(x) for x in result["cited_slide_ids"]],
        expected_slide_ids,
    )
    min_citation_recall = float(scenario["rubric"].get("min_citation_recall", 0.5))
    score = 0.5 * float(answer_metric["matched"]) + 0.5 * float(citation_metric["recall"])
    passed = bool(answer_metric["matched"] and citation_metric["recall"] >= min_citation_recall)
    return {
        "model": model,
        "scenario_id": scenario["scenario_id"],
        "task_type": "qa",
        "passed": passed,
        "score": round(score, 4),
        "details": {
            "answer_metric": answer_metric,
            "citation_metric": citation_metric,
            "thresholds": {"min_citation_recall": min_citation_recall},
            "answer_preview": str(result["answer"])[:200],
            "retrieved_chunks": result.get("retrieved_chunks", []),
        },
    }


def run_eval_suite(
    *,
    suite: str,
    models: list[str],
    outdir: str | Path,
) -> dict[str, object]:
    if not models:
        raise ValueError("At least one model must be provided")
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)

    scenarios = load_scenarios(suite=suite)
    if not scenarios:
        raise ValueError(f"No scenarios found for suite '{suite}'")

    start = time.perf_counter()
    results: list[dict[str, object]] = []
    for model in models:
        for scenario in scenarios:
            task_type = scenario["task_type"]
            if task_type == "summary":
                row = _evaluate_summary_scenario(scenario, model)
            elif task_type == "qa":
                row = _evaluate_qa_scenario(scenario, model, outdir=out_path)
            else:
                raise ValueError(f"Unsupported task_type '{task_type}' in {scenario['scenario_id']}")
            results.append(row)

    duration = time.perf_counter() - start
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    avg_score = sum(float(r["score"]) for r in results) / total if total else 0.0
    report = {
        "suite": suite,
        "models": models,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_scenarios": total,
            "passed_scenarios": passed,
            "pass_rate": round(passed / total if total else 0.0, 4),
            "overall_score": round(avg_score, 4),
            "duration_sec": round(duration, 4),
        },
        "results": results,
    }
    report["artifacts"] = {
        "latest_report_json": str((out_path / "latest_report.json").resolve()),
        "latest_report_md": str((out_path / "latest_report.md").resolve()),
    }
    json_path = write_report_json(report, out_path / "latest_report.json")
    markdown = render_report_markdown(report)
    md_path = write_report_markdown(markdown, out_path / "latest_report.md")
    report["artifacts"] = {
        "latest_report_json": str(json_path.resolve()),
        "latest_report_md": str(md_path.resolve()),
    }
    return report
