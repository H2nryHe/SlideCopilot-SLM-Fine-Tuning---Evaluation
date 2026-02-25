# Stage 6 Review

## Scope
Implemented finetune pipeline with deterministic smoke backend, adapter artifacts, dataset manifests, and before/after SPOCK-lite eval comparison.

## Commands Run

```bash
python -m pip install -e .
pytest
pptcopilot finetune --config configs/finetune_small.yaml
pptcopilot summarize data/processed/sample.jsonl --model finetuned:artifacts/finetune/small_mock_peft_adapter -o reports/summaries/finetuned_summary.json
pptcopilot eval run --suite finetune --model mock --model finetuned:artifacts/finetune/small_mock_peft_adapter --outdir reports/finetune/comparison
```

Repro check:

```bash
cp reports/finetune/small_mock_peft/run_report.json reports/finetune/small_mock_peft/run_report_run1.json
pptcopilot finetune --config configs/finetune_small.yaml
cp reports/finetune/small_mock_peft/run_report.json reports/finetune/small_mock_peft/run_report_run2.json
```

## Outputs

- `pytest`: `18 passed in 0.11s`
- finetune command output:
  - `eval_before_score=0.6111`
  - `eval_after_score=1.0`
  - `score_delta=0.3889`
  - `pass_rate_delta=0.6667`
- run report:
  - `reports/finetune/small_mock_peft/run_report.json`
  - includes dataset hash manifest, config/seed, training metrics, eval metrics, and artifact paths
- reproducibility check:
  - training metrics identical across reruns
  - eval deltas identical across reruns
