"""Deterministic uncertainty assessment from collected investigation evidence."""

from __future__ import annotations

from ravel.domain.enums import DecisionReadiness, PatternStatus, RiskLevel, Verdict
from ravel.domain.pattern import PatternResult
from ravel.domain.uncertainty import UncertaintyAssessment


def assess_uncertainty(
    *,
    fraud_probability: float,
    model_risk_score: float | None,
    verdict: Verdict,
    pattern_results: list[PatternResult],
    evidence_count: int,
    has_history: bool,
    has_connected_entities: bool,
    customer_response: str = "",
) -> UncertaintyAssessment:
    """Calculate decision readiness without treating model risk as ground truth."""
    candidates = [result for result in pattern_results if result.candidate]
    contradictions = sum(len(result.contradictions) for result in candidates)
    missing = sorted(
        {condition for result in candidates for condition in result.missing_conditions if condition}
    )
    if not customer_response and verdict == Verdict.UNCERTAIN:
        missing.append("customer ownership confirmation")
    if not has_history:
        missing.append("comparable historical case outcome")

    base_completeness = 0.2
    base_completeness += min(0.2, evidence_count * 0.04)
    base_completeness += 0.15 if has_history else 0.0
    base_completeness += 0.15 if has_connected_entities else 0.0
    base_completeness += 0.15 if candidates else 0.0
    base_completeness += 0.15 if customer_response else 0.0
    completeness = max(0.0, min(1.0, base_completeness - min(0.2, contradictions * 0.05)))

    settled_confidence = max(fraud_probability, 1.0 - fraud_probability)
    confidence = max(0.0, min(1.0, settled_confidence - min(0.2, contradictions * 0.05)))
    risk = max(float(model_risk_score or 0.0), fraud_probability)
    risk_level = (
        RiskLevel.CRITICAL
        if risk >= 0.9
        else RiskLevel.HIGH
        if risk >= 0.7
        else RiskLevel.MEDIUM
        if risk >= 0.4
        else RiskLevel.LOW
    )

    if verdict != Verdict.UNCERTAIN and completeness >= 0.6 and confidence >= 0.7:
        readiness = DecisionReadiness.READY
    elif completeness >= 0.45:
        readiness = DecisionReadiness.PARTIALLY_READY
    else:
        readiness = DecisionReadiness.NOT_READY

    hypotheses = [
        f"{result.pattern.value}: {result.status.value} ({result.confidence:.2f})"
        for result in sorted(pattern_results, key=lambda item: item.confidence, reverse=True)
        if result.status != PatternStatus.NOT_DETECTED
    ][:3]

    return UncertaintyAssessment(
        risk=round(risk, 2),
        confidence=round(confidence, 2),
        evidence_completeness=round(completeness, 2),
        contradictions=contradictions,
        decision_readiness=readiness,
        risk_level=risk_level,
        missing_evidence=sorted(set(missing)),
        weak_evidence=sum(1 for result in candidates if result.confidence < 0.5),
        hypotheses=hypotheses,
    )
