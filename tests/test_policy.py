"""Unit tests for PolicyEngine and approval routing."""

from ravel.application.policy_engine import PolicyEngine
from ravel.domain.enums import ActionType, ApprovalRoute, ApprovalState, FraudPattern, Verdict


def test_approval_routing():
    engine = PolicyEngine()
    # Decline is L1
    assert engine.determine_approval_route(ActionType.DECLINE_TRANSACTION) == ApprovalRoute.L1

    # Block <= 2500 is L1
    assert engine.determine_approval_route(ActionType.BLOCK_CARD, 1500.0) == ApprovalRoute.L1

    # Block > 2500 is L2
    assert engine.determine_approval_route(ActionType.BLOCK_CARD, 3500.0) == ApprovalRoute.L2

    # File report is always L2
    assert engine.determine_approval_route(ActionType.FILE_REPORT) == ApprovalRoute.L2

    # Close case / verify is auto
    assert engine.determine_approval_route(ActionType.CLOSE_NO_FRAUD) == ApprovalRoute.AUTO
    assert engine.determine_approval_route(ActionType.VERIFY_WITH_CUSTOMER) == ApprovalRoute.AUTO


def test_recommended_actions_derive_approval_metadata():
    engine = PolicyEngine()
    actions = engine.evaluate_final_actions(
        verdict=Verdict.FRAUD,
        final_fraud_prob=0.95,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD,
        exposure_usd=1500.0,
        customer_response="Customer denied making this purchase",
        has_shared_device=False,
        connected_card_ids=[],
    )
    block = next(action for action in actions if action.action == ActionType.BLOCK_CARD)
    create_case = next(action for action in actions if action.action == ActionType.CREATE_CASE)
    assert block.requires_approval is True
    assert block.state == ApprovalState.PENDING
    assert create_case.requires_approval is False
    assert create_case.state == ApprovalState.NOT_REQUIRED


def test_rule_r1_weak_signal():
    engine = PolicyEngine()
    actions = engine.evaluate_initial_actions(
        verdict=Verdict.UNCERTAIN,
        fraud_prob=0.45,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD,
        exposure_usd=200.0,
        signals_count=1,
        has_shared_device=False,
        is_recurring=False,
    )
    action_types = [a.action for a in actions]
    assert ActionType.VERIFY_WITH_CUSTOMER in action_types
    assert ActionType.BLOCK_CARD not in action_types  # Must not block on single weak signal


def test_rule_r2_customer_denial():
    engine = PolicyEngine()
    actions = engine.evaluate_final_actions(
        verdict=Verdict.FRAUD,
        final_fraud_prob=0.95,
        pattern=FraudPattern.CARD_NOT_PRESENT_FRAUD,
        exposure_usd=1500.0,
        customer_response="Customer denied making this purchase",
        has_shared_device=True,
        connected_card_ids=["C12345-K2"],
    )
    action_types = [a.action for a in actions]
    assert ActionType.BLOCK_CARD in action_types
    assert ActionType.CREATE_CASE in action_types
    assert ActionType.FILE_REPORT in action_types  # Exposure > 1000 & shared device
    assert ActionType.MONITOR_CONNECTED_CARDS in action_types


def test_rule_r3_customer_confirmation():
    engine = PolicyEngine()
    actions = engine.evaluate_final_actions(
        verdict=Verdict.LEGITIMATE,
        final_fraud_prob=0.05,
        pattern=FraudPattern.NONE,
        exposure_usd=0.0,
        customer_response="Customer confirmed transaction as legitimate cardholder activity",
        has_shared_device=False,
        connected_card_ids=[],
    )
    assert len(actions) == 1
    assert actions[0].action == ActionType.CLOSE_NO_FRAUD
    assert actions[0].route == ApprovalRoute.AUTO
