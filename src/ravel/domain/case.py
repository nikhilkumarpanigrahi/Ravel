"""Case record — the graded internal investigation record (Part 1 of the answer file)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from ravel.domain.enums import CaseStatus, FraudPattern, Verdict
from ravel.domain.evidence import EvidenceRecord
from ravel.domain.uncertainty import UncertaintyJourney


class CaseEvidence(BaseModel):
    """Answer-file evidence object."""

    claim: str
    source: str
    ref: str = ""
    entity_ids: list[str] = Field(default_factory=list)
    graph_path: str = ""
    supports: str = ""
    contradicts: str = ""


class Case(BaseModel):
    case_id: str
    status: CaseStatus = CaseStatus.OPEN
    verdict: Verdict = Verdict.UNCERTAIN
    fraud_probability: float = 0.0
    pattern: FraudPattern = FraudPattern.NONE
    pattern_description: str = ""
    affected_txn_ids: list[str] = Field(default_factory=list)
    first_suspicious_txn_id: str = ""
    connected_card_ids: list[str] = Field(default_factory=list)
    connected_device_profiles: list[str] = Field(default_factory=list)
    exposure_usd: float = 0.0
    evidence: list[CaseEvidence] = Field(default_factory=list)
    similar_prior_cases: list[str] = Field(default_factory=list)
    summary: str = ""
    written_to_graph: bool = False
    graph_case_id: str = ""
    opened_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))

    @classmethod
    def evidence_from(cls, ev: EvidenceRecord) -> CaseEvidence:
        return CaseEvidence(
            claim=ev.claim,
            source=ev.source.value,
            ref=ev.ref,
            entity_ids=ev.entity_ids,
            graph_path=ev.graph_path,
            supports=ev.supports,
            contradicts=ev.contradicts,
        )


class SAR(BaseModel):
    """Part 2 of the answer file — the regulatory filing."""

    file: bool = False
    reason: str = ""
    narrative: str = ""
    subjects: list[str] = Field(default_factory=list)
    total_amount_usd: float = 0.0
    activity_dates: list[str] = Field(default_factory=list)


class AnswerFile(BaseModel):
    """The full graded deliverable for one benchmark case."""

    case_id: str
    case: Case
    evidence_requests: list[dict] = Field(default_factory=list)
    next_best_actions: dict = Field(default_factory=dict)
    uncertainty: UncertaintyJourney = Field(default_factory=UncertaintyJourney)
    sar: SAR = Field(default_factory=SAR)
    stop_reason: str = ""
    tool_calls: int = 0
    tokens: int = 0
    latency_s: float = 0.0
    agent_trace: list[dict] = Field(default_factory=list)


class CaseMemoryEntry(BaseModel):
    """Persisted reusable memory written after case closure."""

    memory_id: str = Field(default_factory=lambda: f"MEM-{uuid.uuid4().hex[:10]}")
    case_id: str
    graph_case_id: str = ""
    summary: str
    verdict: str
    pattern: str
    exposure_usd: float
    affected_txn_ids: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    device_profiles: list[str] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
