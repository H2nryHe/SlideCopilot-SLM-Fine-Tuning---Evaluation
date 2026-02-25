# Finetune Reproducibility

## Smoke config (compute-light)

Use the tiny deterministic config:

```bash
pptcopilot finetune --config configs/finetune_small.yaml
```

This runs a mock PEFT/QLoRA pipeline that logs:
- dataset manifest (`dataset_sha256`, row counts, slide-id hash)
- full config + seed
- training metrics
- eval before/after + delta

Outputs are written under:
- `reports/finetune/<run_name>/`
- adapter artifact under `artifacts/finetune/...`

## PEFT path

`configs/finetune_peft_example.yaml` demonstrates the same interface with `backend=peft`.
If `peft`/`transformers` are installed and compute is available, extend
`src/pptcopilot/summarize/finetune.py` in `_maybe_run_real_peft_backend`.

## Repro check

Re-run the same command with the same config/seed. The smoke backend is deterministic:
training metrics and eval deltas should be near-identical (exact for this scaffold).
