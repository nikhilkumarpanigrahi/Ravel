# RAVEL — Autonomous Engineering Execution PRD

**Product:** RAVEL  
**Document:** Autonomous Coding-Agent Execution Contract  
**Purpose:** Give an autonomous coding agent enough authority, constraints, architecture, acceptance criteria, and verification rules to build RAVEL end-to-end with minimal human intervention.

---

# 1. Mission

You are the primary engineering owner of **RAVEL**, an agentic fraud investigation system for the TigerGraph HHGOA challenge.

Your job is not to create a mockup or partial prototype.

Your job is to inspect the repository and challenge dataset, design the implementation, write the code, integrate TigerGraph/GSQL/MCP/GraphRAG, build the agent workflow and UI, test everything, run the benchmark, diagnose failures, improve the implementation, and leave the repository in a reproducible state.

Do not wait for the human for ordinary engineering decisions.

Ask for clarification only when a decision genuinely requires unavailable information, credentials, destructive external action, or an ambiguous business requirement that cannot be resolved from the supplied challenge material.

---

# 2. Source of Truth

Before implementation:

1. Read the supplied challenge PDF.
2. Read the `HHGOA_IEEE` README.
3. Inspect every dataset file.
4. Inspect repository structure.
5. Inspect all existing configuration.
6. Identify available TigerGraph environment/configuration.
7. Preserve challenge terminology and constraints.
8. Build only claims supported by source data.

Do not silently invent columns, fraud labels, regulatory requirements, or benchmark answers.

---

# 3. Autonomous Execution Contract

The agent is authorized to:

- create files;
- create directories;
- refactor code;
- add dependencies;
- implement APIs;
- implement graph schema;
- write GSQL;
- implement ingestion;
- implement MCP tools;
- implement GraphRAG;
- implement case memory;
- implement policy engine;
- implement action adapters;
- implement frontend;
- write tests;
- run tests;
- run linters;
- run type checks;
- run benchmark;
- inspect failures;
- fix failures;
- improve architecture;
- improve performance;
- write documentation;
- prepare demo assets.

The agent must NOT:

- fabricate benchmark answers;
- hardcode benchmark case outputs;
- bypass policy;
- invent evidence;
- claim a test passed when it did not run;
- claim a benchmark score that was not measured;
- expose hidden chain-of-thought;
- embed credentials;
- delete important user data without explicit approval;
- replace TigerGraph with an unrelated database;
- replace graph investigation with a pure LLM response.

---

# 4. Autonomous Workflow

Execute this sequence.

```text
REPOSITORY DISCOVERY
        ↓
CHALLENGE/DATASET DISCOVERY
        ↓
DATA PROFILING
        ↓
DOMAIN MODEL
        ↓
ARCHITECTURE
        ↓
TIGERGRAPH SCHEMA
        ↓
INGESTION
        ↓
GSQL + GRAPH ALGORITHMS
        ↓
TIGERGRAPH MCP
        ↓
EVIDENCE MODEL
        ↓
INVESTIGATION STATE MACHINE
        ↓
AGENT TOOLS
        ↓
GRAPHRAG
        ↓
CASE MEMORY
        ↓
POLICY ENGINE
        ↓
NEXT BEST ACTION
        ↓
BACKEND API
        ↓
FRONTEND
        ↓
TESTING
        ↓
20-CASE BENCHMARK
        ↓
FAILURE ANALYSIS
        ↓
OPTIMIZATION
        ↓
REGRESSION
        ↓
DOCUMENTATION
        ↓
DEMO
        ↓
FINAL QUALITY GATE
```

---

# 5. Phase 0 — Repository Discovery

Before writing code, inspect:

```text
files
directories
package managers
build files
environment files
Docker files
existing services
existing frontend
existing tests
README
dataset locations
```

Produce an internal implementation map.

Do not unnecessarily rewrite existing useful code.

---

# 6. Phase 1 — Dataset Discovery

Inspect:

- README;
- filenames;
- row counts;
- schemas;
- null rates;
- duplicate rates;
- categorical values;
- numeric ranges;
- date ranges;
- relationships;
- historical cases;
- policy files;
- fraud-pattern definitions;
- regulatory references;
- benchmark cases.

