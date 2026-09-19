# RAVEL — Product Requirements Document

**Product:** RAVEL  
**Subtitle:** Agentic Fraud Investigation  
**Document:** Product PRD  
**Status:** Build Specification  
**Primary requirement source:** TigerGraph Agentic Fraud Investigation HHGOA challenge statement and supplied `HHGOA_IEEE` dataset specification.

---

## 1. Product Definition

RAVEL is an evidence-driven, graph-first fraud investigation system that turns a fraud signal into a defensible investigation, next-best action, approval route, and persistent case memory.

RAVEL is **not** a conventional fraud classifier.

Its primary job is to:

1. receive a fraud signal, customer report, or analyst-triggered investigation;
2. gather relevant evidence from transactions, identities, devices, connections, prior cases, policies, and approved external sources;
3. use TigerGraph and graph algorithms to expose relationships and fraud patterns;
4. assess risk, uncertainty, contradictions, and evidence completeness;
5. recognize when available evidence is insufficient;
6. request controlled additional evidence when appropriate;
7. reassess after new evidence;
8. recommend or execute an authorized next-best action;
9. route actions through the correct approval path;
10. produce a complete, explainable case record;
11. store findings, decisions, actions, outcomes, and reusable investigation memory.

The system must make it possible to answer:

> **What happened, what evidence supports it, what remains uncertain, what should happen next, who must approve it, and why?**

---

# 2. Challenge Alignment

The challenge requires an AI Agent for Fraud Investigation and Next-Best Action.

RAVEL must implement the following required capabilities.

| Challenge capability | RAVEL requirement |
|---|---|
| Trigger investigation | Supported |
| Investigate transactions | Supported |
| Investigate connected entities | Supported through TigerGraph |
| Analyze device/identity signals | Supported where dataset fields permit |
| Review previous fraud cases | Supported |
| Use external/policy information | Supported through controlled knowledge sources |
| Assess fraud pattern/type/risk | Supported |
| Create/progress case | Supported |
| Add evidence/findings | Supported |
| Update status/risk/actions | Supported |
| Case memory | Supported |
| Retrieve similar historical cases | Supported |
| Learn from prior decisions/outcomes | Supported |
| Request additional evidence | Supported |
| Customer validation / step-up / approved information | Supported as controlled actions or simulation stubs |
| Recommend/take action | Supported |
| Policy/permission enforcement | Deterministic, not LLM-only |
| Human approval | Supported |
| Explain decisions | Supported |
| Stop when evidence is sufficient | Supported |
| Update memory | Supported |
| TigerGraph | Core investigation engine |
| GSQL | Required |
| TigerGraph graph algorithms | Required |
| TigerGraph MCP | Required |
| GraphRAG | Required |
| Investigation UI | Required |

LLM reasoning is used for planning, tool selection, evidence synthesis, uncertainty explanation, and natural-language decisions. It must **not replace deterministic graph analysis, policy enforcement, authorization, or benchmark truth**.

---

# 3. Dataset Requirements

The benchmark dataset is `HHGOA_IEEE`.

The supplied challenge describes it as:

- approximately 590,000 card transactions;
- approximately 13,500 customers;
- six months of transaction activity;
- device/connection information;
- a risk score for every transaction;
- no direct `Is Fraud` flag;
- closed investigations from the first four months;
- confirmed fraud and cleared cases;
- bank fraud policy;
- five known fraud patterns;
- relevant regulatory references;
- 20 benchmark cases from the final two months;
- identical benchmark cases for all teams.

### Dataset rules

RAVEL must:

- read the dataset README before implementation;
- inspect every provided file and column;
- preserve source semantics;
- distinguish missing from negative/false values;
- never invent ground-truth labels;
- never hardcode the 20 benchmark answers;
- support additional data without architectural redesign;
- preserve provenance for derived evidence;
- make ingestion reproducible.

If a source does not contain a field, RAVEL must not fabricate it.

---

# 4. Product Principles

## 4.1 Evidence over intuition

Every material conclusion must reference evidence.

## 4.2 Graph first

Relationships are first-class investigation evidence.

## 4.3 Uncertainty is a product feature

RAVEL must be allowed to say:

> Insufficient evidence.

It should identify what is missing and what evidence could reduce uncertainty.

## 4.4 Deterministic controls

Policy, permissions, action eligibility, approval routing, thresholds, and audit requirements cannot depend solely on an LLM.

## 4.5 Human authority

Where policy requires approval, RAVEL recommends and routes; it does not bypass approval.

## 4.6 Reproducibility

