# PROJECT_SPEC.md — PPT Copilot (SLM Fine-tuning + SPOCK-lite Evaluation + Latency/Cost Bench)

## 0) One-line pitch
Build a **Copilot-style PowerPoint assistant** that can **summarize slides + answer questions**, backed by a **scenario-based evaluation harness** (SPOCK-lite) and a **latency/cost benchmark** so you can iterate like a production applied-science team.

## 1) What “good” looks like (product KPIs)
You will be judged on the same axis as Office AI Platform-style work:
- **Quality:** summary usefulness + Q&A correctness measured by scenario-based evals
- **Reliability:** regression tests catch quality drops when models/prompts change
- **Speed:** p50/p95 latency and throughput (tokens/s) tracked
- **Cost-awareness:** rough GPU cost estimate per 1k requests, trade-off curves

## 2) Non-goals (to prevent scope creep)
- No full UI app requirement (CLI + minimal API demo is enough)
- No need to beat SOTA; focus on **reproducibility, eval rigor, and engineering**
- No proprietary Office data required

## 3) Tech choices (recommended defaults)
- Language: **Python 3.11**
- Core: **PyTorch + Hugging Face Transformers**
- Retrieval: sentence-transformers (or OpenAI embeddings if allowed), FAISS
- Fine-tuning: **LoRA/QLoRA** via PEFT
- Eval: custom harness + optional LLM-as-judge (pluggable)
- Serving: FastAPI (optional but recommended)
- CI: GitHub Actions (daily scheduled eval run)
- Data: JSONL + parquet (optional) + manifests with hashes for versioning

## 4) Repository structure (target)
```
ppt-copilot/
  README.md
  PROJECT_SPEC.md
  TASK_BOARD.md
  pyproject.toml
  src/pptcopilot/
    __init__.py
    config.py
    io/
      ingest_pptx.py
      ingest_pdf.py
      ocr.py
      chunking.py
    retrieval/
      embed.py
      index_faiss.py
      retrieve.py
    summarize/
      baseline.py
      prompts.py
    qa/
      answer.py
      citations.py
    eval/
      scenarios/
        README.md
        s001_slide_summary.json
        s002_slide_qa.json
      harness.py
      metrics.py
      judges.py
      report.py
    bench/
      latency.py
      cost.py
      profile.py
    api/
      app.py
    cli.py
  data/
    raw/              # not committed; use .gitignore
    processed/        # optional small sample committed
    manifests/
  reports/
    eval/             # generated, can be committed as artifacts
    bench/
  .github/workflows/
    nightly_eval.yml
  tests/
    test_ingest.py
    test_eval_harness.py
    test_retrieval.py
```

## 5) Stage plan (each stage has a gate + review)
**Rule:** Do NOT proceed to the next stage until the **Stage Gate** is satisfied.
At the end of every stage, you will do:
1) **Run the checks**
2) **Inspect outputs**
3) **Record results** (in `reports/` and a short note in the PR/commit message)
4) **Decide next stage readiness**

---

# Stage 1 — Bootstrap & Reproducibility Scaffold
### Goal
Create a clean, reproducible project skeleton with linting, tests, and a “hello pipeline”.

### Deliverables
- Repo structure created
- `pyproject.toml` with dependencies
- `src/pptcopilot/cli.py` with `pptcopilot --help`
- Basic unit test framework (pytest)
- `.gitignore` for data, caches

### Implementation notes
- Add a `make`-like set of commands (Makefile or `scripts/`)
- Add `pre-commit` hooks if you like (optional)

### Stage Gate (must pass)
- `python -m pip install -e .` works
- `pytest` passes (even if only one trivial test)
- `pptcopilot --help` prints usage

### Stage Review (before moving on)
- Can a fresh clone run in <10 minutes?
- Does the project layout match the target structure?
- Is there a single source of truth config (`config.py`)?

---

# Stage 2 — Data Ingestion (PPTX/PDF → Slide Text + Metadata)
### Goal
Turn PPTX or PDF slides into a **standard internal sample format**.

### Deliverables
- `ingest_pptx.py` and/or `ingest_pdf.py`
- Standard output JSONL schema:
  - `doc_id`, `slide_id`, `slide_text`, `notes_text` (if any)
  - `title`, `n_slides`, `source_path`, `lang`, `hash`
- A small committed sample in `data/processed/sample.jsonl` (5–20 slides)

### Stage Gate (must pass)
- `pptcopilot ingest path/to/file.pptx -o data/processed/sample.jsonl` produces JSONL
- The sample file validates against schema
- Unit test: ingestion returns non-empty `slide_text` for a known sample

### Stage Review
- Are you preserving slide order reliably?
- Do you have stable `doc_id/slide_id` and content hashing?
- Is the output format easy for later retrieval + eval to consume?

---

# Stage 3 — Baseline Summarization (No Retrieval Yet)
### Goal
Generate a usable summary from slide text with a simple baseline.

### Deliverables
- `summarize/baseline.py` that produces:
  - slide-level bullets (optional)
  - document-level summary (required)