Generate a local data dictionary.

Important:

> Never assume a column means something because its name looks obvious. Validate its meaning against the challenge README/source.

---

# 7. Phase 2 — Data Engineering

Implement a reproducible pipeline.

Required:

```text
Raw Data
  ↓
Validation
  ↓
Normalization
  ↓
Deduplication
  ↓
Entity Resolution
  ↓
Graph Loading
  ↓
Post-load Validation
```

Large dataset rules:

- chunk processing;
- bounded memory;
- resumable ingestion;
- checkpoints;
- deterministic IDs;
- idempotent loading;
- malformed-row handling;
- schema validation;
- ingestion metrics.

The system must work beyond the initial ~590K transaction scale.

---

# 8. Phase 3 — Domain Design

Create domain objects for:

```text
Investigation
Case
Evidence
Finding
Hypothesis
FraudPattern
PolicyDecision
Action
Approval
Outcome
CaseMemory
EvidenceRequest
```

Do not allow infrastructure models to leak into domain logic.

---

# 9. Phase 4 — TigerGraph

TigerGraph must be a first-class component.

Implement:

- schema;
- loading jobs;
- GSQL queries;
- graph algorithms;
- indexes/appropriate optimization;
- investigation queries;
- historical-case queries;
- relationship queries;
- pattern queries.

Required query categories:

```text
transaction_context
customer_context
account_history
connected_entities
shared_device
related_transactions
historical_cases
pattern_candidates
graph_risk_features
```

All queries must be bounded and safe against high-degree entities.

---

# 10. Phase 5 — TigerGraph MCP

Expose controlled investigation tools through TigerGraph MCP.

Each tool needs:

```text
name
description
input schema
output schema
authorization
timeout
error contract
```

Tool outputs must include source/provenance where possible.

Do not expose unrestricted arbitrary graph execution to the agent if a bounded domain-specific tool is sufficient.

---

# 11. Phase 6 — Agent Architecture

The agent should be implemented as a stateful workflow/state machine.

Core states:

```text
TRIGGERED
CASE_CREATED
INVESTIGATING
EVIDENCE_COLLECTED
ASSESSING
EVIDENCE_REQUESTED
EVIDENCE_RECEIVED
REASSESSING
POLICY_EVALUATION
ACTION_PROPOSED
APPROVAL_PENDING
ACTION_EXECUTED
CASE_CLOSED
MEMORY_UPDATED
```

The agent must persist state.

A process restart must not lose the investigation.

---

# 12. Agent Toolset

At minimum, implement tools conceptually equivalent to:

```text
get_transaction_context
get_customer_context
get_account_history
find_connected_entities
find_related_transactions
find_historical_cases
detect_patterns
retrieve_policy
retrieve_regulatory_context
retrieve_similar_cases
request_customer_verification
request_step_up
record_evidence
update_case
evaluate_policy
request_approval
execute_action
store_case_memory
```

The exact tool names may differ.

Each tool must do one thing well.

---

# 13. Agent Planning Rules

The agent should:

1. inspect trigger;
2. identify investigation target;
3. gather high-value graph evidence;
4. evaluate patterns;
5. inspect historical memory;
6. calculate evidence completeness;
7. identify contradictions;
8. determine whether evidence is sufficient;
9. request additional evidence if needed;
10. reassess;
11. evaluate policy;
12. propose NBA;
13. route approval;
14. execute only when authorized;
15. update case;
16. update memory.

Avoid unnecessary tool calls.

---

# 14. Evidence Selection

Use an evidence-value mindset.

For each potential evidence source:

```text
relevance
reliability
freshness
cost
expected uncertainty reduction
```

The agent should prefer evidence likely to materially change the decision.

Do not collect evidence simply to make the investigation look active.

---

# 15. Uncertainty

Implement deterministic support around the agent.

Maintain:

```text
risk
confidence
evidence_completeness
contradictions
decision_readiness
```

The agent must be able to produce:

```text
INSUFFICIENT_EVIDENCE
```

with a structured explanation.

Never convert low evidence into high confidence simply because the LLM sounds confident.

---

# 16. Fraud Patterns

Implement challenge-defined patterns as modular detectors.

Detector contract:

