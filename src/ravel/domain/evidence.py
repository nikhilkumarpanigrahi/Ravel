"""Evidence ledger records and evidence requests."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from ravel.domain.enums import EvidenceRequestType, EvidenceSource, EvidenceType


class EvidenceRecord(BaseModel):
    """One ledger entry. Mirrors the evidence object emitted in answer files, extended with
    the fields the Product PRD (section 11) requires for provenance and scoring."""

    evidence_id: str = Field(default_factory=lambda: f"EV-{uuid.uuid4().hex[:10]}")
    case_id: str = ""
    claim: str
    source: EvidenceSource
    ref: str = ""
    entity_ids: list[str] = Field(default_factory=list)
    evidence_type: EvidenceType = EvidenceType.TRANSACTION
    observed_at: datetime | None = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    supports: str = ""
    contradicts: str = ""
    strength: float = 0.0  # 0..1 weight of this evidence
    confidence: float = 0.0  # 0..1 trust in the evidence itself
    derived_from: str = ""
    tool_used: str = ""
    policy_context: str = ""


class EvidenceRequest(BaseModel):
    """A controlled request for additional evidence (customer validation, step-up, analyst info)."""

    request_id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:10]}")
    type: EvidenceRequestType
    asked_after_step: int
    assumed_response: str = ""
    reason: str = ""
    expected_value: str = ""
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    fulfilled: bool = False
    fulfilled_at: datetime | None = None


class MissingEvidencePlan(BaseModel):
    missing: str
    reason: str
    action: str
    expected_value: str
