# Jira Baseline Analytics

Establishes human work baselines by **type x size x area** buckets from Jira project data, enabling future comparison against AI-run projects.

## Quick Start

```bash
python main.py analyze --project PAY --tickets 50 --output ./out
python main.py inspect-ticket --ticket PAY-5
python main.py validate-config --config project_rules.yaml
python main.py analyze --project PAY --since 2025-01-01 --output ./out --csv
```

## Outputs

- `tickets_normalized.jsonl` — per-ticket canonical records
- `bucket_baselines.json` — per-bucket metrics
- `ranked_slow_buckets.json` — buckets sorted slowest-first
- `summary.json` — exclusion breakdown, data quality, recommendations

## Tests

```bash
python -m unittest discover -s tests -v   # 120 tests
```
