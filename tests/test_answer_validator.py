"""Tests for benchmark output consistency validation."""

import pytest

from ravel.application.answer_validator import AnswerValidationError, validate_answer
from ravel.domain.case import AnswerFile, Case
from ravel.domain.enums import CaseStatus, FraudPattern, Verdict


def _answer(verdict: Verdict, actions: list[dict]) -> AnswerFile:
    return AnswerFile(
        case_id="HHG-TEST",
        case=Case(
            case_id="HHG-TEST",
            status=CaseStatus.CLOSED_FRAUD
            if verdict == Verdict.FRAUD
            else CaseStatus.CLOSED_LEGITIMATE,
            verdict=verdict,
            pattern=FraudPattern.NONE,
            written_to_graph=True,
            graph_case_id="CASE-TEST",
        ),
        next_best_actions={"initial": [], "final": actions, "what_changed": "test"},
    )


def test_rejects_fraud_closed_as_no_fraud():
    answer = _answer(
        Verdict.FRAUD,
        [
            {
                "action": "CLOSE_NO_FRAUD",
                "route": "auto",
                "requires_approval": False,
                "state": "NOT_REQUIRED",
            }
        ],
    )
    with pytest.raises(AnswerValidationError, match="fraud verdict"):
        validate_answer(answer)


def test_accepts_governed_action_with_pending_approval():
    answer = _answer(
        Verdict.FRAUD,
        [
            {
                "action": "BLOCK_CARD",
                "route": "L1",
                "approval_id": "APP-TEST",
                "requires_approval": True,
                "state": "PENDING",
            }
        ],
    )
    validate_answer(answer)