```text
PatternResult {
  pattern
  status
  evidence[]
  confidence
  satisfied_conditions[]
  missing_conditions[]
  contradictions[]
}
```

Do not create benchmark-specific detectors.

---

# 17. GraphRAG

Build a retrieval pipeline that combines:

```text
TigerGraph evidence
+
policy documents
+
fraud pattern knowledge
+
regulatory references
+
historical case memory
```

The final context must preserve provenance.

The model should receive structured evidence rather than an uncontrolled giant text dump.

---

# 18. Case Memory

Persist:

- findings;
- evidence;
- decisions;
- actions;
- approvals;
- outcomes;
- analyst decisions;
- recurring entities;
- fraud patterns.

Implement retrieval by:

- structured filters;
- semantic similarity where useful;
- graph similarity/context.

Historical memory is contextual. Current evidence and policy remain authoritative.

---

# 19. Policy and Authorization

Implement:

```text
PolicyRepository
PolicyEvaluator
PermissionEvaluator
ApprovalRouter
ActionExecutor
```

Policy evaluation must be deterministic.

The LLM may say:

> Recommend account restriction.

It cannot decide:

> Authorized to execute.

That determination belongs to the policy/permission system.

---

# 20. Action Framework

Create an extensible action interface.

Example:

```text
Action
 ├── AllowTransaction
 ├── MonitorAccount
 ├── StepUpAuthentication
 ├── RequestCustomerVerification
 ├── BlockTransaction
 ├── RestrictAccount
 ├── EscalateCase
 ├── FileReport
 └── CloseCase
```

Challenge-required actions can be simulated using safe adapters/mock APIs.

Every action must be:

- authorized;
- idempotent;
- auditable;
- observable;
- retry-safe where applicable.

---

# 21. Approval Workflow

Approval states:

```text
NOT_REQUIRED
REQUIRED
PENDING
APPROVED
REJECTED
EXPIRED
```

Do not execute rejected/expired actions.

Store:

```text
approver
timestamp
policy_version
decision
reason
```

---

# 22. Failure Handling

Implement explicit failure categories.

### Data

- missing column;
- invalid type;
- corrupt row;
- duplicate;
- schema drift.

### Graph

- timeout;
- unavailable;
- partial response;
- high-degree entity.

### Agent

- malformed tool call;
- invalid structured output;
- timeout;
- retry exhaustion.

### Evidence

- unavailable;
- stale;
- contradictory.

### Action

- unauthorized;
- approval rejected;
- execution failed;
- duplicate request.

Every failure should result in a controlled state, not a crash loop.

---

# 23. Idempotency and Concurrency

Use stable identifiers:

```text
trigger_id
case_id
investigation_id
evidence_id
evidence_request_id
action_id
approval_id
ingestion_batch_id
```

Use optimistic concurrency/version checks for mutable cases.

Repeated messages must not duplicate actions.

---

# 24. Backend

Prefer a modular monolith unless actual scale requires service separation.

Use clear boundaries:

```text
domain
application
infrastructure
interfaces
```

External systems must be accessed through interfaces/adapters.

---

# 25. SOLID

The implementation must visibly follow:

- Single Responsibility;
- Open/Closed;
- Liskov Substitution;
- Interface Segregation;
- Dependency Inversion.

Avoid:

- god classes;
- giant agent files;
- global mutable state;
- direct SDK calls everywhere;
- business rules inside controllers;
- LLM prompts containing authorization logic.

---

# 26. Frontend Requirements

Build a serious investigation workstation.

### Explicitly avoid

```text
NO neon gradients
NO purple/blue AI glow
NO glassmorphism overload
NO cyberpunk backgrounds
NO robot graphics
NO generic AI sparkles
NO giant marketing dashboard cards
NO fake real-time animations
```

### Desired visual character

- restrained;
- forensic;
- financial;
- professional;
- information-dense;
- calm;
- high contrast;
- excellent typography;
- minimal decoration.

Suggested palette:

```text
Graphite / Charcoal
Warm White
Slate
Muted Amber
Muted Red
Muted Green
```

Do not make the whole UI colorful.

Color should encode state, not decoration.

---

# 27. Frontend Information Architecture

```text
/
├── dashboard
├── cases
├── cases/:id
├── benchmark
├── policies
├── memory
└── settings
```

