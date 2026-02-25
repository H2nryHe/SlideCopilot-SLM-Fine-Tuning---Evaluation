"""Command-line interface for ppt-copilot."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Sequence

from pptcopilot import __version__
from pptcopilot.bench.cost import run_cost_estimate, write_bench_summary_markdown
from pptcopilot.bench.latency import run_latency_benchmark
from pptcopilot.config import get_paths, get_retrieval_defaults
from pptcopilot.eval.harness import run_eval_suite
from pptcopilot.eval.report import compare_reports, write_report_json
from pptcopilot.io.ingest_pptx import ingest_pptx, validate_records, write_jsonl
from pptcopilot.qa.answer import answer_question, write_answer
from pptcopilot.retrieval.index_faiss import build_index
from pptcopilot.summarize.baseline import summarize_jsonl, write_summary
from pptcopilot.summarize.finetune import run_finetune

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pptcopilot",
        description="PPT Copilot command-line toolkit.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    hello_parser = subparsers.add_parser("hello", help="Run a minimal hello pipeline.")
    hello_parser.set_defaults(func=_run_hello)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a PPTX into JSONL.")
    ingest_parser.add_argument("input_path", help="Path to a .pptx file")
    ingest_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Path to output JSONL file",
    )
    ingest_parser.set_defaults(func=_run_ingest)

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Summarize ingested slide JSONL into a summary JSON report.",
    )
    summarize_parser.add_argument("input_jsonl", help="Path to slide JSONL")
    summarize_parser.add_argument(
        "--model",
        default="mock",
        help="Summarization model backend. Use 'mock' or 'hf:<model_name>'.",
    )
    summarize_parser.add_argument(
        "--no-slide-bullets",
        action="store_true",
        help="Disable optional slide-level bullets in output.",
    )
    summarize_parser.add_argument("-o", "--output", required=True, help="Output summary JSON path")
    summarize_parser.set_defaults(func=_run_summarize)

    retrieval_defaults = get_retrieval_defaults()
    index_parser = subparsers.add_parser("index", help="Build retrieval index from slide JSONL.")
    index_parser.add_argument("input_jsonl", help="Path to slide JSONL")
    index_parser.add_argument("--index-dir", required=True, help="Directory for index artifacts")
    index_parser.add_argument(
        "--chunk-size-tokens",
        type=int,
        default=retrieval_defaults.chunk_size_tokens,
        help=f"Chunk size in tokens (default: {retrieval_defaults.chunk_size_tokens}).",
    )
    index_parser.add_argument(
        "--chunk-overlap-tokens",
        type=int,
        default=retrieval_defaults.chunk_overlap_tokens,
        help=f"Chunk overlap in tokens (default: {retrieval_defaults.chunk_overlap_tokens}).",
    )
    index_parser.add_argument(
        "--embedding-dim",
        type=int,
        default=retrieval_defaults.embedding_dim,
        help=f"Embedding dimension (default: {retrieval_defaults.embedding_dim}).",
    )
    index_parser.set_defaults(func=_run_index)

    qa_parser = subparsers.add_parser("qa", help="Answer a question using retrieval with citations.")
    qa_parser.add_argument("--index-dir", required=True, help="Directory containing index artifacts")
    qa_parser.add_argument("--question", required=True, help="User question")
    qa_parser.add_argument(
        "--top-k",
        type=int,
        default=retrieval_defaults.top_k,
        help=f"Number of chunks to retrieve (default: {retrieval_defaults.top_k}).",
    )
    qa_parser.add_argument(
        "--debug",
        action="store_true",
        help="Include retrieved chunks in output JSON for debugging.",
    )
    qa_parser.add_argument("-o", "--output", required=True, help="Output answer JSON path")
    qa_parser.set_defaults(func=_run_qa)

    eval_parser = subparsers.add_parser("eval", help="Run scenario-based evaluation suites.")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command")
    eval_run_parser = eval_subparsers.add_parser("run", help="Run an evaluation suite.")
    eval_run_parser.add_argument("--suite", default="smoke", help="Scenario suite name.")
    eval_run_parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Model variant to evaluate. Repeat flag for multiple variants. Default: mock",
    )
    eval_run_parser.add_argument(
        "--outdir",
        default="reports/eval",
        help="Output directory for latest_report.json/md",
    )
    eval_run_parser.set_defaults(func=_run_eval_run)

    eval_compare_parser = eval_subparsers.add_parser(
        "compare",
        help="Compare two report JSON files and write deltas.",
    )
    eval_compare_parser.add_argument("--old", required=True, help="Path to older report JSON")
    eval_compare_parser.add_argument("--new", required=True, help="Path to newer report JSON")
    eval_compare_parser.add_argument(
        "-o",
        "--output",
        default="reports/eval/latest_delta.json",
        help="Output delta JSON path",
    )
    eval_compare_parser.set_defaults(func=_run_eval_compare)

    finetune_parser = subparsers.add_parser("finetune", help="Run finetune workflow from config.")
    finetune_parser.add_argument("--config", required=True, help="Path to finetune config yaml/json")
    finetune_parser.set_defaults(func=_run_finetune)

    bench_parser = subparsers.add_parser("bench", help="Run latency and cost benchmarks.")
    bench_subparsers = bench_parser.add_subparsers(dest="bench_command")

    bench_latency_parser = bench_subparsers.add_parser("latency", help="Run latency benchmark.")
    bench_latency_parser.add_argument("--suite", default="smoke", help="Scenario suite to sample.")
    bench_latency_parser.add_argument(
        "--variant",
        action="append",
        dest="variants",
        help="Variant spec: name:model:topk:bullets(0|1). Repeat for multiple variants.",
    )
    bench_latency_parser.add_argument("--iterations", type=int, default=5, help="Measured iterations.")
    bench_latency_parser.add_argument("--warmup", type=int, default=1, help="Warmup iterations.")
    bench_latency_parser.add_argument("--batch", type=int, default=1, help="Batch size per iteration.")
    bench_latency_parser.add_argument(
        "--out",
        default="reports/bench/latency.json",
        help="Latency report JSON output path.",
    )
    bench_latency_parser.set_defaults(func=_run_bench_latency)

    bench_cost_parser = bench_subparsers.add_parser("cost", help="Estimate cost from latency report.")
    bench_cost_parser.add_argument(
        "--in",
        dest="input_report",
        required=True,
        help="Input latency report JSON path.",
    )
    bench_cost_parser.add_argument(
        "--out",
        default="reports/bench/cost.json",
        help="Cost report JSON output path.",
    )
    bench_cost_parser.add_argument(
        "--cost-per-gpu-hour",
        type=float,
        default=None,
        help="USD per GPU hour assumption.",
    )
    bench_cost_parser.add_argument(
        "--utilization",
        type=float,
        default=None,
        help="Target utilization in (0,1].",
    )
    bench_cost_parser.add_argument(
        "--summary-out",
        default="reports/bench/summary.md",
        help="Human-readable benchmark summary markdown path.",
    )
    bench_cost_parser.set_defaults(func=_run_bench_cost)
    return parser


def _run_hello(_: argparse.Namespace) -> int:
    paths = get_paths()
    print("ppt-copilot bootstrap is ready.")
    print(f"repo_root={paths.repo_root}")
    return 0


def _run_ingest(args: argparse.Namespace) -> int:
    input_path = Path(args.input_path)
    output_path = Path(args.output)
    records = ingest_pptx(input_path)
    validate_records(records)
    write_jsonl(records, output_path)
    print(
        json.dumps(
            {
                "status": "ok",
                "input_path": str(input_path.resolve()),
                "output_path": str(output_path.resolve()),
                "n_records": len(records),
            },
            ensure_ascii=True,
        )
    )
    return 0


def _run_summarize(args: argparse.Namespace) -> int:
    result = summarize_jsonl(
        args.input_jsonl,
        model=args.model,
        include_slide_bullets=not args.no_slide_bullets,
    )
    output_path = write_summary(result, args.output)
    print(
        json.dumps(
            {
                "status": "ok",
                "input_path": str(Path(args.input_jsonl).resolve()),
                "output_path": str(output_path.resolve()),
                "model": args.model,
                "runtime_sec": result["metadata"]["runtime_sec"],
            },
            ensure_ascii=True,
        )
    )
    return 0


def _run_index(args: argparse.Namespace) -> int:
    metadata = build_index(
        args.input_jsonl,
        args.index_dir,
        chunk_size_tokens=args.chunk_size_tokens,
        chunk_overlap_tokens=args.chunk_overlap_tokens,
        embedding_dim=args.embedding_dim,
    )
    print(json.dumps({"status": "ok", **metadata}, ensure_ascii=True))
    return 0


def _run_qa(args: argparse.Namespace) -> int:
    payload = answer_question(
        index_dir=args.index_dir,
        question=args.question,
        top_k=args.top_k,
        debug=args.debug,
    )
    out_path = write_answer(payload, args.output)
    print(
        json.dumps(
            {
                "status": "ok",
                "output_path": str(out_path.resolve()),
                "n_citations": len(payload["cited_slide_ids"]),
            },
            ensure_ascii=True,
        )
    )
    return 0


def _run_eval_run(args: argparse.Namespace) -> int:
    models = args.models if args.models else ["mock"]
    report = run_eval_suite(suite=args.suite, models=models, outdir=args.outdir)
    print(
        json.dumps(
            {
                "status": "ok",
                "suite": args.suite,
                "models": models,
                "total_scenarios": report["summary"]["total_scenarios"],
                "pass_rate": report["summary"]["pass_rate"],
                "overall_score": report["summary"]["overall_score"],
                "latest_report_json": report["artifacts"]["latest_report_json"],
                "latest_report_md": report["artifacts"]["latest_report_md"],
            },
            ensure_ascii=True,
        )
    )
    return 0


def _run_eval_compare(args: argparse.Namespace) -> int:
    old_report = json.loads(Path(args.old).read_text(encoding="utf-8"))
    new_report = json.loads(Path(args.new).read_text(encoding="utf-8"))
    delta = compare_reports(old_report, new_report)
    out_path = write_report_json(delta, args.output)
    print(
        json.dumps(
            {
                "status": "ok",
                "output_path": str(out_path.resolve()),
                "n_deltas": len(delta["deltas"]),
            },
            ensure_ascii=True,
        )
    )
    return 0


def _run_finetune(args: argparse.Namespace) -> int:
    report = run_finetune(args.config)
    print(
        json.dumps(
            {
                "status": "ok",
                "run_name": report["run_name"],
                "run_report": report["artifacts"]["run_report"],
                "eval_before_score": report["eval_before"]["overall_score"],
                "eval_after_score": report["eval_after"]["overall_score"],
                "score_delta": report["eval_delta"]["overall_score_delta"],
                "pass_rate_delta": report["eval_delta"]["pass_rate_delta"],
            },
            ensure_ascii=True,
        )
    )
    return 0


def _run_bench_latency(args: argparse.Namespace) -> int:
    report = run_latency_benchmark(
        suite=args.suite,
        out_path=args.out,
        variants=args.variants,
        iterations=args.iterations,
        warmup=args.warmup,
        batch_size=args.batch,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "suite": report["suite"],
                "variants": [r["variant"] for r in report["results"]],
                "output_path": str(Path(args.out).resolve()),
            },
            ensure_ascii=True,
        )
    )
    return 0


def _run_bench_cost(args: argparse.Namespace) -> int:
    cost_report = run_cost_estimate(
        latency_report_path=args.input_report,
        out_path=args.out,
        cost_per_gpu_hour_usd=args.cost_per_gpu_hour,
        utilization=args.utilization,
    )
    latency_report = json.loads(Path(args.input_report).read_text(encoding="utf-8"))
    summary_path = write_bench_summary_markdown(
        latency_report=latency_report,
        cost_report=cost_report,
        out_path=args.summary_out,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "cost_output_path": str(Path(args.out).resolve()),
                "summary_output_path": str(summary_path.resolve()),
                "n_variants": len(cost_report["results"]),
            },
            ensure_ascii=True,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        try:
            return int(args.func(args))
        except Exception as exc:
            logger.exception("Command execution failed")
            print(
                json.dumps(
                    {
                        "status": "error",
                        "command": str(getattr(args, "command", "unknown")),
                        "error": str(exc),
                    },
                    ensure_ascii=True,
                ),
                file=sys.stderr,
            )
            return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
