# RAVEL 20-Case Benchmark Evaluation & Governance Scorecard

## Accuracy & Policy Governance Summary

- **Ground-Truth Verdict Accuracy**: **100.0%** (20/20 cases aligned with exam answer key)
- **Policy Conformity Rate**: **100.0%** (100% adherence to Rules R1–R8)
- **Pattern Consistency Rate**: **100.0%** (Zero fraud cases with pattern none; zero false patterns on legit cases)
- **Graph Lineage Completeness**: **100.0%** (100% of claims verified with canonical graph paths)

**Cases Evaluated**: 20  
**Total Exposure Identified**: $2,996.56 USD  
**SARs Filed**: 9  
**Average Latency**: 0.38s / case  
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
| `none` | 4 |
| `card_not_present_fraud` | 9 |
| `account_takeover` | 6 |
| `card_not_present_new_device` | 1 |

## Case-by-Case Breakdown

| Case ID | Verdict | Pattern | Probability | Exposure | SAR Filed | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HHG-001` | `legitimate` | `none` | 0.15 | $0.00 | No | 0.19s |
| `HHG-002` | `uncertain` | `card_not_present_fraud` | 0.30 | $0.00 | No | 0.98s |
| `HHG-003` | `fraud` | `card_not_present_fraud` | 0.94 | $49.00 | Yes | 0.57s |
| `HHG-004` | `fraud` | `card_not_present_fraud` | 0.94 | $128.33 | Yes | 0.48s |
| `HHG-005` | `uncertain` | `account_takeover` | 0.75 | $100.07 | No | 0.1s |
| `HHG-006` | `fraud` | `card_not_present_new_device` | 0.95 | $1,906.07 | Yes | 0.13s |
| `HHG-007` | `legitimate` | `none` | 0.15 | $0.00 | No | 0.39s |
| `HHG-008` | `fraud` | `card_not_present_fraud` | 0.94 | $55.68 | Yes | 0.46s |
| `HHG-009` | `fraud` | `card_not_present_fraud` | 0.94 | $30.02 | Yes | 0.22s |
| `HHG-010` | `uncertain` | `card_not_present_fraud` | 0.30 | $0.00 | No | 0.09s |
| `HHG-011` | `fraud` | `card_not_present_fraud` | 0.94 | $131.30 | Yes | 0.57s |
| `HHG-012` | `legitimate` | `none` | 0.15 | $0.00 | No | 0.38s |
| `HHG-013` | `uncertain` | `account_takeover` | 0.75 | $197.38 | No | 0.23s |
| `HHG-014` | `fraud` | `account_takeover` | 0.90 | $74.96 | Yes | 0.07s |
| `HHG-015` | `uncertain` | `card_not_present_fraud` | 0.30 | $0.00 | No | 0.27s |
| `HHG-016` | `fraud` | `account_takeover` | 0.94 | $59.67 | Yes | 0.42s |
| `HHG-017` | `legitimate` | `none` | 0.05 | $0.00 | No | 0.46s |
| `HHG-018` | `fraud` | `card_not_present_fraud` | 0.94 | $39.08 | Yes | 1.17s |
| `HHG-019` | `uncertain` | `account_takeover` | 0.75 | $99.92 | No | 0.23s |
| `HHG-020` | `uncertain` | `account_takeover` | 0.75 | $125.08 | No | 0.12s |