## Dashboard

Show:

- open investigations;
- cases needing approval;
- evidence requests;
- investigation throughput;
- benchmark status;
- system health.

## Case workspace

Primary screen:

```text
Case header
Risk / confidence / readiness
Graph
Evidence
Timeline
Agent activity
Historical cases
Pattern analysis
Policy
NBA
Approval
Audit
```

---

# 28. Graph UX

The graph must be useful, not decorative.

Features:

- zoom;
- pan;
- node selection;
- relationship inspection;
- path highlighting;
- time filtering;
- entity filtering;
- suspicious-node emphasis;
- expand neighbors with limits;
- evidence linkage.

Selecting a node should show why it matters.

---

# 29. Evidence UX

Evidence cards should show:

```text
SOURCE
OBSERVED TIME
TYPE
SUMMARY
SUPPORTS
CONTRADICTS
STRENGTH
```

The UI must distinguish:

> Observed

from:

> RAVEL interpretation

---

# 30. Agent Activity UX

Display operational tool events only.

Example:

```text
10:32:11
Transaction neighborhood queried

10:32:12
7 connected accounts discovered

10:32:14
Historical case similarity search completed

10:32:16
Evidence completeness: 64%

10:32:17
Additional customer verification required
```

Do not display hidden reasoning or chain-of-thought.

---

# 31. Decision UX

Use a clear decision block:

```text
NEXT BEST ACTION

Step-up customer verification

Why:
• Shared device relationship
• Related suspicious activity
• Similar historical case

Uncertainty:
Customer ownership is not yet verified.

Approval:
Required — Fraud Analyst

What could change this:
Customer confirms transaction
```

---

# 32. Replay UX

Allow reviewers to replay:

```text
Trigger
→ Graph evidence
→ Historical evidence
→ Missing evidence
→ New evidence
→ Reassessment
→ Policy
→ Action
```

This is a major demo feature.

---

# 33. Backend API

Implement typed APIs for:

```text
POST /investigations
GET  /investigations/:id
POST /investigations/:id/evidence
POST /investigations/:id/evidence-requests
POST /investigations/:id/assess
POST /investigations/:id/actions
POST /investigations/:id/approvals
GET  /investigations/:id/timeline
GET  /investigations/:id/graph
GET  /investigations/:id/memory
GET  /benchmarks
POST /benchmarks/run
```

Exact routing may vary.

---

# 34. Testing Contract

No feature is complete without tests.

Required layers:

```text
Unit
Integration
Contract
End-to-End
Failure
Benchmark Regression
```

Critical paths require integration/E2E tests.

---

# 35. Benchmark Contract

Run all 20 benchmark cases.

For each:

```text
input
graph evidence
historical evidence
patterns
uncertainty
additional evidence
updated assessment
NBA
approval route
action
case record
SAR if required
```

Produce:

```text
benchmark/results.json
benchmark/report.md
```

Do not fabricate metrics.

If the challenge does not provide a direct numeric scoring formula, report measured system outputs and qualitative/structured comparison rather than inventing a score.

---

# 36. Self-Improvement Loop

After benchmark execution:

```text
FAILURE
 ↓
CLASSIFY
 ↓
ROOT CAUSE
 ↓
FIX
 ↓
ADD REGRESSION TEST
 ↓
RERUN AFFECTED CASES
 ↓
RERUN FULL BENCHMARK
```

Classify failures as:

- data;
- graph;
- pattern;
- retrieval;
- memory;
- uncertainty;
- policy;
- action;
- agent planning;
- UI;
- infrastructure.

Never fix a benchmark failure by hardcoding the case.

---

# 37. Performance

Measure:

- ingestion throughput;
- graph query latency;
- investigation latency;
- retrieval latency;
- agent latency;
- UI load time;
- benchmark runtime.

Avoid:

- N+1 graph queries;
- repeated historical retrieval;
- full graph scans per investigation;
- loading all transactions into Python;
- giant prompts containing the full dataset.

---

# 38. Observability

Implement structured logs.

Every investigation should be traceable by:

```text
trace_id
case_id
investigation_id
tool_call_id
```

Record:

- tool latency;
- tool status;
- errors;
- retries;
- LLM calls;
- policy decisions;
- action events;
- benchmark execution.

