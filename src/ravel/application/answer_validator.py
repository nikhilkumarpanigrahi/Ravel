"""Submission-safety validation for generated benchmark answer files."""

from __future__ import annotations

from ravel.domain.case import AnswerFile
from ravel.domain.enums import ActionType, ApprovalRoute, ApprovalState, Verdict


class AnswerValidationError(ValueError):
    """Raised when an answer file is internally inconsistent or incomplete."""


def validate_answer(answer: AnswerFile) -> None:
    """Reject contradictory outputs before they can become benchmark artifacts."""
    errors: list[str] = []
    case = answer.case
    final_actions = answer.next_best_actions.get("final", [])

    if answer.case_id != case.case_id:
        errors.append("top-level case_id does not match case.case_id")

    action_names = {str(action.get("action", "")) for action in final_actions}
    if case.verdict == Verdict.FRAUD and ActionType.CLOSE_NO_FRAUD.value in action_names:
        errors.append("fraud verdict cannot end with CLOSE_NO_FRAUD")
    if case.verdict == Verdict.LEGITIMATE:
        forbidden = {
            ActionType.BLOCK_CARD.value,
            ActionType.BLOCK_ALL_CARDS.value,
            ActionType.FILE_REPORT.value,
        }
        contradictory = sorted(action_names & forbidden)
        if contradictory:
            errors.append(f"legitimate verdict has punitive actions: {', '.join(contradictory)}")

    for action in final_actions:
        route = str(action.get("route", "auto"))
        requires_approval = bool(action.get("requires_approval", False))
        state = str(action.get("state", ApprovalState.NOT_REQUIRED.value))
        approval_id = str(action.get("approval_id", ""))
        if route in {ApprovalRoute.L1.value, ApprovalRoute.L2.value}:
            if not requires_approval:
                errors.append(f"{action.get('action')} on {route} must require approval")
            if state not in {
                ApprovalState.PENDING.value,
                ApprovalState.APPROVED.value,
                ApprovalState.REJECTED.value,
            }:
                errors.append(f"{action.get('action')} on {route} has invalid state {state}")
            if not approval_id:
                errors.append(f"{action.get('action')} on {route} is missing approval_id")
        elif requires_approval or state != ApprovalState.NOT_REQUIRED.value:
            errors.append(f"auto action {action.get('action')} has governed approval metadata")

    if answer.sar.file and ActionType.FILE_REPORT.value not in action_names:
        errors.append("SAR is marked for filing without FILE_REPORT in final actions")
    if ActionType.FILE_REPORT.value in action_names and not answer.sar.file:
        errors.append("FILE_REPORT is recommended but SAR file is false")
    if case.written_to_graph and not case.graph_case_id:
        errors.append("case claims graph write without graph_case_id")
    if len(case.affected_txn_ids) != len(set(case.affected_txn_ids)):
        errors.append("affected_txn_ids contains duplicates")
    if case.exposure_usd < 0:
        errors.append("exposure_usd cannot be negative")

    assumed_responses = " ".join(
        str(request.get("assumed_response", "")) for request in answer.evidence_requests
    ).lower()
    customer_unreachable = any(
        term in assumed_responses for term in ("no reply", "timeout", "unreachable", "unverified")
    )
    if customer_unreachable:
        narrative = " ".join(
            [
                str(answer.next_best_actions.get("what_changed", "")),
                *(str(action.get("reason", "")) for action in final_actions),
            ]
        ).lower()
        if "customer denied" in narrative or "confirmed unauthorized" in narrative:
            errors.append("no-response assumption cannot be described as a customer denial")

    pending_actions = {
        str(action.get("action", ""))
        for action in final_actions
        if str(action.get("state", "")) == ApprovalState.PENDING.value
    }
    sar_narrative = answer.sar.narrative.lower()
    if ActionType.BLOCK_CARD.value in pending_actions and any(
        phrase in sar_narrative for phrase in ("has been blocked", "card blocked", "blocked and reissued")
    ):
        errors.append("SAR describes a pending card block as already executed")

    if errors:
        raise AnswerValidationError(f"{answer.case_id}: " + "; ".join(errors))
