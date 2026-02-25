# Evaluation Report

- suite: `finetune`
- models: `mock, finetuned:artifacts/finetune/small_mock_peft_adapter`
- scenarios: `6`
- pass rate: `66.7%`
- duration_sec: `0.0065`

## Scenario Results

| model | scenario_id | task | pass | score |
|---|---|---:|---:|---:|
| mock | s101_summary_latency_cost_required | summary | FAIL | 0.000 |
| mock | s102_summary_all_sections | summary | FAIL | 0.833 |
| mock | s103_qa_eval_stability | qa | PASS | 1.000 |
| finetuned:artifacts/finetune/small_mock_peft_adapter | s101_summary_latency_cost_required | summary | PASS | 1.000 |
| finetuned:artifacts/finetune/small_mock_peft_adapter | s102_summary_all_sections | summary | PASS | 1.000 |
| finetuned:artifacts/finetune/small_mock_peft_adapter | s103_qa_eval_stability | qa | PASS | 1.000 |
