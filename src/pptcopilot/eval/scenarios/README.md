# Scenario Format

Each scenario is a JSON file named `sXXX_<name>.json`.

Required schema:

```json
{
  "scenario_id": "s001_summary_core_topics",
  "name": "Summary covers core topics",
  "task_type": "summary",
  "suites": ["smoke"],
  "input": {
    "path": "data/processed/sample.jsonl"
  },
  "rubric": {
    "min_keypoint_coverage": 0.6
  },
  "expected": {
    "required_key_points": ["Data Pipeline", "Evaluation Harness"]
  }
}
```

For QA scenarios:

```json
{
  "scenario_id": "s004_qa_eval_slide",
  "name": "QA finds evaluation slide",
  "task_type": "qa",
  "suites": ["smoke"],
  "input": {
    "path": "data/processed/sample.jsonl",
    "question": "Which slide discusses evaluation harness and scenarios?",
    "top_k": 3
  },
  "rubric": {
    "min_citation_recall": 0.5
  },
  "expected": {
    "acceptable_answers": ["evaluation harness", "scenario"],
    "expected_slide_ids": ["fdb513bf99588c7e_s005"]
  }
}
```

Notes:
- `suites` controls inclusion when running `pptcopilot eval run --suite <suite>`.
- Summary scoring is keyword coverage over `required_key_points`.
- QA scoring uses answer match + citation recall.
