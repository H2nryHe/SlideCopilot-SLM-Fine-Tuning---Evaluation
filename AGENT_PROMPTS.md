# AGENT_PROMPTS.md — Stage-by-Stage Prompts for Building PPT Copilot

These prompts are designed for a coding agent (Cursor/Claude Code/GitHub Copilot Workspace/Code Interpreter-style agent).
Copy **one stage prompt at a time**. Do **not** start a new stage until the **Stage Gate** is PASS.

> Repo reference: `PROJECT_SPEC.md` is the source of truth for goals, structure, and gates.

---

## How to use these prompts (recommended workflow)
1) Create a new git branch for the stage: `stage-<N>-<short-name>`
2) Paste the corresponding prompt to your agent
3) Let the agent implement + run checks + produce artifacts
4) You personally verify the Stage Gate
5) Commit with a “Stage N Review” note (template in PROJECT_SPEC.md)

---

## Global Agent System Prompt (paste once at the start of your session)
**Prompt:**
You are a senior applied-science engineering agent working inside a Python repo called `ppt-copilot`.  
Your job is to implement the requested stage from `PROJECT_SPEC.md` with high code quality, reproducibility, and measurable outputs.  
Rules:
- Operate incrementally. Keep changes scoped to the stage.
- Prefer scripts over notebooks unless explicitly requested.
- Add/adjust tests for each stage.
- Update README only when the stage adds a user-facing command.
- After implementation, run the required commands and report outputs, paths, and results.
- If you are unsure about a requirement, make a reasonable assumption and document it in `reports/` or comments—do not block.
- Do not invent results; only report what you can run/verify.
Deliverables must match Stage Gate criteria. End your work with:
1) A checklist of completed deliverables  
2) Commands run + outputs produced  
3) Stage Gate PASS/FAIL with evidence  
4) Next-stage readiness notes

---

# Stage 1 — Bootstrap & Reproducibility Scaffold
**Prompt:**
Implement **Stage 1** from `PROJECT_SPEC.md` (Bootstrap & Reproducibility Scaffold).

Tasks:
- Create the repo skeleton and package layout under `src/pptcopilot/`
- Add `pyproject.toml` with dependencies and entrypoint so `pptcopilot --help` works
- Add pytest test runner and at least one trivial passing test
- Add `.gitignore` for data, caches, venv, artifacts
- Add `config.py` as a single source of truth for paths and defaults

Acceptance (Stage Gate):
- `python -m pip install -e .` works
- `pytest` passes
- `pptcopilot --help` prints usage

Output requirements:
- Show the exact commands you ran and their outputs.
- List created files and key design decisions.

---

# Stage 2 — Data Ingestion (PPTX/PDF → Slide Text + Metadata)
**Prompt:**
Implement **Stage 2** from `PROJECT_SPEC.md` (Data Ingestion).

Tasks:
- Implement `src/pptcopilot/io/ingest_pptx.py` (preferred) and optionally `ingest_pdf.py`
- Define a standard JSONL schema: `doc_id`, `slide_id`, `slide_text`, `notes_text`, `title`, `n_slides`, `source_path`, `lang`, `hash`
- Add CLI command: `pptcopilot ingest <path> -o <output.jsonl>`
- Add schema validation (lightweight) and one unit test for ingestion
- Produce a small sample output: `data/processed/sample.jsonl` (5–20 slides) using a local sample deck
  - If no sample deck exists, create a tiny synthetic PPTX generator script under `scripts/` to generate one

Acceptance (Stage Gate):
- Running `pptcopilot ingest path/to/file.pptx -o data/processed/sample.jsonl` produces valid JSONL
- Unit test verifies non-empty `slide_text`
- Sample validates against schema

Output requirements:
- Provide the schema (as markdown in code comments or `docs/schema.md`)
- Provide `data/processed/sample.jsonl` generation instructions

---

# Stage 3 — Baseline Summarization (No Retrieval Yet)
**Prompt:**
Implement **Stage 3** from `PROJECT_SPEC.md` (Baseline Summarization).

Tasks:
- Implement `src/pptcopilot/summarize/baseline.py` that takes JSONL slides and outputs:
  - document-level summary (required)
  - optional slide-level bullets
- Add CLI command: `pptcopilot summarize <jsonl> --model <baseline> -o <out.json>`
- Make the model interface pluggable:
  - Option A: local HF model (if available)
  - Option B: “mock summarizer” baseline (deterministic) for tests + smoke runs
- Save a run output to: `reports/summaries/sample_summary.json`

Acceptance (Stage Gate):
- Stage runs end-to-end on `data/processed/sample.jsonl`
- Output is saved to `reports/summaries/sample_summary.json`
- Runtime recorded in the output JSON metadata (even rough)

Output requirements:
- Document how to run locally without GPU (mock baseline)
- Ensure determinism for regression tests (seed, temperature=0, etc.)

---

# Stage 4 — Retrieval (RAG for Slide Grounding)
**Prompt:**
Implement **Stage 4** from `PROJECT_SPEC.md` (Retrieval + RAG Q&A with citations).

