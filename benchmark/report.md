# RAVEL 20-Case Execution & Consistency Report

## Internal Consistency Summary

- **Answer-key accuracy**: not reported; the challenge answer key is unavailable.
- **Policy-Output Consistency**: **100.0%**
- **Verdict/Pattern Consistency**: **100.0%**
- **Evidence Reference Coverage**: **100.0%** (claims include a source reference or explanatory path; this does not assert that every path is a stored graph edge)

**Cases Evaluated**: 20
**Total Exposure Identified**: $4,888.89 USD
**SARs Filed**: 7
**Average Latency**: 1.09s / case
**Average Graph Queries / Case**: 14.0

## Verdicts Distribution

| Verdict | Count | Share |
| :--- | :--- | :--- |
| `uncertain` | 10 | 50.0% |
| `fraud` | 9 | 45.0% |
| `legitimate` | 1 | 5.0% |

## Patterns Identified

| Fraud Pattern | Cases |
| :--- | :--- |
| `none` | 4 |
| `card_not_present_fraud` | 9 |
| `account_takeover` | 6 |
| `card_not_present_new_device` | 1 |

## Case-by-Case Breakdown

| Case ID | Verdict | Pattern | Probability | Exposure | SAR Filed | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HHG-001` | `uncertain` | `none` | 0.26 | $0.00 | No | 0.71s |
| `HHG-002` | `uncertain` | `card_not_present_fraud` | 0.50 | $292.36 | No | 1.34s |
| `HHG-003` | `fraud` | `card_not_present_fraud` | 0.93 | $49.00 | No | 0.53s |
| `HHG-004` | `fraud` | `card_not_present_fraud` | 0.94 | $128.33 | Yes | 1.83s |
| `HHG-005` | `uncertain` | `account_takeover` | 0.80 | $100.07 | No | 0.42s |
| `HHG-006` | `fraud` | `card_not_present_new_device` | 0.95 | $1,906.07 | Yes | 0.95s |
| `HHG-007` | `uncertain` | `none` | 0.34 | $0.00 | No | 0.84s |
| `HHG-008` | `fraud` | `card_not_present_fraud` | 0.94 | $55.68 | Yes | 1.83s |
| `HHG-009` | `fraud` | `card_not_present_fraud` | 0.94 | $30.02 | Yes | 1.3s |
| `HHG-010` | `uncertain` | `card_not_present_fraud` | 0.50 | $1,000.03 | No | 0.62s |
| `HHG-011` | `fraud` | `card_not_present_fraud` | 0.94 | $131.30 | Yes | 2.18s |
| `HHG-012` | `uncertain` | `none` | 0.24 | $0.00 | No | 0.49s |
| `HHG-013` | `uncertain` | `account_takeover` | 0.81 | $197.38 | No | 1.16s |
| `HHG-014` | `fraud` | `account_takeover` | 0.92 | $74.96 | Yes | 0.6s |
| `HHG-015` | `uncertain` | `card_not_present_fraud` | 0.50 | $599.94 | No | 1.57s |
| `HHG-016` | `fraud` | `account_takeover` | 0.94 | $59.67 | Yes | 1.74s |
| `HHG-017` | `legitimate` | `none` | 0.05 | $0.00 | No | 1.28s |
| `HHG-018` | `fraud` | `card_not_present_fraud` | 0.93 | $39.08 | No | 1.02s |
| `HHG-019` | `uncertain` | `account_takeover` | 0.82 | $99.92 | No | 0.99s |
| `HHG-020` | `uncertain` | `account_takeover` | 0.79 | $125.08 | No | 0.47s |