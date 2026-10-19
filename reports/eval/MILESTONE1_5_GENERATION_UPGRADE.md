# Milestone 1.5 Generation Upgrade

Date: 2026-10-19

## Decision

Milestone 1.5 passes its quality target without changing retrieval or benchmark data.
Dense Recall@1 remains 1.00. The best CI-sized local generator,
`deepset/roberta-base-squad2`, reaches 0.80 Answer Accuracy with Dense top-5 and 0.90
with Dense top-1 or oracle evidence. The original FLAN-T5-small result was 0.50 with
Dense top-5.

The experiment also rejects a simple "larger instruct model is better" hypothesis:
FLAN-T5-base and Qwen2.5-0.5B-Instruct both plateaued at 0.70 with top-1/oracle
evidence, and stricter span prompts made several results worse. All negative runs are
retained below.

## Frozen protocol

No rows, labels, questions, or retrieval settings were changed.

- corpus: `data/eval/milestone1_corpus.jsonl`
- corpus SHA-256: `82f8942c01f0e0c37e0e734eeaf2cdadf820522cf6fe4051149380ac63cdaf77`
- held-out data: `data/eval/milestone1_qa.jsonl`
- held-out SHA-256: `4eea99dca6c5e78afab678f848a12be66c6680245e48c5accc016f6f93c3c9d6`
- queries: 10
- retriever: Dense + FAISS
- embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- retrieval depth: 10
- production-style generation context: Dense top-5
- ablations: Dense top-1 and oracle evidence

The benchmark checks these two input digests and the embedding model before running.
It builds Dense retrieval once and queries each held-out question once. Every generator
then receives those same ranked hits. Oracle evidence is constructed from the expected
slide IDs only after retrieval metrics have been recorded.

## Final measured result

Artifact: `reports/eval/milestone1_5_generation.json`

Artifact file SHA-256:
`81922928e8caba311f48dbb90dfb2dd0aaaf1d4a30af582a3ab8f9b9f9c42413`

| Generator | Parameters | Context | Recall@1 | MRR | Answer Accuracy | Citation Recall |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| FLAN-T5-small | 76,961,152 | Dense top-5 | 1.00 | 1.00 | 0.50 | 0.50 |
| FLAN-T5-small | 76,961,152 | Dense top-1 | 1.00 | 1.00 | 0.70 | 0.90 |
| FLAN-T5-small | 76,961,152 | Oracle | 1.00 | 1.00 | 0.70 | 0.90 |
| FLAN-T5-base | 247,577,856 | Dense top-5 | 1.00 | 1.00 | 0.50 | 0.80 |
| FLAN-T5-base | 247,577,856 | Dense top-1 | 1.00 | 1.00 | 0.70 | 0.90 |
| FLAN-T5-base | 247,577,856 | Oracle | 1.00 | 1.00 | 0.70 | 0.90 |
| **RoBERTa extractive QA** | **124,056,578** | **Dense top-5** | **1.00** | **1.00** | **0.80** | **0.90** |
| **RoBERTa extractive QA** | **124,056,578** | **Dense top-1** | **1.00** | **1.00** | **0.90** | **1.00** |
| **RoBERTa extractive QA** | **124,056,578** | **Oracle** | **1.00** | **1.00** | **0.90** | **1.00** |

Resolved model revisions recorded in the JSON artifact:

- `google/flan-t5-small`: `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab`
- `google/flan-t5-base`: `7bcac572ce56db69c1ea7c8af255c5d7c9672fc2`
- `deepset/roberta-base-squad2`: `adc3b06f79f797d1c575d5479d6f5efe54a9e3b4`

## Negative results retained

### Round 1: larger seq2seq model

Artifact: `milestone1_5_generation_round1.json`

SHA-256: `206284de87d2370c17c2ea9e6a54b3f9498878a44343daef87afb578e2961947`

