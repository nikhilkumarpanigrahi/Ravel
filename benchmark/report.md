# RAVEL 20-Case Execution & Consistency Report

## Internal Consistency Summary

- **Answer-key accuracy**: not reported; the challenge answer key is unavailable.
- **Policy-Output Consistency**: **100.0%**
- **Verdict/Pattern Consistency**: **100.0%**
- **Evidence Reference Coverage**: **100.0%** (claims include a source reference or explanatory path; this does not assert that every path is a stored graph edge)

**Cases Evaluated**: 20
**Total Exposure Identified**: $4,727.17 USD
**SARs Filed**: 6
**Average Latency**: 26.29s / case
**Average Graph Queries / Case**: 14.0

## Verdicts Distribution

| Verdict | Count | Share |
| :--- | :--- | :--- |
| `uncertain` | 11 | 55.0% |
| `fraud` | 8 | 40.0% |
| `legitimate` | 1 | 5.0% |

## Patterns Identified

| Fraud Pattern | Cases |
| :--- | :--- |
| `none` | 4 |
| `card_not_present_fraud` | 10 |
| `account_takeover` | 5 |
| `card_not_present_new_device` | 1 |

## Case-by-Case Breakdown

| Case ID | Verdict | Pattern | Probability | Exposure | SAR Filed | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HHG-001` | `uncertain` | `none` | 0.26 | $0.00 | No | 3.92s |
| `HHG-002` | `uncertain` | `card_not_present_fraud` | 0.50 | $292.36 | No | 5.78s |
| `HHG-003` | `fraud` | `card_not_present_fraud` | 0.93 | $49.00 | No | 3.63s |
| `HHG-004` | `fraud` | `card_not_present_fraud` | 0.94 | $128.33 | Yes | 7.64s |
| `HHG-005` | `uncertain` | `account_takeover` | 0.80 | $100.07 | No | 8.37s |
| `HHG-006` | `fraud` | `card_not_present_new_device` | 0.94 | $1,906.07 | Yes | 2.01s |
| `HHG-007` | `uncertain` | `none` | 0.34 | $0.00 | No | 6.37s |
| `HHG-008` | `fraud` | `card_not_present_fraud` | 0.94 | $55.68 | Yes | 11.38s |
| `HHG-009` | `fraud` | `card_not_present_fraud` | 0.94 | $30.02 | Yes | 5.33s |
| `HHG-010` | `uncertain` | `card_not_present_fraud` | 0.50 | $1,000.03 | No | 7.4s |
| `HHG-011` | `fraud` | `card_not_present_fraud` | 0.94 | $131.30 | Yes | 10.52s |
| `HHG-012` | `uncertain` | `none` | 0.24 | $0.00 | No | 2.22s |
| `HHG-013` | `uncertain` | `card_not_present_fraud` | 0.43 | $35.66 | No | 4.0s |
| `HHG-014` | `uncertain` | `account_takeover` | 0.83 | $74.96 | No | 42.3s |
| `HHG-015` | `uncertain` | `card_not_present_fraud` | 0.50 | $599.94 | No | 68.86s |
| `HHG-016` | `fraud` | `account_takeover` | 0.94 | $59.67 | Yes | 60.46s |
| `HHG-017` | `legitimate` | `none` | 0.05 | $0.00 | No | 52.04s |
| `HHG-018` | `fraud` | `card_not_present_fraud` | 0.93 | $39.08 | No | 104.36s |
| `HHG-019` | `uncertain` | `account_takeover` | 0.82 | $99.92 | No | 118.84s |
| `HHG-020` | `uncertain` | `account_takeover` | 0.79 | $125.08 | No | 0.46s |