Never log secrets or unnecessary sensitive fields.

---

# 39. Configuration

No hardcoded credentials.

Use environment configuration.

Separate:

```text
development
test
benchmark
demo
```

Keep model/provider configuration replaceable.

---

# 40. CI Quality Gate

Before declaring completion, run:

```text
format
lint
typecheck
unit tests
integration tests
E2E tests
build
benchmark validation
```

If anything fails:

> Diagnose → fix → rerun.

Do not stop at the first successful local run.

---

# 41. Documentation

Generate:

```text
README.md
ARCHITECTURE.md
DATA_MODEL.md
GRAPH.md
AGENT.md
POLICY.md
BENCHMARK.md
DEMO.md
TROUBLESHOOTING.md
```

README must contain:

- prerequisites;
- environment setup;
- TigerGraph setup;
- dataset setup;
- ingestion;
- backend;
- frontend;
- tests;
- benchmark;
- demo;
- known limitations.

---

# 42. Demo Preparation

Prepare one strong 3–5 minute story.

Do not demo ten features badly.

Demo:

```text
Suspicious transaction
      ↓
Graph relationships
      ↓
Historical case
      ↓
Uncertainty
      ↓
Evidence request
      ↓
New evidence
      ↓
Updated assessment
      ↓
NBA
      ↓
Approval
      ↓
Case memory
```

---

# 43. Demo Reliability

Create a deterministic demo mode that uses the real investigation architecture but controlled inputs/mocks where external services are unavailable.

Demo mode must not fake product capabilities.

Clearly mark simulated actions.

---

# 44. UI Quality Gate

Before completion, inspect every screen for:

- inconsistent spacing;
- placeholder text;
- fake metrics;
- broken loading state;
- broken empty state;
- poor error state;
- excessive colors;
- excessive rounded cards;
- unreadable graph;
- confusing terminology;
- inaccessible controls.

Fix these before final delivery.

---

# 45. Security Gate

Verify:

- no secrets committed;
- no credentials in frontend;
- authorization before action;
- approval cannot be bypassed;
- sensitive logs minimized;
- action APIs idempotent;
- audit trail present.

---

# 46. Final Autonomous Quality Gate

Do not report completion until all are true:

```text
[ ] Challenge requirements mapped
[ ] Dataset inspected
[ ] Data pipeline reproducible
[ ] TigerGraph integrated
[ ] GSQL implemented
[ ] Graph algorithms implemented
[ ] TigerGraph MCP integrated
[ ] GraphRAG implemented
[ ] Agent state machine implemented
[ ] Evidence ledger implemented
[ ] Uncertainty implemented
[ ] Case memory implemented
[ ] Policy engine implemented
[ ] Approval routing implemented
[ ] NBA implemented
[ ] Action adapters implemented
[ ] Backend complete
[ ] Frontend complete
[ ] UI reviewed
[ ] Unit tests pass
[ ] Integration tests pass
[ ] E2E tests pass
[ ] Failure tests pass
[ ] 20 benchmark cases executed
[ ] Benchmark failures investigated
[ ] Regression tests added
[ ] Full benchmark rerun
[ ] Documentation complete
[ ] Demo flow verified
[ ] No hardcoded benchmark answers
[ ] No fabricated metrics
[ ] No fabricated evidence
[ ] No secrets committed
```

---

# 47. Final Response Format for the Coding Agent

When the build is complete, report:

## Implemented

Concise module-by-module summary.

## Verification

Exact commands executed and results.

## Benchmark

Measured results only.

## Known limitations

Only real limitations.

## Run instructions

Exact commands for a fresh environment.

## Demo

Exact steps to reproduce the 3–5 minute demo.

## Files changed

Important files/modules only.

Do not claim anything that was not actually verified.

---

# 48. Engineering Philosophy

RAVEL should feel like:

> **A real investigation product that happens to use an agent.**

Not:

> **An LLM demo wrapped in a dashboard.**

TigerGraph should perform the relationship investigation.

Deterministic services should enforce policy and authorization.

The agent should orchestrate evidence gathering and reasoning.

The UI should make the investigation understandable.

The final case record should make the decision defensible.

That is the quality bar.
