from ravel.application.counterfactual import CounterfactualActionOptimizer
from ravel.domain.enums import ActionType, ApprovalRoute


def test_counterfactual_action_optimizer_high_fraud():
    optimizer = CounterfactualActionOptimizer()
    candidate_actions = [
        {"action": ActionType.BLOCK_CARD.value, "route": ApprovalRoute.L1.value, "target": "card-123"},
        {"action": ActionType.STEP_UP_AUTH.value, "route": ApprovalRoute.AUTO.value, "target": "txn-456"},
        {"action": ActionType.MONITOR_CARD.value, "route": ApprovalRoute.AUTO.value, "target": "card-123"},
    ]

    # When fraud probability is high (0.90) and exposure is $5,000
    results = optimizer.evaluate_candidates(
        candidate_actions=candidate_actions,
        fraud_probability=0.90,
        exposure_usd=5000.0,
        sar_required=False,
    )

    assert len(results) == 3
    # BLOCK_CARD should stop 100% of fraud ($4,500 expected loss prevented) and have highest utility
    block_res = next(r for r in results if r.action_type == ActionType.BLOCK_CARD)
    assert block_res.loss_prevented_usd == 4500.0
    assert block_res.pareto_optimal is True


def test_counterfactual_action_optimizer_low_fraud():
    optimizer = CounterfactualActionOptimizer()
    candidate_actions = [
        {"action": ActionType.BLOCK_CARD.value, "route": ApprovalRoute.L1.value, "target": "card-123"},
        {"action": ActionType.MONITOR_CARD.value, "route": ApprovalRoute.AUTO.value, "target": "card-123"},
    ]

    # When fraud probability is low (0.05) and exposure is $50
    results = optimizer.evaluate_candidates(
        candidate_actions=candidate_actions,
        fraud_probability=0.05,
        exposure_usd=50.0,
        sar_required=False,
    )

    # Passive monitoring should outperform blocking because blocking incurs high false-friction penalty
    monitor_res = next(r for r in results if r.action_type == ActionType.MONITOR_CARD)
    block_res = next(r for r in results if r.action_type == ActionType.BLOCK_CARD)
    assert monitor_res.net_utility_score > block_res.net_utility_score
