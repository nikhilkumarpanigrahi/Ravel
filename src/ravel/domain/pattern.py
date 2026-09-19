"""Fraud pattern detection results and detector contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from ravel.domain.enums import FraudPattern, PatternStatus


class PatternResult(BaseModel):
    pattern: FraudPattern = FraudPattern.NONE
    status: PatternStatus = PatternStatus.NOT_DETECTED
    candidate: bool = False
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    satisfied_conditions: list[str] = Field(default_factory=list)
    missing_conditions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    affected_txn_ids: list[str] = Field(default_factory=list)
    first_suspicious_txn_id: str = ""
    device_profiles: list[str] = Field(default_factory=list)
    connected_card_ids: list[str] = Field(default_factory=list)
    description: str = ""


class PatternDetector(ABC):
    """Base contract for modular fraud-pattern detectors (Open/Closed principle)."""

    pattern: FraudPattern

    @abstractmethod
    def detect(self, ctx: InvestigationContext) -> PatternResult: ...


class InvestigationContext(BaseModel):
    """Deterministic view of collected graph evidence handed to detectors and the agent."""

    txn: dict = Field(default_factory=dict)  # the flagged transaction
    customer: dict = Field(default_factory=dict)
    card_history: list[dict] = Field(default_factory=list)
    card_window: list[dict] = Field(default_factory=list)
    devices: list[dict] = Field(default_factory=list)
    connected_entities: list[dict] = Field(default_factory=list)
    related_transactions: list[dict] = Field(default_factory=list)
    historical_cases: list[dict] = Field(default_factory=list)
    similar_cases: list[dict] = Field(default_factory=list)
    regions: list[dict] = Field(default_factory=list)
    signals: dict = Field(default_factory=dict)
