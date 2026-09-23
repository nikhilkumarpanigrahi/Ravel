# RAVEL 20-Case Benchmark Report

**Cases Evaluated**: 20  
**Total Exposure Identified**: $2,996.56 USD  
**SARs Filed**: 9  
**Average Latency**: 1.59s / case  
**Average Graph Queries / Case**: 14.0  

## Verdicts Distribution

| Verdict | Count | Share |
| :--- | :--- | :--- |
| `legitimate` | 4 | 20.0% |
| `uncertain` | 7 | 35.0% |
| `fraud` | 9 | 45.0% |

## Patterns Identified

| Fraud Pattern | Cases |
| :--- | :--- |
| `none` | 6 |
| `card_not_present_fraud` | 7 |
| `account_takeover` | 6 |
| `card_not_present_new_device` | 1 |

## Case-by-Case Breakdown

| Case ID | Verdict | Pattern | Probability | Exposure | SAR Filed | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HHG-001` | `legitimate` | `none` | 0.15 | $0.00 | No | 0.89s |
| `HHG-002` | `uncertain` | `card_not_present_fraud` | 0.30 | $0.00 | No | 1.13s |
| `HHG-003` | `fraud` | `none` | 0.98 | $49.00 | Yes | 2.66s |
| `HHG-004` | `fraud` | `card_not_present_fraud` | 0.98 | $128.33 | Yes | 1.24s |
| `HHG-005` | `uncertain` | `account_takeover` | 0.75 | $100.07 | No | 0.48s |
| `HHG-006` | `fraud` | `card_not_present_new_device` | 0.98 | $1,906.07 | Yes | 1.15s |
| `HHG-007` | `legitimate` | `none` | 0.15 | $0.00 | No | 5.08s |
| `HHG-008` | `fraud` | `card_not_present_fraud` | 0.98 | $55.68 | Yes | 3.16s |
| `HHG-009` | `fraud` | `none` | 0.98 | $30.02 | Yes | 1.34s |
| `HHG-010` | `uncertain` | `card_not_present_fraud` | 0.30 | $0.00 | No | 0.82s |
| `HHG-011` | `fraud` | `card_not_present_fraud` | 0.98 | $131.30 | Yes | 4.63s |
| `HHG-012` | `legitimate` | `none` | 0.15 | $0.00 | No | 0.77s |
| `HHG-013` | `uncertain` | `account_takeover` | 0.75 | $197.38 | No | 0.9s |
| `HHG-014` | `fraud` | `account_takeover` | 0.90 | $74.96 | Yes | 0.55s |
| `HHG-015` | `uncertain` | `card_not_present_fraud` | 0.30 | $0.00 | No | 1.13s |
| `HHG-016` | `fraud` | `account_takeover` | 0.98 | $59.67 | Yes | 1.15s |
| `HHG-017` | `legitimate` | `card_not_present_fraud` | 0.05 | $0.00 | No | 0.87s |
| `HHG-018` | `fraud` | `none` | 0.98 | $39.08 | Yes | 2.62s |
| `HHG-019` | `uncertain` | `account_takeover` | 0.75 | $99.92 | No | 0.86s |
| `HHG-020` | `uncertain` | `account_takeover` | 0.75 | $125.08 | No | 0.46s |