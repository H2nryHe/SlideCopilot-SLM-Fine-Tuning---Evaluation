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


## Milestone 1 — Real RAG + Held-out Evaluation

This branch upgrades the retrieval/QA path from deterministic scaffolding to a real end-to-end RAG system.

### Install real RAG dependencies

```bash
python -m pip install -e ".[rag]"
```

### Build the deterministic Hash baseline

```bash
pptcopilot index data/processed/sample.jsonl \
  --index-dir artifacts/index/hash \
  --retriever hash
```

### Build a real Dense + FAISS index

```bash
pptcopilot index data/processed/sample.jsonl \
  --index-dir artifacts/index/dense \
  --retriever dense \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2
```

Dense mode uses a real SentenceTransformer model with L2-normalized embeddings and a FAISS inner-product index. It fails explicitly when the required dependencies are unavailable; it does not silently fall back to a mock embedding.

### Run real retrieval-grounded generation

```bash
pptcopilot qa \
  --index-dir artifacts/index/dense \
  --question "Which slide discusses evaluation quality?" \
  --generator hf:google/flan-t5-small \
  --debug \
  -o reports/qa/real_rag.json
```

The default local real generator is `google/flan-t5-small`. The legacy deterministic `extractive` generator remains available for fast unit tests.

### Frozen held-out benchmark

Milestone 1 adds a controlled held-out corpus and QA set:

- `data/eval/milestone1_corpus.jsonl`
- `data/eval/milestone1_qa.jsonl`

The queries deliberately use semantic paraphrases instead of copying slide keywords. This makes the Hash vs Dense comparison meaningful.

Run the benchmark:

```bash
pptcopilot eval rag \
  --retriever hash \
  --retriever dense \
  --generator hf:google/flan-t5-small \
  -o reports/eval/milestone1_rag.json
```

Reported metrics:

- Recall@1
- Recall@5
- Recall@10
- MRR
- Answer Accuracy
- Citation Recall

### Measured Milestone 1 results

These values come from GitHub Actions run `39324787023`, successful attempt 2, on the frozen 10-query held-out set.

| System | Recall@1 | Recall@5 | Recall@10 | MRR | Answer Accuracy | Citation Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hash + FAISS + FLAN-T5-small | 0.40 | 0.90 | 1.00 | 0.60 | 0.40 | 0.40 |
| Dense + FAISS + FLAN-T5-small | **1.00** | **1.00** | **1.00** | **1.00** | **0.50** | **0.50** |

The experiment shows a clear retrieval win: Dense retrieval returned the relevant slide at rank 1 for all held-out queries. Generation is now the dominant bottleneck. Full methodology, artifact digests, failure analysis, and the negative generation-context ablation are documented in `reports/eval/MILESTONE1_EXPERIMENT.md`.

### CI evidence

Pull requests run two layers:

1. deterministic unit/regression tests without model downloads;
2. a `real-rag` integration job that installs the actual RAG dependencies, downloads the embedding/generation models, runs a real Dense + FAISS test, then executes the Hash vs Dense held-out benchmark.

The resulting `milestone1_rag.json` is uploaded as the `milestone1-real-rag-benchmark` workflow artifact.

## Milestone 1.5 — Generation Upgrade

Milestone 1.5 keeps the Milestone 1 corpus, 10-query held-out set,
`all-MiniLM-L6-v2` Dense retriever, FAISS index settings, and answer labels frozen.
The runner refuses to execute when either input digest or the embedding model differs
from the frozen protocol.

Run the generation-only comparison:

```bash
pptcopilot eval generation \
  --generator hf:google/flan-t5-small \
  --generator hf:google/flan-t5-base \
  --generator hf-qa:deepset/roberta-base-squad2 \
  -o reports/eval/milestone1_5_generation.json
```

Each model receives the same precomputed retrieval results in three conditions:

- Dense top-5: the production-style multi-evidence context;
- Dense top-1: only the highest-ranked Dense result;
- oracle evidence: chunks selected directly from the held-out expected slide IDs.

Measured results from the final local run:

| Generator | Context | Dense Recall@1 | Answer Accuracy | Citation Recall |
| --- | --- | ---: | ---: | ---: |
| FLAN-T5-small | Dense top-5 | 1.00 | 0.50 | 0.50 |
| FLAN-T5-small | Dense top-1 | 1.00 | 0.70 | 0.90 |
| FLAN-T5-base | Dense top-5 | 1.00 | 0.50 | 0.80 |
| FLAN-T5-base | Dense top-1 | 1.00 | 0.70 | 0.90 |
| **RoBERTa extractive QA** | **Dense top-5** | **1.00** | **0.80** | **0.90** |
| **RoBERTa extractive QA** | **Dense top-1** | **1.00** | **0.90** | **1.00** |
| **RoBERTa extractive QA** | **Oracle evidence** | **1.00** | **0.90** | **1.00** |

The stronger FLAN and Qwen instruct candidates did not beat the original model; those
negative results are retained alongside the final artifact. The task-specific local QA
model meets the 0.80 target at top-5 and reaches 0.90 when distractors are removed.
See `reports/eval/MILESTONE1_5_GENERATION_UPGRADE.md` for digests, model revisions,
per-experiment results, and the remaining error attribution.
