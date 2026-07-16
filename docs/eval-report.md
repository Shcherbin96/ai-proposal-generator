# Live Eval Report

- Date: 2026-07-16
- Model: google/gemini-2.5-flash-lite
- Endpoint: https://openrouter.ai/api/v1
- Temperature: 0.4
- JSON mode: True
- Reps per golden file: 3
- Max-repairs configs in this report: 0, 1

> Operational note: this run was executed against google/gemini-2.5-flash-lite via OpenRouter rather than Google's own endpoint — Google AI Studio's free tier caps this model at 20 requests/day, which cannot fit a 30-call eval; the model itself is identical.

## max_repairs = 0

### en-office-4.yaml

Runs: 3 — ok: 3, repaired: 0, failed: 0 (avg latency 1.73s)

| Check | Pass rate |
|---|---|
| language_match | 3/3 |
| length_bounds | 3/3 |
| no_invented_numbers | 3/3 |
| no_markdown_artifacts | 3/3 |

### ru-bathroom-5.yaml

Runs: 3 — ok: 2, repaired: 0, failed: 1 (avg latency 2.18s)

| Check | Pass rate |
|---|---|
| language_match | 2/2 |
| length_bounds | 2/2 |
| no_invented_numbers | 2/2 |
| no_markdown_artifacts | 2/2 |

### ru-kitchen-1.yaml

Runs: 3 — ok: 3, repaired: 0, failed: 0 (avg latency 1.21s)

| Check | Pass rate |
|---|---|
| language_match | 3/3 |
| length_bounds | 3/3 |
| no_invented_numbers | 3/3 |
| no_markdown_artifacts | 3/3 |

### ru-renovation-20.yaml

Runs: 3 — ok: 3, repaired: 0, failed: 0 (avg latency 4.10s)

| Check | Pass rate |
|---|---|
| language_match | 3/3 |
| length_bounds | 3/3 |
| no_invented_numbers | 3/3 |
| no_markdown_artifacts | 3/3 |

### ru-specs-heavy-6.yaml

Runs: 3 — ok: 2, repaired: 0, failed: 1 (avg latency 1.86s)

| Check | Pass rate |
|---|---|
| language_match | 2/2 |
| length_bounds | 2/2 |
| no_invented_numbers | 2/2 |
| no_markdown_artifacts | 2/2 |

**Subtotal (max_repairs=0)**: 15 runs — ok 13, repaired 0, failed 2

## max_repairs = 1

### en-office-4.yaml

Runs: 3 — ok: 2, repaired: 0, failed: 1 (avg latency 1.48s)

| Check | Pass rate |
|---|---|
| language_match | 2/2 |
| length_bounds | 2/2 |
| no_invented_numbers | 2/2 |
| no_markdown_artifacts | 2/2 |

### ru-bathroom-5.yaml

Runs: 3 — ok: 3, repaired: 0, failed: 0 (avg latency 2.08s)

| Check | Pass rate |
|---|---|
| language_match | 3/3 |
| length_bounds | 3/3 |
| no_invented_numbers | 3/3 |
| no_markdown_artifacts | 3/3 |

### ru-kitchen-1.yaml

Runs: 3 — ok: 3, repaired: 0, failed: 0 (avg latency 1.16s)

| Check | Pass rate |
|---|---|
| language_match | 3/3 |
| length_bounds | 3/3 |
| no_invented_numbers | 3/3 |
| no_markdown_artifacts | 3/3 |

### ru-renovation-20.yaml

Runs: 3 — ok: 2, repaired: 1, failed: 0 (avg latency 4.57s)

| Check | Pass rate |
|---|---|
| language_match | 3/3 |
| length_bounds | 3/3 |
| no_invented_numbers | 3/3 |
| no_markdown_artifacts | 3/3 |

### ru-specs-heavy-6.yaml

Runs: 3 — ok: 3, repaired: 0, failed: 0 (avg latency 2.10s)

| Check | Pass rate |
|---|---|
| language_match | 3/3 |
| length_bounds | 3/3 |
| no_invented_numbers | 3/3 |
| no_markdown_artifacts | 3/3 |

**Subtotal (max_repairs=1)**: 15 runs — ok 13, repaired 1, failed 1

## Totals (all configs combined)

- Total runs: 30
- Contract ok: 26
- Contract repaired: 1
- Contract failed: 3
- language_match: 27/27 passed
- length_bounds: 27/27 passed
- no_invented_numbers: 27/27 passed
- no_markdown_artifacts: 27/27 passed