- `pptcopilot summarize data/processed/sample.jsonl --model <baseline>` outputs summary JSON

### Recommended baseline options
- If you have GPU: small instruction model (e.g., Phi/Llama small)
- If not: prompt a remote LLM (only if allowed)
- Keep the interface model-agnostic

### Stage Gate
- On the sample deck, the summary runs end-to-end with:
  - output saved to `reports/summaries/sample_summary.json`
  - runtime recorded (even rough)

### Stage Review
- Does the summary follow a consistent style rubric?
- Are failures handled gracefully (empty slides, weird formatting)?
- Is output deterministic enough for regression testing (seed, temperature)?

---

# Stage 4 — Retrieval (RAG for Slide Grounding)
### Goal
Add retrieval to ground Q&A and reduce hallucinations.

### Deliverables
- `retrieval/embed.py` + `index_faiss.py` + `retrieve.py`
- Chunking strategy (`io/chunking.py`) for slide text
- `qa/answer.py` that:
  - retrieves top-k chunks
  - answers with citations (slide_id references)

### Stage Gate
- `pptcopilot index data/processed/sample.jsonl` builds an index
- `pptcopilot qa --question "..."` returns:
  - an answer
  - cited slide_ids
- Unit test: retrieval returns expected slide_id for a known query

### Stage Review
- Are chunks too large/small?
- Are citations stable and meaningful?
- Do you log retrieved context for debugging?

---

# Stage 5 — SPOCK-lite Evaluation Harness (Scenario-Based)
### Goal
Build the evaluation system that lets you iterate like a product team.

### Deliverables
- Scenario format in `src/pptcopilot/eval/scenarios/`:
  - Each scenario includes:
    - input reference (deck/sample)
    - task type (summary / QA)
    - rubric (what “pass” means)
    - expected key points or acceptable answers
- `eval/harness.py` runs:
  - selected scenarios
  - multiple models (model swap)
  - produces a report JSON + markdown summary

### Metrics (start simple)
- For summaries: coverage of required key points (string match + semantic match)
- For Q&A: exact/semantic match + citation correctness
- Optional: LLM-as-judge module behind a flag

### Stage Gate
- `pptcopilot eval run --suite smoke` runs in <5 minutes on sample
- Generates:
  - `reports/eval/latest_report.json`
  - `reports/eval/latest_report.md`
- At least 5 scenarios exist (mix summary + QA)

### Stage Review
- Are scenarios realistic and “Copilot-like”?
- Can you easily add a new scenario in <10 minutes?
- Does the report clearly show regressions between runs?

---

# Stage 6 — Fine-tuning SLM (LoRA/QLoRA) + Reproducibility
### Goal
Demonstrate that you can post-train a small model for slide summarization style.

### Deliverables
- A training script (or notebook, but script preferred) in `src/pptcopilot/summarize/`
- LoRA/QLoRA config logged and saved
- Training/eval curves saved to `reports/finetune/`
- A finetuned adapter artifact (or instructions to reproduce)

### Training data options
- Public paper–slides pairs (e.g., SciDuet/D2S; DOC2PPT) OR
- Self-constructed small dataset from a handful of decks with human-written summaries

### Stage Gate
- You can run:
  - `pptcopilot finetune --config configs/finetune_small.yaml`
- After finetune, the eval harness shows improvement on at least one metric **without harming** another major metric (or explain trade-off)
- Reproduction: same command re-creates near-identical results (within tolerance)

### Stage Review
- Are you overfitting to a tiny dataset? (check on a held-out deck)
- Is the improvement measurable in scenario reports?
- Are training artifacts properly tracked (config, seed, dataset hash)?

---

# Stage 7 — Latency/Cost Benchmarking (p50/p95 + trade-offs)
### Goal
Quantify quality vs latency vs cost, and show you can optimize the system.

### Deliverables
- `bench/latency.py` to measure p50/p95 and throughput
- `bench/cost.py` with explicit assumptions for rough cost estimation
- Compare at least 2 model/runtime variants
- Save machine-readable reports and a human-readable summary

### Stage Gate
- Benchmark commands run and output JSON reports
- At least two variants are compared
- p95 is reported (not only mean)

### Stage Review
- Are settings configurable (warmup, iterations, batch size)?
- Do you present clear quality/latency/cost trade-offs?
- Are assumptions documented and reproducible?

---

# Stage 8 — Minimal Production Demo (CLI + FastAPI + CI)
### Goal
Ship a production-ish demo with CLI flow, optional API, and CI automation.

### Deliverables
- End-to-end CLI flow: ingest → index → summarize → qa → eval → bench
- Optional FastAPI app endpoints for summarize/qa/eval
- CI workflow for tests and scheduled smoke evals
- README quickstart that a new user can run in 5–10 minutes

### Stage Gate
- New user can execute full smoke flow and inspect outputs
- CI passes on PRs and scheduled smoke job runs
- Documentation is portfolio-ready

### Stage Review
- Are failure messages actionable?
- Are artifacts/logs available for debugging?
- Is the demo easy to reproduce end-to-end?
