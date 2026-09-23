"""Uncertainty engine outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ravel.domain.enums import DecisionReadiness, RiskLevel


class UncertaintyAssessment(BaseModel):
    risk: float = 0.0  # 0..1 raw risk, driven by deterministic risk features
    confidence: float = 0.0  # 0..1 confidence in the determination
    evidence_completeness: float = 0.0  # 0..1 how complete the evidence picture is
    contradictions: int = 0
    decision_readiness: DecisionReadiness = DecisionReadiness.NOT_READY
    risk_level: RiskLevel = RiskLevel.LOW
    missing_evidence: list[str] = Field(default_factory=list)
    stale_evidence: int = 0
    weak_evidence: int = 0
    hypotheses: list[str] = Field(default_factory=list)


class Assessment(BaseModel):
    """Combined pattern + uncertainty assessment for one investigation step."""

    fraud_probability: float = 0.0
    verdict: str = "uncertain"
    pattern_name: str = "none"
    pattern_description: str = ""
    uncertainty: UncertaintyAssessment = Field(default_factory=UncertaintyAssessment)
    pattern_results: list[dict] = Field(default_factory=list)
    assessment_text: str = ""
    step: int = 0


class UncertaintyJourney(BaseModel):
    """Uncertainty before and after controlled additional evidence."""

    initial: UncertaintyAssessment = Field(default_factory=UncertaintyAssessment)
    final: UncertaintyAssessment = Field(default_factory=UncertaintyAssessment)
    what_reduced_uncertainty: list[str] = Field(default_factory=list)
