# Milestone 1 Experiment Report

Date: 2026-10-19

## Goal

Replace the retrieval/QA scaffold with a real end-to-end RAG path and measure whether dense semantic retrieval improves over the deterministic Hash baseline on a frozen held-out QA set.

## Experimental setup

- Corpus: 12 controlled slide records
- Held-out set: 10 semantic-paraphrase QA queries
- Hash baseline: 256-dimensional deterministic hash embeddings + FAISS inner-product search
- Dense system: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, normalized) + FAISS inner-product search
- Generator: `google/flan-t5-small`
- Retrieval metrics: Recall@1, Recall@5, Recall@10, MRR
- End-to-end metrics: Answer Accuracy, Citation Recall
- Chunk size: 40 tokens
- Retrieval evaluation depth: 10
- Generation top-k: 5

The test questions intentionally avoid copying source-slide wording. Example: the source says "Cash and cash equivalents totaled 74 million dollars" while the query asks "How much liquid money was on hand at the end of the quarter?"

## Experiment A — baseline real RAG

GitHub Actions run: `39324787023`, successful attempt 2.

Artifact:
- name: `milestone1-real-rag-benchmark`
- artifact id: `12221728707`
- digest: `sha256:0bbc4f912415a15f7478361cbdca694d5b14b7e50d30aa73ff77a258b7118861`

| System | Recall@1 | Recall@5 | Recall@10 | MRR | Answer Accuracy | Citation Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hash + FAISS + FLAN-T5-small | 0.40 | 0.90 | 1.00 | 0.60 | 0.40 | 0.40 |
| Dense + FAISS + FLAN-T5-small | **1.00** | **1.00** | **1.00** | **1.00** | **0.50** | **0.50** |

### Interpretation

Dense semantic retrieval is the clear winner. It places the relevant slide at rank 1 for all 10 held-out queries, while the Hash baseline reaches only 40% Recall@1 and 0.60 MRR.

The remaining bottleneck is generation, not retrieval. Even when Dense retrieval returns the correct slide at rank 1 on every query, FLAN-T5-small answers only 50% of the benchmark correctly. Several failures are caused by the small generator copying citation labels such as `[evaldeck_s004]` instead of extracting the requested value.

This means the project now has evidence for a useful architectural conclusion:

> Dense retrieval solved the evidence-selection problem on this controlled semantic benchmark; answer generation is now the dominant quality bottleneck.

## Experiment B — generation-context ablation

Change:
- removed slide IDs from generation context
- reduced generation context from top-5 to top-3
- kept corpus, held-out questions, embedding model, FAISS index, and FLAN-T5-small unchanged

GitHub Actions run: `39324787023`, successful attempt 3.

Artifact:
- name: `milestone1-real-rag-benchmark`
- artifact id: `12222550477`
- digest: `sha256:cd3d51fbe110988486eccf361f7a4a8b29f8bb1b8d606776bbedbce725be202a`

| System | Recall@1 | Recall@5 | Recall@10 | MRR | Answer Accuracy | Citation Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hash + modified generation context | 0.40 | 0.90 | 1.00 | 0.60 | 0.10 | 0.40 |
| Dense + modified generation context | 1.00 | 1.00 | 1.00 | 1.00 | 0.10 | 0.30 |

The ablation made generation worse. The experiment is retained as a negative result rather than presented as an optimization. The branch was reverted to the higher-scoring Experiment A generation configuration.

## Additional fixes discovered during execution

The first workflow attempt exposed two reproducibility bugs:

1. CI assumed `data/processed/sample.jsonl` existed. A deterministic committed smoke sample was added.
2. The original chunker reconstructed text from normalized retrieval tokens, turning values such as `18.7%` into `18 7`. Chunk text now preserves original surface text, while embedding backends remain responsible for normalization.

After these fixes, regression tests, the real Dense/FAISS integration test, the benchmark, and artifact upload all completed successfully.

## Milestone 1 conclusion

Milestone 1 is complete as an evidence milestone:

- real embedding model: PASS
- real FAISS dense retrieval: PASS
- real local LLM generation: PASS
- independent frozen test set: PASS
- Hash vs Dense comparison: PASS
- Recall@1/5/10 and MRR: PASS
- Answer Accuracy and Citation Recall: PASS
- CI-reproducible benchmark artifact: PASS

The next quality step should focus on generation rather than more retrieval tuning. Recommended order:

1. replace FLAN-T5-small with a stronger instruct model while keeping the frozen benchmark unchanged;
2. evaluate retrieval-only vs generation-only error attribution;
3. add unanswerable questions and abstention accuracy;
4. only then expand to the P1 real-PPTX scale benchmark.