| Generator | Dense top-5 | Dense top-1 | Oracle |
| --- | ---: | ---: | ---: |
| FLAN-T5-small | 0.50 | 0.70 | 0.70 |
| FLAN-T5-base | 0.50 | 0.70 | 0.70 |

FLAN-T5-base added 170.6M parameters but no Answer Accuracy. Its failures included
returning `year over year`, `p95`, or `INSUFFICIENT_CONTEXT` even when the correct
evidence was the only context.

### Round 2: stronger causal instruct model

Artifact: `milestone1_5_qwen_candidate.json`

SHA-256: `c1753a8628513eb29c12e6178b113e6ab49b7c7e7d779fed8eafd0dc13484eb5`

| Generator | Dense top-5 | Dense top-1 | Oracle |
| --- | ---: | ---: | ---: |
| Qwen2.5-0.5B-Instruct | 0.50 | 0.70 | 0.70 |

The 494,032,768-parameter model was also slower locally. It hallucinated `16.5%` for
an evidence sentence containing `18.7 percent`, shortened `SOC 2 Type II` to `SOC 2`,
and returned `strong` instead of the 112 percent retention metric.

### Round 3: exact-span prompt contract

Artifact: `milestone1_5_span_candidate.json`

SHA-256: `804416dc285c51eeacbb14fe4cafacc61ef0401533ed696d7bf28ffe711309a9`

| Generator | Dense top-5 | Dense top-1 | Oracle |
| --- | ---: | ---: | ---: |
| FLAN-T5-base + exact-span prompt | 0.60 | 0.50 | 0.50 |
| Qwen2.5-0.5B + exact-span prompt | 0.40 | 0.40 | 0.40 |

The stricter prompt often copied a related noun phrase (`Operating Margin`, `EMEA`,
or `Serving Latency`) rather than the value requested by the question. This is a
negative prompt ablation, not the selected implementation.

### Round 4: task-specific extractive QA

Initial candidate artifact: `milestone1_5_qa_candidate.json`

SHA-256: `dc9e6273737ee185f3d9116d046b4afa47621f73a06e8158d55731b328adaccd`

This candidate reached 0.80 / 0.90 / 0.90 Answer Accuracy. It also revealed that the
citation tokenizer treated trailing sentence punctuation as part of a token, so
`seconds` did not overlap `seconds.`. The tokenizer fix has a dedicated regression
test; the final artifact records corrected top-1/oracle Citation Recall of 1.00.

## Error attribution

Retrieval is not responsible for any final error: all 10 expected slides are at Dense
rank 1, and every failure occurs with the expected slide present in the generation
context.

The selected generator has two top-5 errors:

1. `q03` returns `strong` instead of `112 percent`. This also fails with top-1 and
   oracle evidence, so it is a semantic-intent generation failure.
2. `q08` returns `health checks` from the rank-2 distractor instead of `Recall@5` from
   the rank-1 evidence. It becomes correct with top-1/oracle evidence, so it is a
   multi-context distractor failure.

This explains the measured ceiling cleanly: restricting generation to the already
perfect Dense top-1 removes one error (0.80 to 0.90), while the remaining question
requires better semantic interpretation or a reranker trained for the requested value.

## CI and artifact integrity

The real-RAG workflow now:

1. runs deterministic regression tests;
2. runs the original Dense/FAISS integration and Milestone 1 benchmark;
3. runs the three-model, three-context Milestone 1.5 benchmark;
4. writes a SHA-256 sidecar;
5. uploads both files as `milestone1-5-generation-benchmark` and records the GitHub
   artifact digest in the workflow summary.

The workflow timeout is 40 minutes. The selected QA model is smaller than
FLAN-T5-base and Qwen2.5-0.5B, and local generation after model load completed in
3.19 seconds for top-5 plus less than one second each for top-1 and oracle.

## Next step

Do not change retrieval on this benchmark. The best next experiment is a generation
reranker or intent-aware answer selector aimed at `q03`, validated first against the
same frozen oracle condition. Broader claims should wait for the planned real-PPTX
scale benchmark because this controlled set contains only 10 answerable questions.