An investigation must be replayable from its recorded inputs, tool calls, evidence references, policy version, and model/configuration version.

## 4.7 No fabricated certainty

The system must distinguish:

- observed evidence;
- derived graph evidence;
- historical evidence;
- policy knowledge;
- model interpretation;
- unresolved uncertainty.

---

# 5. End-to-End Product Flow

```text
Fraud Signal
    |
    v
Create Investigation
    |
    v
Normalize Trigger
    |
    v
Build Investigation Context
    |
    v
TigerGraph Investigation
    |
    +--> Transaction context
    +--> Customer/account context
    +--> Device/IP/entity relationships
    +--> Related transactions
    +--> Historical cases
    +--> Graph patterns
    |
    v
Evidence Ledger
    |
    v
Pattern + Risk Assessment
    |
    v
Uncertainty Assessment
    |
    +--> Sufficient
    |       |
    |       v
    |   Policy Evaluation
    |
    +--> Insufficient
            |
            v
      Missing Evidence Plan
            |
            v
      Controlled Evidence Action
            |
            v
      New Evidence
            |
            v
        Reassessment
            |
            v
     Next Best Action
            |
            v
 Approval / Authorized Execution
            |
            v
 Case Update
            |
            v
 Case Memory
```

---

# 6. Investigation State Machine

Required states:

```text
TRIGGERED
  ↓
CASE_CREATED
  ↓
INVESTIGATING
  ↓
EVIDENCE_COLLECTED
  ↓
ASSESSING
  ├── INSUFFICIENT_EVIDENCE → EVIDENCE_REQUESTED
  │                              ↓
  │                         EVIDENCE_RECEIVED
  │                              ↓
  │                         REASSESSING
  │
  └── SUFFICIENT_EVIDENCE
             ↓
       POLICY_EVALUATION
             ↓
       ACTION_PROPOSED
             ↓
      APPROVAL_REQUIRED?
        /           \
      YES            NO
       |              |
 APPROVAL_PENDING   EXECUTABLE
       |              |
 APPROVED / REJECTED  |
       \              /
        ACTION_EXECUTED
              ↓
          CASE_CLOSED
              ↓
        MEMORY_UPDATED
```

Every transition must be auditable.

---

# 7. Graph Architecture

TigerGraph is the core relationship and investigation engine.

## 7.1 Conceptual entities

The exact schema must be derived from the supplied dataset rather than invented.

Potential entities include:

- Customer
- Account
- Transaction
- Device
- IP / network identifier
- Merchant
- Investigation
- Fraud Case
- Evidence
- Pattern
- Action
- Policy
- Approval
- Outcome

## 7.2 Relationship examples

```text
Customer ─OWNS→ Account
Account ─PERFORMS→ Transaction
Transaction ─USES→ Device
Transaction ─FROM_IP→ IP
Transaction ─TO→ Merchant
Customer ─HAS_DEVICE→ Device
Customer ─HAS_CASE→ Case
Case ─HAS_EVIDENCE→ Evidence
Case ─RESULTED_IN→ Outcome
```

Only relationships supported by source data should be implemented as factual relationships.

---

# 8. Graph Investigation Capabilities

RAVEL must expose bounded, purpose-built graph queries rather than unrestricted graph traversal.

Required investigation capabilities:

- transaction neighborhood;
- customer/account history;
- shared device detection;
- shared connection detection;
- related-account discovery;
- transaction chains;
- temporal relationships;
- historical case relationships;
- connected suspicious entities;
- repeated behavioral patterns;
- graph-derived risk features;
- fraud-pattern candidate detection.

### High-degree protection

The system must handle entities connected to thousands of records.

Controls:

- bounded traversal depth;
- result limits;
- pagination;
- time windows;
- ranking;
- top-K expansion;
- aggregation before expansion;
- timeout;
- query cancellation;
- high-degree entity safeguards.

---

# 9. Graph Algorithms

Use TigerGraph GSQL and graph algorithms where appropriate.

Examples:

- neighborhood exploration;
- similarity;
- connected components;
- community/cluster discovery;
- shortest/weighted paths;
- centrality where meaningful;
- temporal relationship analysis;
- suspicious subgraph discovery.

Algorithms must have a documented purpose. Do not add algorithms simply to make the architecture look complex.

---

# 10. GraphRAG

RAVEL must combine:

### Graph evidence

- entities;
- relationships;
- transaction paths;
- connected activity;
- historical cases.

### Unstructured knowledge

- bank fraud policy;
- documented fraud patterns;
- regulatory references;
- case notes where available.

