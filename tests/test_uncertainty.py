"""Unit tests for deterministic uncertainty assessment."""

from ravel.application.uncertainty_service import assess_uncertainty
from ravel.domain.enums import DecisionReadiness, FraudPattern, PatternStatus, Verdict
from ravel.domain.pattern import PatternResult


def test_customer_response_improves_decision_readiness():
    result = PatternResult(
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD,
        status=PatternStatus.PARTIAL,
        candidate=True,
        confidence=0.65,
        missing_conditions=["customer ownership confirmation"],
    )
    initial = assess_uncertainty(
        fraud_probability=0.65,
        model_risk_score=0.8,
        verdict=Verdict.UNCERTAIN,
        pattern_results=[result],
        evidence_count=3,
        has_history=True,
        has_connected_entities=False,
    )
    final = assess_uncertainty(
        fraud_probability=0.9,
        model_risk_score=0.8,
        verdict=Verdict.FRAUD,
        pattern_results=[result],
        evidence_count=4,
        has_history=True,
        has_connected_entities=False,
        customer_response="Customer denied the transaction",
    )
    assert final.evidence_completeness > initial.evidence_completeness
    assert final.confidence > initial.confidence
    assert final.decision_readiness == DecisionReadiness.READY


def test_contradictions_reduce_confidence():
    result = PatternResult(
        pattern=FraudPattern.OUT_OF_REGION_USE,
        status=PatternStatus.PARTIAL,
        candidate=True,
        confidence=0.7,
        contradictions=["activity resembles established travel"],
    )
    assessment = assess_uncertainty(
        fraud_probability=0.7,
        model_risk_score=0.7,
        verdict=Verdict.UNCERTAIN,
        pattern_results=[result],
        evidence_count=2,
        has_history=False,
        has_connected_entities=False,
    )
    assert assessment.contradictions == 1
    assert assessment.decision_readiness != DecisionReadiness.READY
    assert "comparable historical case outcome" in assessment.missing_evidence
