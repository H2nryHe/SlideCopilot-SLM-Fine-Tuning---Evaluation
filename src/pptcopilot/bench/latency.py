"""Latency benchmarking for summarize and QA flows."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pptcopilot.bench.profile import summarize_latency
from pptcopilot.config import get_bench_defaults, get_paths
from pptcopilot.eval.harness import load_scenarios
from pptcopilot.qa.answer import answer_question
from pptcopilot.retrieval.index_faiss import build_index
from pptcopilot.summarize.baseline import summarize_jsonl


def _token_count(text: str) -> int:
    return len(text.split())


def _default_variants() -> list[dict[str, object]]:
    # Always compare at least two variants.
    return [
        {
            "name": "baseline",
            "summarize_model": "mock",
            "include_slide_bullets": True,
            "qa_top_k": 3,
        },
        {
            "name": "fast",
            "summarize_model": "mock",
            "include_slide_bullets": False,
            "qa_top_k": 1,
        },
    ]


def _parse_variant(spec: str) -> dict[str, object]:
    # Format: name:model:topk:bullets(0|1), e.g. fast:mock:1:0
    parts = spec.split(":")
    if len(parts) != 4:
        raise ValueError(
            "Invalid --variant format. Expected name:model:topk:bullets(0|1), "
            f"got '{spec}'"
        )
    name, model, topk_str, bullets_str = parts
    return {
        "name": name,
        "summarize_model": model,
        "qa_top_k": int(topk_str),
        "include_slide_bullets": bool(int(bullets_str)),
    }


def _collect_suite_inputs(suite: str) -> tuple[Path, list[str]]:
    scenarios = load_scenarios(suite=suite)
    if not scenarios:
        raise ValueError(f"No scenarios found for suite '{suite}'")
    summary_inputs = [s for s in scenarios if s["task_type"] == "summary"]
    qa_inputs = [s for s in scenarios if s["task_type"] == "qa"]
    if not summary_inputs:
        raise ValueError(f"No summary scenarios in suite '{suite}'")
    summary_path = Path(summary_inputs[0]["input"]["path"])
    if not summary_path.is_absolute():
        summary_path = get_paths().repo_root / summary_path
    questions = [str(s["input"]["question"]) for s in qa_inputs]
    if not questions:
        questions = ["Which slide discusses evaluation harness and scenarios?"]
    return summary_path.resolve(), questions


def _run_summarize_case(
    *,
    input_jsonl: Path,
    model: str,
    include_slide_bullets: bool,
) -> tuple[float, int]:
    start = time.perf_counter()
    out = summarize_jsonl(
        input_jsonl,
        model=model,
        include_slide_bullets=include_slide_bullets,
    )
    latency = time.perf_counter() - start
    tokens = _token_count(str(out["document_summary"]))
    return latency, tokens


def _run_qa_case(
    *,
    index_dir: Path,
    question: str,
    top_k: int,
) -> tuple[float, int]:
    start = time.perf_counter()
    out = answer_question(index_dir=index_dir, question=question, top_k=top_k, debug=False)
    latency = time.perf_counter() - start
    tokens = _token_count(str(out["answer"]))
    return latency, tokens


def run_latency_benchmark(
    *,
    suite: str,
    out_path: str | Path,
    variants: list[str] | None = None,
    iterations: int | None = None,
    warmup: int | None = None,
    batch_size: int | None = None,
) -> dict[str, object]:
    defaults = get_bench_defaults()
    iterations = defaults.iterations if iterations is None else iterations
    warmup = defaults.warmup if warmup is None else warmup
    batch_size = defaults.batch_size if batch_size is None else batch_size
    if iterations <= 0 or warmup < 0 or batch_size <= 0:
        raise ValueError("iterations>0, warmup>=0, batch_size>0 are required")

    variant_cfgs = (
        [_parse_variant(v) for v in variants] if variants else _default_variants()
    )
    if len(variant_cfgs) < 2:
        raise ValueError("At least two variants are required for comparison")

    summary_path, questions = _collect_suite_inputs(suite)
    index_dir = Path(out_path).parent / "_qa_index"
    build_index(summary_path, index_dir)

    results: list[dict[str, object]] = []
    for variant in variant_cfgs:
        summarize_latencies: list[float] = []
        summarize_tokens: list[int] = []
        qa_latencies: list[float] = []
        qa_tokens: list[int] = []

        for _ in range(warmup):
            _run_summarize_case(
                input_jsonl=summary_path,
                model=str(variant["summarize_model"]),
                include_slide_bullets=bool(variant["include_slide_bullets"]),
            )
            _run_qa_case(
                index_dir=index_dir,
                question=questions[0],
                top_k=int(variant["qa_top_k"]),
            )

        for i in range(iterations):
            for _ in range(batch_size):
                s_latency, s_tokens = _run_summarize_case(
                    input_jsonl=summary_path,
                    model=str(variant["summarize_model"]),
                    include_slide_bullets=bool(variant["include_slide_bullets"]),
                )
                q_latency, q_tokens = _run_qa_case(
                    index_dir=index_dir,
                    question=questions[i % len(questions)],
                    top_k=int(variant["qa_top_k"]),
                )
                summarize_latencies.append(s_latency)
                summarize_tokens.append(s_tokens)
                qa_latencies.append(q_latency)
                qa_tokens.append(q_tokens)

        summarize_stats = summarize_latency(summarize_latencies)
        qa_stats = summarize_latency(qa_latencies)
        s_tps = (
            sum(summarize_tokens) / sum(summarize_latencies)
            if sum(summarize_latencies) > 0
            else 0.0
        )
        q_tps = sum(qa_tokens) / sum(qa_latencies) if sum(qa_latencies) > 0 else 0.0

        results.append(
            {
                "variant": variant["name"],
                "settings": variant,
                "summarize": {
                    **summarize_stats,
                    "tokens_per_sec": round(float(s_tps), 3),
                    "n_samples": len(summarize_latencies),
                },
                "qa": {
                    **qa_stats,
                    "tokens_per_sec": round(float(q_tps), 3),
                    "n_samples": len(qa_latencies),
                },
            }
        )

    report = {
        "suite": suite,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "iterations": iterations,
            "warmup": warmup,
            "batch_size": batch_size,
            "variants": variant_cfgs,
        },
        "results": results,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return report