The retrieval layer must preserve source references.

The LLM must not treat retrieved text as an authorization source.

---

# 11. Evidence Ledger

Every investigation maintains an evidence ledger.

Each evidence record contains, where available:

```text
evidence_id
case_id
source
source_reference
evidence_type
observed_at
collected_at
summary
supports
contradicts
strength
confidence
derived_from
tool_used
policy_context
```

Evidence categories:

- transaction;
- relationship;
- behavioral;
- device;
- identity;
- historical case;
- policy;
- customer response;
- external source;
- analyst input;
- model-derived hypothesis.

The UI must distinguish observed evidence from interpretation.

---

# 12. Uncertainty Engine

RAVEL must maintain separate concepts:

```text
Risk
Confidence
Evidence Completeness
Decision Readiness
Contradiction Level
```

A high-risk transaction is not automatically a high-confidence fraud determination.

The engine must identify:

- missing evidence;
- contradictory evidence;
- stale evidence;
- weak evidence;
- unavailable evidence;
- evidence with conflicting timestamps;
- unresolved hypotheses.

Example:

```text
Risk:                 HIGH
Evidence confidence:  MEDIUM
Completeness:         61%
Contradictions:       1
Decision readiness:   NOT READY

Recommended evidence:
Customer verification
```

---

# 13. Fraud Pattern Analysis

The five documented challenge patterns must be represented as explicit, testable pattern definitions after the dataset/policy has been inspected.

Pattern detection should be modular:

```text
PatternDetector
 ├── PatternA
 ├── PatternB
 ├── PatternC
 ├── PatternD
 └── PatternE
```

A pattern detector must return:

- candidate;
- evidence;
- confidence;
- conditions met;
- conditions missing;
- contradictory signals.

Patterns must not be hardcoded to benchmark cases.

---

# 14. Case Memory

RAVEL must maintain investigation memory.

Memory should contain:

- case summary;
- evidence;
- findings;
- decisions;
- actions;
- approvals;
- outcomes;
- analyst decisions;
- discovered recurring entities;
- fraud patterns;
- final resolution.

Memory retrieval must support:

- similar transaction contexts;
- similar graph structures;
- similar patterns;
- similar customer/account behavior;
- previous decisions;
- previous outcomes.

Historical memory should influence recommendations as contextual evidence, not override current evidence or policy.

---

# 15. Additional Evidence

When evidence is insufficient, RAVEL creates a missing-evidence plan.

Example:

```text
Missing evidence:
Customer ownership confirmation

Reason:
Current graph evidence indicates a shared device,
but account ownership cannot be established.

Action:
Request customer verification.

Expected value:
Reduce uncertainty around account takeover hypothesis.
```

Evidence requests must be:

- policy-approved;
- authorized;
- auditable;
- idempotent;
- time-bounded;
- failure-aware.

---

# 16. Policy Engine

Policy enforcement must be deterministic.

Architecture:

```text
PolicyRepository
      ↓
PolicyEvaluator
      ↓
PermissionEvaluator
      ↓
ApprovalRouter
      ↓
ActionExecutor
```

The LLM may propose an action.

The policy engine determines:

- whether it is allowed;
- whether approval is required;
- who can approve;
- required evidence;
- applicable thresholds;
- whether execution is simulated or real.

The agent must never bypass the policy engine.

---

# 17. Next Best Action

NBA candidates may include:

- allow;
- monitor;
- request customer validation;
- step-up authentication;
- block transaction;
- restrict account;
- create/escalate case;
- request evidence;
- file/report where required;
- close/clear case;
- escalate to analyst.

RAVEL must explain:

1. recommended action;
2. evidence supporting it;
3. unresolved uncertainty;
4. policy basis;
5. approval route;
6. expected effect of additional evidence;
7. alternatives considered.

---

# 18. SAR / Reporting

Where the supplied challenge policy and case requirements indicate a suspicious activity report is required, RAVEL must create the required SAR/report record in the benchmark output.

The system must not invent regulatory facts.

Regulatory references must be stored with source/provenance.

---

# 19. Backend Architecture

Recommended structure:

```text
src/
├── domain/
│   ├── investigation/
│   ├── evidence/
│   ├── case/
│   ├── policy/
│   ├── action/
│   └── memory/
│
├── application/
│   ├── investigation_service/
│   ├── evidence_service/
│   ├── decision_service/
│   └── case_service/
│
├── infrastructure/
│   ├── tigergraph/
│   ├── mcp/
│   ├── llm/
│   ├── vector_store/
│   ├── persistence/
│   └── external_tools/
│
├── interfaces/
│   ├── api/
│   └── workers/
│
└── tests/
```

