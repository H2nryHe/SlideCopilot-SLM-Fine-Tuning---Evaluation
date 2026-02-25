# Benchmark Summary

- suite: `smoke`
- generated_at: `2026-02-25T10:54:48.080637+00:00`

## Latency And Throughput

| variant | summarize p50 (s) | summarize p95 (s) | summarize tok/s | qa p50 (s) | qa p95 (s) | qa tok/s |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.000099 | 0.000102 | 200028.128 | 0.000415 | 0.000429 | 85873.218 |
| fast | 0.000093 | 0.000784 | 57361.438 | 0.000419 | 0.001435 | 24832.089 |

## Cost Estimate (USD per 1k requests, p95 latency-based)

| variant | summarize | qa | blended |
|---|---:|---:|---:|
| baseline | 0.0001 | 0.0003 | 0.0002 |
| fast | 0.0006 | 0.0010 | 0.0008 |
