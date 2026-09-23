"""Transparent, hypothesis-independent evidence simulation for benchmark/demo runs."""

from __future__ import annotations

from ravel.domain.enums import TriggerType


def simulate_customer_response(
    *,
    trigger_type: TriggerType,
    trigger_text: str,
    is_recurring: bool,
) -> str:
    """Return an explicit assumption without using the predicted fraud pattern or verdict."""
    if trigger_type == TriggerType.CUSTOMER_REPORT:
        return f"Customer reaffirmed the original report: '{trigger_text}'"
    if is_recurring:
        return "Customer recognized the recurring subscription charge and confirmed it as legitimate"
    return "No reply received within 24 hours; ownership remains unverified"