A modular monolith is preferred initially to avoid premature distributed-system complexity.

---

# 20. SOLID Requirements

### Single Responsibility
Each service owns one domain concern.

### Open/Closed
New fraud patterns and action types should be pluggable.

### Liskov Substitution
Tool adapters must implement stable contracts.

### Interface Segregation
Agent tools must expose narrow interfaces.

### Dependency Inversion
Domain logic depends on interfaces, not TigerGraph/LLM SDKs directly.

No giant `AgentManager` class.

---

# 21. Reliability

The system must handle:

- TigerGraph timeout;
- MCP unavailable;
- LLM timeout;
- LLM malformed output;
- partial graph results;
- duplicate trigger;
- duplicate action;
- stale case;
- concurrent analyst update;
- evidence request failure;
- approval timeout;
- action execution failure;
- dataset ingestion restart;
- corrupted row;
- missing column;
- schema drift.

Every external operation needs timeout, retry where safe, and failure classification.

---

# 22. Idempotency

At minimum:

```text
trigger_id
investigation_id
evidence_request_id
action_request_id
approval_request_id
ingestion_batch_id
```

Repeated execution must not duplicate cases, actions, evidence, or memory.

---

# 23. Large Dataset Requirements

The challenge dataset is approximately 590K transactions, but the implementation must not assume that is the permanent maximum.

Requirements:

- batch/streaming ingestion;
- chunking;
- checkpoints;
- resumable loading;
- bounded memory;
- validation before insertion;
- deduplication;
- indexes where supported;
- graph query limits;
- pagination;
- cached reusable investigation context;
- asynchronous long-running jobs;
- progress reporting;
- ingestion metrics.

Never load the entire dataset into application memory.

---

# 24. Frontend Product Direction

## Visual principle

**Absolutely no generic AI-dashboard aesthetic.**

Do not use:

- neon purple/blue gradients;
- glowing cards;
- excessive glassmorphism;
- random circuit backgrounds;
- giant robot/AI illustrations;
- “AI magic” animations;
- excessive rounded cards;
- futuristic sci-fi decorations.

RAVEL should look like a serious financial-crime investigation workstation.

## Visual language

Preferred:

- warm/off-white or very dark neutral base;
- charcoal;
- graphite;
- muted slate;
- restrained amber/red for alerts;
- white/grey typography;
- subtle borders;
- compact information density;
- strong spacing;
- minimal shadows;
- restrained motion.

Think:

> Bloomberg terminal + modern forensic workstation + premium enterprise software.

Not:

> AI startup landing page.

---

# 25. Investigation UI

The investigation page should be the product centerpiece.

Suggested layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ RAVEL                                      CASE #RV-002841   │
├──────────────┬───────────────────────────────┬───────────────┤
│ CASE         │                               │ DECISION      │
│              │      RELATIONSHIP GRAPH       │               │
│ Risk 87      │                               │ Status        │
│ Confidence  │                               │ Investigation │
│ 71           │                               │               │
│              │                               │ Next Action   │
│ Pattern      │                               │ STEP-UP       │
│ ATO          │                               │               │
├──────────────┼───────────────────────────────┼───────────────┤
│ EVIDENCE     │ INVESTIGATION TIMELINE        │ POLICY        │
│              │                               │ Approval      │
│ Transaction  │ 10:31 signal                  │ Required      │
│ Device       │ 10:32 graph expanded         │               │
│ History      │ 10:33 case found             │               │
│ Customer     │ 10:35 verification requested │               │
└──────────────┴───────────────────────────────┴───────────────┘
```

---

# 26. UI Features

Required:

- case inbox;
- investigation workspace;
- graph visualization;
- evidence ledger;
- timeline;
- uncertainty panel;
- fraud pattern panel;
- policy/approval panel;
- next-best-action panel;
- agent activity/tool trace;
- case memory;
- similar historical cases;
- action history;
- audit trail;
- benchmark case view;
- decision replay.

### Agent activity

Show concise operational events:

```text
10:32:11  Queried transaction neighborhood
10:32:12  Found 7 related accounts
10:32:13  Detected shared device
10:32:15  Retrieved 2 similar cases
10:32:16  Evidence completeness: 64%
10:32:17  Customer verification required
```

Do not expose hidden chain-of-thought.

---

# 27. Decision Replay

Every case should be replayable:

```text
Trigger
 ↓
