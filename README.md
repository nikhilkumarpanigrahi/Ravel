# RAVEL — Autonomous Agentic Fraud Investigation Workstation

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com)
[![TigerGraph](https://img.shields.io/badge/TigerGraph-Savanna%20%7C%20CE-orange.svg)](https://www.tigergraph.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**RAVEL** is an enterprise forensic fraud investigation system designed for the **TigerGraph × Hacker House Goa 2026** challenge. It unites **graph relationship analytics (GSQL / pyTigerGraph)**, **deterministic policy governance (Rules R1–R10)**, **multi-hop GraphRAG context retrieval**, and an **interactive forensic workstation** into a production-grade autonomous agent.

---

## Key Highlights

- **14-State Investigation Machine**: Stateful lifecycle from alert intake (`TRIGGERED`) through graph traversal (`INVESTIGATING`), uncertainty calculation (`ASSESSING`), external customer inquiry simulation (`EVIDENCE_REQUESTED`), policy action routing (`POLICY_EVALUATION`), to defensible case record closure (`CASE_CLOSED`) and graph memory recording (`MEMORY_UPDATED`).
- **Deterministic Fraud Policy Engine**: Enforces Rules R1–R10 (verification before blocking on weak signals, customer denial/confirmation handling, card testing, shared origin detection, and approval routing across `auto`, `L1`, `L2`).
- **Regulatory Suspicious Activity Report (SAR) Generation**: Produces complete narrative filings detailing Who, What, When, Where, How, and Why suspicious, matching FinCEN standards.
- **Dual Graph Support**:
  - **Live TigerGraph Mode**: Savanna / CE connection via GSQL schema and loading jobs.
  - **High-Performance Mock Graph Mode**: SQLite WAL-backed graph adapter over all 590,742 transactions, 13,553 customers, 9,706 devices, and 5,565 closed cases for instant local execution and deterministic demonstrations.
- **Forensic Analyst Workstation**: Clean, financial-grade UI with canvas subgraph exploration, evidence ledger, state machine timeline, and approval actions.

---

## 20-Case Benchmark Summary

Executed deterministically on all 20 exam cases from `HHGOA_IEEE/case_pack.csv` using the local mock graph adapter:

| Metric | Result |
| :--- | :--- |
| **Cases Evaluated** | **20 / 20** |
| **Confirmed Fraud** | 9 cases |
| **Legitimate Cleared** | 4 cases |
| **Uncertain Escalated** | 7 cases |
| **SARs Recommended** | 9 simulated regulatory filings |
| **Total Exposure Identified** | **$2,996.56 USD** |
| **Average Latency** | **1.59 seconds / case** |
| **Average Graph Queries** | **14.0 queries / case** |

Detailed breakdown available in [`benchmark/report.md`](benchmark/report.md) and individual graded answer files in [`cases/`](cases/).

---

## Quick Start

### 1. Prerequisites & Environment Setup

```bash
# Clone the repository
git clone https://github.com/nikhilkumarpanigrahi/Ravel.git
cd Ravel

# Install dependencies with uv (or python virtual environment)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 2. Ingest Dataset

Normalize the 590,742 raw IEEE-CIS transactions, identities, and closed cases:

```bash
python -m ravel.interfaces.cli ingest --chunksize 200000
```
*Outputs generated in `data/level0/` (`transactions.csv`, `customers.csv`, `devices.csv`, `next_edges.csv`, etc.).*

### 3. Run Benchmark

Evaluate all 20 challenge cases and generate compliant answer files:

```bash
python -m ravel.interfaces.cli benchmark --out-dir cases/
```

### 4. Launch Forensic Workstation UI

Start the FastAPI server and open the browser workstation:

```bash
python -m ravel.interfaces.cli serve --port 8000
```
Open **http://127.0.0.1:8000** in your browser to inspect the interactive relationship graph, evidence ledger, timeline, and approve pending actions.

### 5. Inspect a Case File

```bash
python -m ravel.interfaces.cli show HHG-017
```

---

## Test Suite

Run pytest to verify the full suite (detectors, policy rules, graph adapters, workflow, and API routes):

```bash
pytest -v
```

Linting and code quality:
```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

---

## Repository Architecture

```
Ravel/
├── HHGOA_IEEE/                    # Raw challenge dataset & README
├── data/level0/                   # Normalized dataset & SQLite graph DB
├── cases/                         # 20 graded benchmark answer files (HHG-001 to HHG-020)
├── benchmark/                     # Benchmark results.json and report.md
├── src/ravel/
│   ├── application/
│   │   ├── benchmark_service.py   # 20-case benchmark orchestrator
│   │   ├── detectors.py           # 5 modular fraud pattern detectors
│   │   ├── graphrag.py            # GraphRAG multi-hop retrieval service
│   │   ├── policy_engine.py       # Fraud Policy (R1-R10) & SAR engine
│   │   └── workflow.py            # 14-state investigation state machine
│   ├── domain/                    # Aggregates: Case, SAR, Evidence, Policy, Trigger
│   ├── infrastructure/
│   │   ├── graph/                 # GraphAdapter (MockGraphAdapter & TigerGraphAdapter)
│   │   ├── ingestion/             # Streaming chunked data engineering pipeline
│   │   └── persistence.py         # SQLite persistence for investigation states & memory
│   └── interfaces/
│       ├── api.py                 # FastAPI REST API
│       ├── cli.py                 # CLI entrypoints (ingest, benchmark, serve, show)
│       └── static/index.html      # Forensic workstation single-page app
└── tests/                         # Comprehensive unit and integration test suite
```

---

## License

MIT License. Designed for TigerGraph Hacker House Goa 2026.
