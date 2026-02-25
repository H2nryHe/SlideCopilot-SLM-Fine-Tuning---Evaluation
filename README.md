# ppt-copilot

Production-ish applied-science demo for a PowerPoint copilot:
- ingest slides
- summarize
- retrieval-grounded QA with citations
- scenario eval harness
- finetune reproducibility pipeline
- latency/cost benchmarking

## 5–10 Minute Quickstart

### 1) Install

```bash
python -m pip install -e .
```

### 2) Create sample deck + ingest

```bash
python scripts/generate_sample_pptx.py -o data/raw/sample_deck.pptx
pptcopilot ingest data/raw/sample_deck.pptx -o data/processed/sample.jsonl
```

Expected output:
```text
{"status":"ok",...,"n_records":6}
```

### 3) Index + summarize + QA

```bash
pptcopilot index data/processed/sample.jsonl --index-dir artifacts/index/sample
pptcopilot summarize data/processed/sample.jsonl --model mock -o reports/summaries/sample_summary.json
pptcopilot qa --index-dir artifacts/index/sample --question "Which slide discusses evaluation harness?" -o reports/qa/sample_qa.json
```

Expected artifacts:
- `reports/summaries/sample_summary.json`
- `reports/qa/sample_qa.json`

### 4) Run eval suite

```bash
pptcopilot eval run --suite smoke --model mock --outdir reports/eval
```

Expected artifacts:
- `reports/eval/latest_report.json`
- `reports/eval/latest_report.md`

### 5) Run benchmarks

```bash
pptcopilot bench latency --suite smoke --out reports/bench/latency.json --iterations 5 --warmup 1 --batch 1
pptcopilot bench cost --in reports/bench/latency.json --out reports/bench/cost.json --summary-out reports/bench/summary.md
```

Expected artifacts:
- `reports/bench/latency.json`
- `reports/bench/cost.json`
- `reports/bench/summary.md`

## Optional API Demo (FastAPI)

Install API extras:

```bash
python -m pip install -e ".[api]"
```

Run server:

```bash
uvicorn pptcopilot.api.app:app --host 0.0.0.0 --port 8000
```

Endpoints:
- `POST /summarize`
- `POST /qa`
- `POST /eval/run`

Example:

```bash
curl -s http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"input_jsonl":"data/processed/sample.jsonl","model":"mock"}'
```

## CI

Workflow: `.github/workflows/nightly_eval.yml`
- PR/push: runs `pytest`
- nightly cron: runs smoke eval
- uploads `reports/eval/latest_report.json` + `.md` as artifacts

## Finetune Reproducibility

Smoke finetune:

```bash
pptcopilot finetune --config configs/finetune_small.yaml
```

Details: `reports/finetune/README.md`.

## Demo Capture Instructions

Terminal capture (portable):

```bash
script -q demo_terminal.txt
# run ingest -> index -> summarize -> qa -> eval commands
exit
```

Optional GIF route:
1. Record terminal with any recorder (`asciinema rec demo.cast` or screen recorder).
2. Convert to GIF (`agg`, `asciinema + svg-term`, or editor export).
3. Attach the GIF to your repo/PR.

## Failure Handling

- CLI now emits structured JSON errors and logs stack traces.
- API endpoints return HTTP 400 with informative `detail` messages.
