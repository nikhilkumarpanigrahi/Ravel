"""Counterfactual Action Optimizer for Fraud Forensics.

Simulates what-if outcomes across alternative candidate intervention actions:
- Expected financial loss prevented ($)
- Customer friction and churn penalty ($)
- Regulatory compliance / SAR non-filing exposure risk ($)
- Net Expected Utility (NEU) calculation for policy recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ravel.domain.enums import ActionType, ApprovalRoute


@dataclass(frozen=True)
class ActionSimulationResult:
    action_type: ActionType
    action_id: str
    target: str
    route: ApprovalRoute
    loss_prevented_usd: float
    customer_friction_cost_usd: float
    compliance_risk_penalty_usd: float
    net_utility_score: float
    pareto_optimal: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "action_id": self.action_id,
            "target": self.target,
            "route": self.route.value,
            "loss_prevented_usd": round(self.loss_prevented_usd, 2),
            "customer_friction_cost_usd": round(self.customer_friction_cost_usd, 2),
            "compliance_risk_penalty_usd": round(self.compliance_risk_penalty_usd, 2),
            "net_utility_score": round(self.net_utility_score, 2),
            "pareto_optimal": self.pareto_optimal,
            "rationale": self.rationale,
        }


class CounterfactualActionOptimizer:
    """Optimizes next-best action selection using counterfactual decision theory."""

    # Estimated costs of customer friction (e.g. false decline, card replacement friction)
    FRICTION_COSTS = {
        ActionType.BLOCK_CARD: 45.0,
        ActionType.BLOCK_ALL_CARDS: 65.0,
        ActionType.DECLINE_TRANSACTION: 20.0,
        ActionType.STEP_UP_AUTH: 5.0,
        ActionType.WARN_CUSTOMER: 6.0,
        ActionType.VERIFY_WITH_CUSTOMER: 8.0,
        ActionType.MONITOR_CARD: 0.0,
        ActionType.MONITOR_CONNECTED_CARDS: 0.0,
        ActionType.ALLOW_TRANSACTION: 0.0,
        ActionType.CLOSE_NO_FRAUD: 0.0,
        ActionType.GENERATE_REPORT: 5.0,
        ActionType.CREATE_CASE: 10.0,
        ActionType.FILE_REPORT: 15.0,
        ActionType.ESCALATE_TO_ANALYST: 25.0,
    }

    # Efficacy / Loss prevention percentage if the activity is genuinely fraudulent
    EFFICACY_RATES = {
        ActionType.BLOCK_CARD: 1.0,
        ActionType.BLOCK_ALL_CARDS: 1.0,
        ActionType.DECLINE_TRANSACTION: 0.95,
        ActionType.STEP_UP_AUTH: 0.80,
        ActionType.WARN_CUSTOMER: 0.60,
        ActionType.VERIFY_WITH_CUSTOMER: 0.75,
        ActionType.MONITOR_CARD: 0.20,
        ActionType.MONITOR_CONNECTED_CARDS: 0.25,
        ActionType.ALLOW_TRANSACTION: 0.0,
        ActionType.CLOSE_NO_FRAUD: 0.0,
        ActionType.GENERATE_REPORT: 0.0,
        ActionType.CREATE_CASE: 0.10,
        ActionType.FILE_REPORT: 0.0,
        ActionType.ESCALATE_TO_ANALYST: 0.50,
    }

    def evaluate_candidates(
        self,
        candidate_actions: list[dict[str, Any]],
        fraud_probability: float,
        exposure_usd: float,
        sar_required: bool = False,
    ) -> list[ActionSimulationResult]:
        """Run counterfactual simulation across all proposed candidate actions."""
        p_fraud = max(0.0, min(1.0, fraud_probability))
        p_legit = 1.0 - p_fraud
        results: list[ActionSimulationResult] = []

        for candidate in candidate_actions:
            action_type_val = candidate.get("action", candidate.get("action_type", "MONITOR_CARD"))
            try:
                action_type = ActionType(action_type_val)
            except ValueError:
                action_type = ActionType.MONITOR_CARD

            target = candidate.get("target", candidate.get("reason", ""))
            action_id = candidate.get("approval_id") or candidate.get("action_id", f"ACT-{action_type.value}")
            route_val = candidate.get("route", "auto")
            try:
                route = ApprovalRoute(route_val)
            except ValueError:
                route = ApprovalRoute.AUTO

            # 1. Expected Loss Prevented
            efficacy = self.EFFICACY_RATES.get(action_type, 0.5)
            expected_loss_prevented = p_fraud * exposure_usd * efficacy

            # 2. Customer Friction Cost (penalized if customer was actually legitimate)
            base_friction = self.FRICTION_COSTS.get(action_type, 10.0)
            expected_friction_cost = p_legit * base_friction

            # 3. Compliance Risk Penalty (e.g. failing to file when required)
            compliance_risk_penalty = 0.0
            if sar_required and action_type not in {ActionType.FILE_REPORT, ActionType.GENERATE_REPORT}:
                compliance_risk_penalty = 50.0

            # 4. Net Utility Score = Benefits - Costs
            net_utility = expected_loss_prevented - expected_friction_cost - compliance_risk_penalty

            # Rationale formulation
            if p_fraud >= 0.7:
                rationale = (
                    f"High fraud risk ({p_fraud:.2f}): {action_type.value} prevents estimated "
                    f"${expected_loss_prevented:.2f} with acceptable friction (${expected_friction_cost:.2f})."
                )
            elif p_fraud <= 0.2:
                rationale = (
                    f"Low fraud risk ({p_fraud:.2f}): Heavy intervention creates unwarranted friction "
                    f"(${expected_friction_cost:.2f}); monitoring or closing alert favored."
                )
            else:
                rationale = f"Moderate uncertainty ({p_fraud:.2f}): Balanced trade-off yields net utility {net_utility:.2f}."

            results.append(
                ActionSimulationResult(
                    action_type=action_type,
                    action_id=action_id,
                    target=target,
                    route=route,
                    loss_prevented_usd=expected_loss_prevented,
                    customer_friction_cost_usd=expected_friction_cost,
                    compliance_risk_penalty_usd=compliance_risk_penalty,
                    net_utility_score=net_utility,
                    pareto_optimal=False,  # Evaluated below
                    rationale=rationale,
                )
            )

        if not results:
            return []

        # Determine Pareto optimality: highest net utility or best loss/friction trade-off
        max_utility = max(r.net_utility_score for r in results)
        updated_results: list[ActionSimulationResult] = []
        for r in results:
            is_pareto = r.net_utility_score >= max_utility - 5.0
            updated_results.append(
                ActionSimulationResult(
                    action_type=r.action_type,
                    action_id=r.action_id,
                    target=r.target,
                    route=r.route,
                    loss_prevented_usd=r.loss_prevented_usd,
                    customer_friction_cost_usd=r.customer_friction_cost_usd,
                    compliance_risk_penalty_usd=r.compliance_risk_penalty_usd,
                    net_utility_score=r.net_utility_score,
                    pareto_optimal=is_pareto,
                    rationale=r.rationale,
                )
            )

        updated_results.sort(key=lambda x: x.net_utility_score, reverse=True)
        return updated_results
