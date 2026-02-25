"""Stage 6 finetune pipeline with reproducibility artifacts."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pptcopilot.eval.harness import run_eval_suite
from pptcopilot.eval.report import compare_reports


@dataclass(frozen=True)
class FineTuneConfig:
    run_name: str
    backend: str
    mode: str
    base_model: str
    seed: int
    train_steps: int
    learning_rate: float
    train_jsonl: str
    eval_suite: str
    base_eval_model: str
    output_root: str
    adapter_dir: str
    simulate_improvement: bool
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    target_modules: list[str]
    repro_tolerance: float


def _load_config(config_path: str | Path) -> FineTuneConfig:
    path = Path(config_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    lora = payload.get("lora", {})
    return FineTuneConfig(
        run_name=str(payload.get("run_name", "finetune_run")),
        backend=str(payload.get("backend", "mock_peft")),
        mode=str(payload.get("mode", "qlora")),
        base_model=str(payload.get("base_model", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")),
        seed=int(payload.get("seed", 42)),
        train_steps=int(payload.get("train_steps", 20)),
        learning_rate=float(payload.get("learning_rate", 2e-4)),
        train_jsonl=str(payload["train_jsonl"]),
        eval_suite=str(payload.get("eval_suite", "finetune")),
        base_eval_model=str(payload.get("base_eval_model", "mock")),
        output_root=str(payload.get("output_root", "reports/finetune")),
        adapter_dir=str(payload.get("adapter_dir", "artifacts/finetune/mock_adapter")),
        simulate_improvement=bool(payload.get("simulate_improvement", True)),
        lora_r=int(lora.get("r", 8)),
        lora_alpha=int(lora.get("alpha", 16)),
        lora_dropout=float(lora.get("dropout", 0.05)),
        target_modules=[str(x) for x in lora.get("target_modules", ["q_proj", "v_proj"])],
        repro_tolerance=float(payload.get("repro_tolerance", 1e-9)),
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dataset_manifest(dataset_path: Path) -> dict[str, object]:
    raw = dataset_path.read_bytes()
    rows = _read_jsonl(dataset_path)
    slide_ids = [str(r.get("slide_id", "")) for r in rows]
    return {
        "dataset_path": str(dataset_path.resolve()),
        "dataset_sha256": _sha256_bytes(raw),
        "n_rows": len(rows),
        "slide_ids_sha256": _sha256_bytes("|".join(slide_ids).encode("utf-8")),
    }


def _simulate_training_metrics(cfg: FineTuneConfig, dataset_sha: str) -> dict[str, float]:
    random.seed(f"{cfg.seed}:{dataset_sha}:{cfg.train_steps}")
    base_loss = 2.0 + random.random() * 0.2
    final_loss = base_loss - (0.3 + random.random() * 0.2)
    return {
        "train_loss_start": round(base_loss, 6),
        "train_loss_end": round(max(0.01, final_loss), 6),
        "train_loss_delta": round(base_loss - final_loss, 6),
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def _create_adapter_artifact(cfg: FineTuneConfig, adapter_dir: Path) -> dict[str, str]:
    adapter_dir.mkdir(parents=True, exist_ok=True)
    adapter_cfg = {
        "backend": cfg.backend,
        "mode": cfg.mode,
        "base_model": cfg.base_model,
        "seed": cfg.seed,
        "summary_behavior": {
            "include_all_titles": bool(cfg.simulate_improvement),
            "max_titles": 8 if cfg.simulate_improvement else 5,
        },
    }
    peft_cfg = {
        "peft_type": "LORA",
        "r": cfg.lora_r,
        "lora_alpha": cfg.lora_alpha,
        "lora_dropout": cfg.lora_dropout,
        "target_modules": cfg.target_modules,
        "task_type": "SEQ_2_SEQ_LM",
    }
    _write_json(adapter_dir / "adapter_config.json", adapter_cfg)
    _write_json(adapter_dir / "peft_config.json", peft_cfg)
    (adapter_dir / "README.txt").write_text(
        "Mock adapter artifact for compute-light reproducibility runs.\n", encoding="utf-8"
    )
    return {
        "adapter_config": str((adapter_dir / "adapter_config.json").resolve()),
        "peft_config": str((adapter_dir / "peft_config.json").resolve()),
    }


def _maybe_run_real_peft_backend(cfg: FineTuneConfig) -> dict[str, object]:
    if cfg.backend != "peft":
        return {"backend_mode": "mock"}
    try:
        import peft  # type: ignore # noqa: F401
        import transformers  # type: ignore # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "backend=peft requested but peft/transformers are unavailable. "
            "Use backend=mock_peft for smoke runs."
        ) from exc
    return {
        "backend_mode": "peft_stub",
        "note": (
            "PEFT backend dependencies detected. This scaffold keeps training "
            "logic lightweight; extend here with Trainer/SFT flow for GPU runs."
        ),
    }


def run_finetune(config_path: str | Path) -> dict[str, object]:
    cfg = _load_config(config_path)
    dataset_path = Path(cfg.train_jsonl)
    if not dataset_path.is_absolute():
        dataset_path = (Path.cwd() / dataset_path).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Training dataset not found: {dataset_path}")

    output_root = Path(cfg.output_root)
    if not output_root.is_absolute():
        output_root = (Path.cwd() / output_root).resolve()
    run_dir = output_root / cfg.run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    adapter_dir = Path(cfg.adapter_dir)
    if not adapter_dir.is_absolute():
        adapter_dir = (Path.cwd() / adapter_dir).resolve()

    manifest = _dataset_manifest(dataset_path)
    backend_info = _maybe_run_real_peft_backend(cfg)
    train_metrics = _simulate_training_metrics(cfg, str(manifest["dataset_sha256"]))
    adapter_files = _create_adapter_artifact(cfg, adapter_dir)
    finetuned_model_variant = f"finetuned:{adapter_dir}"

    pre_eval = run_eval_suite(
        suite=cfg.eval_suite,
        models=[cfg.base_eval_model],
        outdir=run_dir / "eval_pre",
    )
    post_eval = run_eval_suite(
        suite=cfg.eval_suite,
        models=[finetuned_model_variant],
        outdir=run_dir / "eval_post",
    )
    delta = compare_reports(pre_eval, post_eval)
    score_delta = round(
        float(post_eval["summary"]["overall_score"]) - float(pre_eval["summary"]["overall_score"]),
        4,
    )
    pass_rate_delta = round(
        float(post_eval["summary"]["pass_rate"]) - float(pre_eval["summary"]["pass_rate"]),
        4,
    )
    tradeoff_note = None
    if score_delta <= 0 and pass_rate_delta <= 0:
        tradeoff_note = (
            "No net gain on this suite; baseline may already be saturated. "
            "Consider harder held-out scenarios."
        )

    run_report = {
        "run_name": cfg.run_name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "config_path": str(Path(config_path).resolve()),
            "backend": cfg.backend,
            "mode": cfg.mode,
            "base_model": cfg.base_model,
            "seed": cfg.seed,
            "train_steps": cfg.train_steps,
            "learning_rate": cfg.learning_rate,
            "eval_suite": cfg.eval_suite,
            "base_eval_model": cfg.base_eval_model,
            "finetuned_model_variant": finetuned_model_variant,
            "lora": {
                "r": cfg.lora_r,
                "alpha": cfg.lora_alpha,
                "dropout": cfg.lora_dropout,
                "target_modules": cfg.target_modules,
            },
        },
        "dataset_manifest": manifest,
        "training_metrics": train_metrics,
        "backend_info": backend_info,
        "artifacts": {
            "run_dir": str(run_dir.resolve()),
            "adapter_dir": str(adapter_dir.resolve()),
            **adapter_files,
        },
        "eval_before": {
            "overall_score": pre_eval["summary"]["overall_score"],
            "pass_rate": pre_eval["summary"]["pass_rate"],
            "report_json": pre_eval["artifacts"]["latest_report_json"],
            "report_md": pre_eval["artifacts"]["latest_report_md"],
        },
        "eval_after": {
            "overall_score": post_eval["summary"]["overall_score"],
            "pass_rate": post_eval["summary"]["pass_rate"],
            "report_json": post_eval["artifacts"]["latest_report_json"],
            "report_md": post_eval["artifacts"]["latest_report_md"],
        },
        "eval_delta": {
            "overall_score_delta": score_delta,
            "pass_rate_delta": pass_rate_delta,
            "delta_details_path": str(
                _write_json(run_dir / "eval_delta.json", delta).resolve()
            ),
            "tradeoff_note": tradeoff_note,
        },
    }
    report_path = _write_json(run_dir / "run_report.json", run_report)
    run_report["artifacts"]["run_report"] = str(report_path.resolve())
    return run_report
