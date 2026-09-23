"""Deterministic Policy Engine enforcing Fraud Policy Version 1.0 (Rules R1-R10)."""

from __future__ import annotations

from ravel.domain.case import SAR
from ravel.domain.enums import ActionType, ApprovalRoute, FraudPattern, Verdict
from ravel.domain.policy import NextBestActions, RecommendedAction


class PolicyEngine:
    """Evaluates investigation findings against bank fraud policy and approval routing."""

    @staticmethod
    def determine_approval_route(action: ActionType, exposure_usd: float = 0.0) -> ApprovalRoute:
        """Section 2: Approval routing table."""
        if action == ActionType.DECLINE_TRANSACTION:
            return ApprovalRoute.L1
        if action == ActionType.BLOCK_CARD:
            return ApprovalRoute.L1 if exposure_usd <= 2500.0 else ApprovalRoute.L2
        if action in (ActionType.BLOCK_ALL_CARDS, ActionType.FILE_REPORT):
            return ApprovalRoute.L2
        return ApprovalRoute.AUTO

    def evaluate_initial_actions(
        self,
        verdict: Verdict,
        fraud_prob: float,
        pattern: FraudPattern,
        exposure_usd: float,
        signals_count: int,
        has_shared_device: bool,
        is_recurring: bool,
        cleared_over_100: bool = False,
    ) -> list[RecommendedAction]:
        """Determine initial recommended actions BEFORE external evidence requests."""
        actions: list[RecommendedAction] = []

        # R7: Disputed but legitimate recurring charge
        if is_recurring:
            actions.append(
                RecommendedAction(
                    action=ActionType.CREATE_CASE,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Disputed charge matches recurring historical merchant pattern",
                    order=1,
                )
            )
            actions.append(
                RecommendedAction(
                    action=ActionType.VERIFY_WITH_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Verify whether cardholder recalls recurring billing agreement",
                    order=2,
                )
            )
            actions.append(
                RecommendedAction(
                    action=ActionType.WARN_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Send recurring charge advisory notice",
                    order=3,
                )
            )
            return actions

        # R5: Card testing pattern detected
        if pattern == FraudPattern.CARD_TESTING:
            actions.append(
                RecommendedAction(
                    action=ActionType.DECLINE_TRANSACTION,
                    route=ApprovalRoute.L1,
                    reason="R5: Card testing sequence identified, decline pending authorization",
                    order=1,
                )
            )
            if cleared_over_100:
                route = self.determine_approval_route(ActionType.BLOCK_CARD, exposure_usd)
                actions.append(
                    RecommendedAction(
                        action=ActionType.BLOCK_CARD,
                        route=route,
                        reason=f"R5: Testing sequence followed by cleared purchase over $100 (exposure ${exposure_usd:.2f})",
                        order=2,
                    )
                )
            else:
                actions.append(
                    RecommendedAction(
                        action=ActionType.STEP_UP_AUTH,
                        route=ApprovalRoute.AUTO,
                        reason="R5: Require step-up authentication on further activity",
                        order=2,
                    )
                )
            actions.append(
                RecommendedAction(
                    action=ActionType.VERIFY_WITH_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason="R1: Confirm unauthorized status before complete card termination",
                    order=3,
                )
            )
            return actions

        # R1: Verify before block on weak signal (prob < 0.70 or single signal)
        if fraud_prob < 0.70 or signals_count <= 1:
            if fraud_prob >= 0.30:
                actions.append(
                    RecommendedAction(
                        action=ActionType.CREATE_CASE,
                        route=ApprovalRoute.AUTO,
                        reason="Section 3a: Open internal fraud case as probability reaches threshold",
                        order=1,
                    )
                )
            actions.append(
                RecommendedAction(
                    action=ActionType.VERIFY_WITH_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason=f"R1: Single signal / probability {fraud_prob:.2f} < 0.70; verify before blocking",
                    order=2,
                )
            )
            actions.append(
                RecommendedAction(
                    action=ActionType.MONITOR_CARD,
                    route=ApprovalRoute.AUTO,
                    reason="Policy 1: Card remains active under heightened 72-hour monitoring pending reply",
                    order=3,
                )
            )
            return actions

        # Strong signal (> 0.70) initial recommendation
        route = self.determine_approval_route(ActionType.BLOCK_CARD, exposure_usd)
        actions.append(
            RecommendedAction(
                action=ActionType.BLOCK_CARD,
                route=route,
                reason=f"Policy 1: High fraud probability {fraud_prob:.2f} on pattern {pattern.value}",
                order=1,
            )
        )
        actions.append(
            RecommendedAction(
                action=ActionType.CREATE_CASE,
                route=ApprovalRoute.AUTO,
                reason="Section 3a: Internal fraud case record",
                order=2,
            )
        )
        if has_shared_device or exposure_usd > 1000.0:
            actions.append(
                RecommendedAction(
                    action=ActionType.FILE_REPORT,
                    route=ApprovalRoute.L2,
                    reason=f"Section 3a & R6: Exposure ${exposure_usd:.2f} > $1,000 or shared infrastructure",
                    order=3,
                )
            )
        return actions

    def evaluate_final_actions(
        self,
        verdict: Verdict,
        final_fraud_prob: float,
        pattern: FraudPattern,
        exposure_usd: float,
        customer_response: str,
        has_shared_device: bool,
        connected_card_ids: list[str],
        is_recurring: bool = False,
    ) -> list[RecommendedAction]:
        """Determine final recommended actions AFTER requested evidence is received."""
        actions: list[RecommendedAction] = []
        cust_norm = customer_response.lower()
        is_denial = any(term in cust_norm for term in ("deni", "never made", "stolen", "unauthorized"))
        is_confirmation = (
            any(term in cust_norm for term in ("confirm", "legitimate", "made this purchase"))
            and not is_denial
        )

        # R3: Customer confirms transaction
        if is_confirmation:
            actions.append(
                RecommendedAction(
                    action=ActionType.CLOSE_NO_FRAUD,
                    route=ApprovalRoute.AUTO,
                    reason="R3: Customer confirmed transaction as legitimate cardholder activity",
                    order=1,
                )
            )
            return actions

        # R7: Disputed recurring
        if is_recurring and ("recurring" in cust_norm or "subscription" in cust_norm):
            actions.append(
                RecommendedAction(
                    action=ActionType.CREATE_CASE,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Case recorded for merchant billing dispute",
                    order=1,
                )
            )
            actions.append(
                RecommendedAction(
                    action=ActionType.WARN_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Merchant cancellation advice provided to customer",
                    order=2,
                )
            )
            return actions

        # R2: Customer denies transaction (or confirmed fraud)
        if is_denial or verdict == Verdict.FRAUD:
            route = self.determine_approval_route(ActionType.BLOCK_CARD, exposure_usd)
            actions.append(
                RecommendedAction(
                    action=ActionType.BLOCK_CARD,
                    route=route,
                    reason=f"R2: Customer denied activity; card compromised (exposure ${exposure_usd:.2f})",
                    order=1,
                )
            )
            actions.append(
                RecommendedAction(
                    action=ActionType.CREATE_CASE,
                    route=ApprovalRoute.AUTO,
                    reason="R2 and Section 3a: Internal fraud case record with graph persistence",
                    order=2,
                )
            )
            if exposure_usd > 1000.0 or has_shared_device or pattern == FraudPattern.UNDOCUMENTED:
                actions.append(
                    RecommendedAction(
                        action=ActionType.FILE_REPORT,
                        route=ApprovalRoute.L2,
                        reason="R2 & R6: Exposure exceeds $1,000, shared device cluster, or coordinated pattern",
                        order=3,
                    )
                )
            if connected_card_ids:
                actions.append(
                    RecommendedAction(
                        action=ActionType.MONITOR_CONNECTED_CARDS,
                        route=ApprovalRoute.AUTO,
                        reason=f"R6: Monitor {len(connected_card_ids)} connected card(s) linked via shared infrastructure",
                        order=4,
                    )
                )
            return actions

        # R4: No response / timed out
        if "no reply" in cust_norm or "timeout" in cust_norm or "unreachable" in cust_norm:
            actions.append(
                RecommendedAction(
                    action=ActionType.MONITOR_CARD,
                    route=ApprovalRoute.AUTO,
                    reason="R4: Customer uncontactable, heighten card monitoring for 72 hours",
                    order=1,
                )
            )
            actions.append(
                RecommendedAction(
                    action=ActionType.DECLINE_TRANSACTION,
                    route=ApprovalRoute.L1,
                    reason="R4: Decline pending authorization until cardholder responds",
                    order=2,
                )
            )
            if exposure_usd > 500.0:
                actions.append(
                    RecommendedAction(
                        action=ActionType.ESCALATE_TO_ANALYST,
                        route=ApprovalRoute.AUTO,
                        reason="R4: Exposure > $500 with unverified cardholder activity",
                        order=3,
                    )
                )
            return actions

        # R8: Uncertain & exposed
        if verdict == Verdict.UNCERTAIN:
            if exposure_usd > 500.0:
                actions.append(
                    RecommendedAction(
                        action=ActionType.ESCALATE_TO_ANALYST,
                        route=ApprovalRoute.AUTO,
                        reason=f"R8: Uncertain verdict with exposure ${exposure_usd:.2f} > $500",
                        order=1,
                    )
                )
            actions.append(
                RecommendedAction(
                    action=ActionType.MONITOR_CARD,
                    route=ApprovalRoute.AUTO,
                    reason="Policy 1: Monitor card pending human review",
                    order=2,
                )
            )
            return actions

        # Default legitimate
        actions.append(
            RecommendedAction(
                action=ActionType.ALLOW_TRANSACTION,
                route=ApprovalRoute.AUTO,
                reason="Policy: Evidence indicates legitimate cardholder activity",
                order=1,
            )
        )
        return actions

    def assemble_nba(
        self,
        initial: list[RecommendedAction],
        final: list[RecommendedAction],
        what_changed: str,
    ) -> NextBestActions:
        return NextBestActions(initial=initial, final=final, what_changed=what_changed)

    def generate_sar(
        self,
        final_actions: list[RecommendedAction],
        case_id: str,
        customer_id: str,
        card_id: str,
        pattern: FraudPattern,
        exposure_usd: float,
        affected_txn_ids: list[str],
        connected_cards: list[str],
        device_profiles: list[str],
        activity_dates: list[str],
        customer_response: str,
        summary: str,
    ) -> SAR:
        """Part 2: Suspicious Activity Report regulatory filing."""
        file_report = any(a.action == ActionType.FILE_REPORT for a in final_actions)
        if not file_report:
            return SAR(
                file=False,
                reason="Policy criteria for regulatory filing not met (exposure <= $1,000 and no multi-card link)",
                narrative="",
                subjects=[],
                total_amount_usd=0.0,
                activity_dates=[],
            )

        # Subjects
        subjects = [customer_id, card_id] + connected_cards
        subjects = sorted(list({s for s in subjects if s}))

        # Dates
        dates = activity_dates if activity_dates else ["2016-11-01", "2016-12-31"]

        # Narrative
        dev_text = (
            f" Activity originated from device profile ({device_profiles[0]})." if device_profiles else ""
        )
        conn_text = (
            f" Investigation uncovered common infrastructure links to connected card(s) {', '.join(connected_cards)}."
            if connected_cards
            else ""
        )
        cust_text = (
            f" Customer was contacted and reported: '{customer_response}'." if customer_response else ""
        )

        narrative = (
            f"Between {dates[0]} and {dates[-1]}, account {customer_id} on card {card_id} was subjected to "
            f"unauthorized fraudulent activity consistent with {pattern.value.replace('_', ' ')}. "
            f"A total of {len(affected_txn_ids)} transaction(s) were flagged, representing an aggregate exposure of "
            f"${exposure_usd:.2f} USD.{dev_text}{conn_text}{cust_text} "
            f"The pattern of unauthorized transactions diverges significantly from cardholder historical profile. "
            f"Based on regulatory guidelines under FinCEN and bank fraud policy R2/R6, the card has been blocked and "
            f"reissued, connected entities placed under heightened monitoring, and this report is submitted to document the illicit financial activity."
        )

        reason = (
            f"R2/R6: Confirmed unauthorized activity under {pattern.value} with exposure of ${exposure_usd:.2f} USD"
            + (f" linking to {len(connected_cards)} other card(s)" if connected_cards else "")
        )

        return SAR(
            file=True,
            reason=reason,
            narrative=narrative,
            subjects=subjects,
            total_amount_usd=round(exposure_usd, 2),
            activity_dates=dates,
        )