Tasks:
- Implement chunking in `src/pptcopilot/io/chunking.py`
- Implement embedding + FAISS indexing in `src/pptcopilot/retrieval/`
- Add CLI commands:
  - `pptcopilot index <jsonl> --index-dir <dir>`
  - `pptcopilot qa --index-dir <dir> --question "..." -o <out.json>`
- Implement `src/pptcopilot/qa/answer.py` to:
  - retrieve top-k chunks
  - answer using retrieved context
  - include citations (slide_id references) and store retrieved contexts for debug
- Add a unit test that a known query retrieves an expected slide_id (use a tiny controlled sample)

Acceptance (Stage Gate):
- Index builds successfully
- Q&A returns answer + cited slide_ids
- Retrieval unit test passes

Output requirements:
- Provide a “debug mode” that logs retrieved chunks
- Document chunk size/top-k defaults in `config.py`

---

# Stage 5 — SPOCK-lite Evaluation Harness (Scenario-Based)
**Prompt:**
Implement **Stage 5** from `PROJECT_SPEC.md` (SPOCK-lite evaluation harness).

Tasks:
- Define scenario JSON format in `src/pptcopilot/eval/scenarios/README.md`
- Create at least **5 scenarios** total:
  - mix of summary + QA
  - each scenario includes input reference, task type, rubric, expected key points/acceptable answers
- Implement `src/pptcopilot/eval/harness.py` to run:
  - a suite (e.g., `smoke`)
  - multiple model variants (model swap)
  - produce report JSON + markdown
- Add CLI:
  - `pptcopilot eval run --suite smoke --model <...> --outdir reports/eval/`
- Keep runtime under 5 minutes on sample (use mock baseline if needed)

Acceptance (Stage Gate):
- `pptcopilot eval run --suite smoke` runs in <5 minutes
- Produces `reports/eval/latest_report.json` and `reports/eval/latest_report.md`
- 5 scenarios exist and run

Output requirements:
- Report must clearly show pass/fail per scenario and an overall score
- Add a regression comparison helper (optional): compare two reports and highlight deltas

---

# Stage 6 — Fine-tuning SLM (LoRA/QLoRA) + Reproducibility
**Prompt:**
Implement **Stage 6** from `PROJECT_SPEC.md` (Fine-tuning + reproducibility).

Tasks:
- Implement training script `pptcopilot finetune --config configs/finetune_small.yaml`
- Use PEFT LoRA/QLoRA with a small HF model
- Log:
  - dataset hash / manifest
  - training config + seeds
  - evaluation metrics
- Save artifacts under `reports/finetune/` and model adapter under `artifacts/` (gitignored or via instructions)
- Integrate finetuned model into `pptcopilot summarize` as a selectable model variant
- Run SPOCK-lite eval before/after and show measurable improvement or documented trade-off

Acceptance (Stage Gate):
- Finetune command runs end-to-end
- Eval harness shows improvement on at least one metric without major regression elsewhere (or documented trade-off)
- Re-running with same config yields near-identical results (within tolerance)

Output requirements:
- Provide a reproducibility section in README or `reports/finetune/README.md`
- If compute is limited, provide a tiny “unit finetune” smoke config that runs quickly

---

# Stage 7 — Latency/Cost Benchmarking (p50/p95 + trade-offs)
**Prompt:**
Implement **Stage 7** from `PROJECT_SPEC.md` (Latency/Cost benchmarks).

Tasks:
- Implement `bench/latency.py` to measure:
  - p50/p95 end-to-end latency for summarize and QA
  - tokens/s where available
- Implement `bench/cost.py` for a simple cost estimate (document assumptions)
- Add CLI:
  - `pptcopilot bench latency --suite smoke --out reports/bench/latency.json`
  - `pptcopilot bench cost --in reports/bench/latency.json --out reports/bench/cost.json`
- Compare at least 2 variants and output a summary table/plot

Acceptance (Stage Gate):
- Benchmark commands run and output JSON reports
- At least two variants compared
- p95 is reported (not just mean)

Output requirements:
- Save a human-readable summary to `reports/bench/summary.md`
- Make benchmark settings configurable (iterations, warmup, batch)

---

# Stage 8 — Minimal Production Demo (CLI + FastAPI + CI)
**Prompt:**
Implement **Stage 8** from `PROJECT_SPEC.md` (Production-ish demo + CI).

Tasks:
- Ensure CLI commands exist and work: ingest, index, summarize, qa, eval, bench
- Add optional FastAPI app with endpoints:
  - `/summarize`, `/qa`, `/eval/run`
- Add GitHub Actions workflow:
  - runs tests on PR
  - nightly scheduled smoke eval
  - uploads eval reports as artifacts
- Improve README Quickstart so a recruiter can run in 5–10 minutes

Acceptance (Stage Gate):
- A new user can run ingest → index → summarize → qa → eval and see a report
- CI runs successfully (at least smoke suite)
- README is portfolio-ready (commands + example outputs)

Output requirements:
- Provide a demo GIF or terminal capture instructions
- Make sure failure messages are helpful and logged

---

## Optional: “Stage 0” Prompt — Repo audit / current-state check
**Prompt:**
Before implementing a new stage, audit the repo and report:
- Current directory tree
- Current commands available (`pptcopilot --help`)
- Current tests and their status
- Existing reports/artifacts
Then recommend the exact next steps to meet the next Stage Gate.
