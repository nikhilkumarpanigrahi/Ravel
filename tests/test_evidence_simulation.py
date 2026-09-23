"""Tests that simulated evidence is transparent and hypothesis-independent."""

from ravel.application.evidence_simulation import simulate_customer_response
from ravel.domain.enums import TriggerType


def test_customer_report_followup_reaffirms_supplied_report():
    response = simulate_customer_response(
        trigger_type=TriggerType.CUSTOMER_REPORT,
        trigger_text="I never made this purchase",
        is_recurring=False,
    )
    assert "never made" in response


def test_risk_trigger_defaults_to_neutral_no_response():
    response = simulate_customer_response(
        trigger_type=TriggerType.RISK_SCORE,
        trigger_text="Model score 0.92",
        is_recurring=False,
    )
    assert "No reply" in response
    assert "denied" not in response


def test_recurring_charge_response_is_based_on_observed_recurrence():
    response = simulate_customer_response(
        trigger_type=TriggerType.RISK_SCORE,
        trigger_text="Model score 0.70",
        is_recurring=True,
    )
    assert "recurring" in response
    assert "legitimate" in response