Evidence
 ↓
Hypothesis
 ↓
Additional evidence
 ↓
Updated evidence
 ↓
Policy
 ↓
Recommendation
 ↓
Approval
 ↓
Action
```

Analysts should be able to understand why the recommendation changed.

---

# 28. Counterfactual / “What Would Change This?”

RAVEL should provide:

```text
Current decision:
STEP-UP VERIFICATION

What could change it?

+ Customer confirms transaction
+ Device ownership verified
+ Contradictory transaction history
+ New connected-account evidence
```

This makes uncertainty operational rather than decorative.

---

# 29. Security

Required:

- role-based access;
- least privilege;
- action authorization;
- sensitive-field minimization;
- audit logs;
- secrets outside source code;
- environment-specific configuration;
- no customer secrets in logs;
- no raw sensitive data in frontend unless required.

---

# 30. Observability

Track:

- investigation latency;
- graph query latency;
- LLM latency;
- tool failures;
- evidence requests;
- action execution;
- approval latency;
- token usage;
- benchmark results;
- memory retrieval;
- ingestion throughput;
- graph query timeout rate.

---

# 31. Testing

### Unit tests

- policy evaluation;
- state transitions;
- evidence scoring;
- uncertainty;
- pattern detectors;
- action authorization;
- idempotency.

### Integration tests

- TigerGraph;
- MCP;
- GraphRAG;
- case memory;
- action adapters.

### End-to-end

At least:

```text
trigger
→ investigate
→ insufficient evidence
→ request evidence
→ receive evidence
→ reassess
→ NBA
→ approval
→ action
→ case memory
```

### Failure tests

Explicitly test:

- timeout;
- malformed LLM output;
- missing graph;
- conflicting evidence;
- duplicate trigger;
- denied approval;
- failed action;
- stale evidence;
- incomplete dataset.

---

# 32. Benchmark

RAVEL must run all 20 challenge benchmark cases through the same pipeline.

For each case output:

- case/investigation record;
- evidence;
- findings;
- decisions;
- actions;
- approval route before and after additional evidence;
- case written to graph;
- SAR where required;
- next-best action;
- reasoning/explanation.

Benchmark runner must produce machine-readable and human-readable results.

Do not optimize by hardcoding case IDs.

---

# 33. Acceptance Criteria

RAVEL is complete only when:

- [ ] dataset ingestion is reproducible;
- [ ] TigerGraph is operational;
- [ ] GSQL queries are implemented;
- [ ] graph algorithms are used meaningfully;
- [ ] TigerGraph MCP is integrated;
- [ ] GraphRAG works;
- [ ] agentic investigation works;
- [ ] case memory works;
- [ ] uncertainty is explicit;
- [ ] additional evidence workflow works;
- [ ] policy enforcement is deterministic;
- [ ] approval routing works;
- [ ] NBA works;
- [ ] benchmark runner executes all 20 cases;
- [ ] UI shows the investigation;
- [ ] complete case records are persisted;
- [ ] tests pass;
- [ ] failure cases are handled;
- [ ] README enables reproducible setup;
- [ ] demo can be completed within 3–5 minutes.

---

# 34. Demo Narrative

The demo should tell one investigation story.

### Scene 1 — Trigger

A suspicious transaction enters RAVEL.

### Scene 2 — Graph

RAVEL expands the transaction into connected entities.

### Scene 3 — Historical memory

A similar historical case is retrieved.

### Scene 4 — Uncertainty

RAVEL explicitly says the evidence is insufficient.

### Scene 5 — Evidence request

Customer verification is requested through a controlled action.

### Scene 6 — Reassessment

The new evidence changes the evidence state.

### Scene 7 — Decision

RAVEL recommends the next-best action.

### Scene 8 — Approval

The action is routed through policy.

### Scene 9 — Case closure

The case record and memory are updated.

The final screen should show:

> **What we knew → what we learned → what changed → what we decided → why.**

---

# 35. Product Quality Bar

RAVEL should feel like software built by an experienced engineering team, not a generated prototype.

Quality signals:

- deterministic domain logic;
- typed interfaces;
- clear module boundaries;
- meaningful tests;
- realistic loading states;
- graceful error states;
- no fake metrics;
- no hardcoded benchmark answers;
- no fabricated evidence;
- no decorative AI UI;
- clear provenance;
- clear policy boundaries;
- reproducible investigations.

---

# 36. Definition of Done

The product is done only when the benchmark can be run from a clean environment and a reviewer can follow a complete investigation from trigger to final action without reading source code.

