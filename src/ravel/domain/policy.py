"""Policy, approval, and next-best-action domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ravel.domain.enums import ActionType, ApprovalRoute, ApprovalState


class RecommendedAction(BaseModel):
    """One recommended action from the policy engine."""

    action: ActionType
    route: ApprovalRoute
    reason: str = ""
    order: int = 0
    requires_approval: bool = False
    state: ApprovalState = ApprovalState.NOT_REQUIRED


class PolicyEvaluation(BaseModel):
    allowed: bool = True
    approved: bool = False
    requires_approval: bool = False
    route: ApprovalRoute = ApprovalRoute.AUTO
    required_evidence: list[str] = Field(default_factory=list)
    policy_version: str = "1.0"
    rationale: str = ""
    citations: list[str] = Field(default_factory=list)


class ApprovalRecord(BaseModel):
    approval_id: str = ""
    action: ActionType
    case_id: str = ""
    route: ApprovalRoute
    state: ApprovalState = ApprovalState.PENDING
    requestor: str = "agent"
    approver: str = ""
    requested_at: str = ""
    decided_at: str = ""
    decision_reason: str = ""
    policy_version: str = "1.0"


class NextBestActions(BaseModel):
    """Part 3 of the answer file."""

    initial: list[RecommendedAction] = Field(default_factory=list)
    final: list[RecommendedAction] = Field(default_factory=list)
    what_changed: str = "nothing"


class ActionExecution(BaseModel):
    action_id: str = ""
    action: ActionType
    case_id: str = ""
    executed: bool = False
    simulated: bool = True
    audit_entry: str = ""
    result: str = ""
