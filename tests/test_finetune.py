from __future__ import annotations

import json
from pathlib import Path

from pptcopilot.summarize.finetune import run_finetune


def _write_config(path: Path, *, output_root: Path, adapter_dir: Path) -> Path:
    payload = {
        "run_name": "test_run",
        "backend": "mock_peft",
        "mode": "qlora",
        "base_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "seed": 7,
        "train_steps": 12,
        "learning_rate": 2e-4,
        "train_jsonl": "data/processed/sample.jsonl",
        "eval_suite": "finetune",
        "base_eval_model": "mock",
        "output_root": str(output_root),
        "adapter_dir": str(adapter_dir),
        "simulate_improvement": True,
        "lora": {"r": 8, "alpha": 16, "dropout": 0.05, "target_modules": ["q_proj", "v_proj"]},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_finetune_run_creates_artifacts(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "finetune_small.yaml",
        output_root=tmp_path / "reports",
        adapter_dir=tmp_path / "artifacts" / "adapter",
    )
    report = run_finetune(cfg_path)

    assert Path(report["artifacts"]["run_report"]).exists()
    assert Path(report["artifacts"]["adapter_config"]).exists()
    assert "dataset_sha256" in report["dataset_manifest"]
    assert "overall_score_delta" in report["eval_delta"]


def test_finetune_reproducible_metrics(tmp_path: Path) -> None:
    cfg_path = _write_config(
        tmp_path / "finetune_small.yaml",
        output_root=tmp_path / "reports",
        adapter_dir=tmp_path / "artifacts" / "adapter",
    )
    report_a = run_finetune(cfg_path)
    report_b = run_finetune(cfg_path)

    assert report_a["training_metrics"] == report_b["training_metrics"]
    assert report_a["eval_delta"]["overall_score_delta"] == report_b["eval_delta"]["overall_score_delta"]
