"""Agentic Investigation Engine: Autonomous evidence-acquisition loop.

Executes a principled active-learning investigation loop:
Hypothesis -> Measure Missing Evidence & Entropy -> Select Best Tool (EIG / VoI) ->
Retrieve Graph Evidence -> Bayesian Belief Update -> Check Stopping Criteria -> Decide.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from ravel.application.evidence_value_optimizer import EvidenceValueOptimizer
from ravel.domain.enums import EvidenceSource, EvidenceType, TriggerType
from ravel.domain.evidence import EvidenceRecord
from ravel.infrastructure.graph.base import GraphAdapter

logger = logging.getLogger("ravel.agentic_engine")


def logit(p: float) -> float:
    p_clamped = min(0.999, max(0.001, p))
    return math.log(p_clamped / (1.0 - p_clamped))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class AgenticInvestigationEngine:
    """Autonomous agentic investigator implementing the hypothesis-driven evidence loop."""

    def __init__(self, graph: GraphAdapter, optimizer: EvidenceValueOptimizer | None = None):
        self.graph = graph
        self.optimizer = optimizer or EvidenceValueOptimizer()

    def run_agentic_loop(
        self,
        case_id: str,
        customer_id: str,
        card_id: str,
        flagged_txn_id: str,
        trigger_type: TriggerType,
        risk_score: float | None = None,
        exposure_usd: float = 0.0,
        has_device: bool = True,
        max_steps: int = 4,
    ) -> tuple[float, list[EvidenceRecord], list[dict[str, Any]]]:
        """Execute the active evidence-acquisition loop.

        Returns:
            (final_belief_probability, collected_evidence, agent_reasoning_trace)
        """
        # 1. Hypothesis Initialization
        if trigger_type == TriggerType.CUSTOMER_REPORT:
            prior_belief = 0.82
            initial_hypothesis = f"Cardholder {customer_id} reports unauthorized transaction {flagged_txn_id} (Presumed CNP fraud)"
        elif trigger_type == TriggerType.ANALYST_REQUEST:
            prior_belief = 0.70
            initial_hypothesis = (
                f"Analyst inquiry: syndicated device profile suspected on txn {flagged_txn_id}"
            )
        else:
            base_score = risk_score if risk_score is not None else 0.50
            prior_belief = min(0.85, max(0.15, base_score))
            initial_hypothesis = f"Model alert on txn {flagged_txn_id} (Risk score: {prior_belief:.2f}): evaluate fraud vs legitimate use"

        current_belief = prior_belief
        evidence_ledger: list[EvidenceRecord] = []
        agent_trace: list[dict[str, Any]] = []
        executed_tools: set[str] = set()

        for step in range(1, max_steps + 1):
            h_prior = self.optimizer.binary_entropy(current_belief)

            # Stopping condition: high certainty (low entropy)
            if h_prior < 0.22 and step > 1:
                agent_trace.append(
                    {
                        "step": step,
                        "action": "HALT_INVESTIGATION",
                        "reason": f"Information entropy H(S)={h_prior:.3f} below threshold (0.22 bits). Decision readiness achieved.",
                        "final_belief": round(current_belief, 3),
                    }
                )
                break

            # 2. Rank Next Best Tool by Value of Information
            ranked_inquiries = self.optimizer.rank_evidence_inquiries(
                current_fraud_prob=current_belief,
                exposure_usd=exposure_usd,
                customer_id=customer_id,
                txn_id=flagged_txn_id,
                has_device=has_device,
            )

            # Execute passive, controlled graph tools only. Customer contact and
            # human review belong to the governed evidence-request workflow.
            autonomous_tools = {"DEVICE_REPUTATION_TELEMETRY", "MERCHANT_TERMINAL_AUDIT"}
            chosen_tool = None
            for opt in ranked_inquiries:
                if opt.inquiry_type in autonomous_tools and opt.inquiry_type not in executed_tools:
                    chosen_tool = opt
                    break

            if not chosen_tool:
                break

            executed_tools.add(chosen_tool.inquiry_type)

            # 3. Tool Execution & Graph Telemetry Retrieval
            log_lr = 0.0
            new_evidence: EvidenceRecord | None = None

            if chosen_tool.inquiry_type == "CARDHOLDER_TRANSACTION_VERIFICATION":
                # Simulated inquiry based on trigger context
                if trigger_type == TriggerType.CUSTOMER_REPORT:
                    resp = "Customer stated they never made this purchase and retained possession of card."
                    supports, contradicts = "fraud", "legitimate"
                    log_lr = 2.4  # strong evidence for fraud
                elif prior_belief < 0.40:
                    resp = "Cardholder confirmed transaction as authorized recurring purchase."
                    supports, contradicts = "legitimate", "fraud"
                    log_lr = -2.8  # strong evidence for legitimate
                else:
                    resp = "Cardholder unreached / pending response; initial alert stands."
                    supports, contradicts = "", ""
                    log_lr = 0.2

                new_evidence = EvidenceRecord(
                    case_id=case_id,
                    claim=f"Cardholder verification inquiry: {resp}",
                    source=EvidenceSource.CUSTOMER,
                    ref=f"tool:customer_inquiry({customer_id})",
                    entity_ids=[customer_id, flagged_txn_id],
                    evidence_type=EvidenceType.CUSTOMER_RESPONSE,
                    strength=0.90,
                    confidence=0.85,
                    supports=supports,
                    contradicts=contradicts,
                    tool_used="customer_inquiry",
                    policy_context="Policy R1: Customer transaction verification",
                    graph_path=f"Cardholder({customer_id}) ──[INQUIRY_RESPONSE]──> Txn({flagged_txn_id})",
                )

            elif chosen_tool.inquiry_type == "DEVICE_REPUTATION_TELEMETRY":
                # Query TigerGraph shared devices
                shared_devs = self.graph.shared_devices(customer_id)
                shared_cards = list({r["other_card_id"] for r in shared_devs if r.get("other_card_id")})
                if len(shared_cards) >= 2:
                    claim = f"TigerGraph shared-device traversal identified syndicate: device shared across {len(shared_cards)} distinct cards"
                    supports, contradicts = "fraud", "legitimate"
                    log_lr = 1.6  # syndicate evidence
                else:
                    claim = "Device reputation check: no high-velocity cross-card syndicates detected on this device"
                    supports, contradicts = "legitimate", "fraud"
                    log_lr = -0.6

                new_evidence = EvidenceRecord(
                    case_id=case_id,
                    claim=claim,
                    source=EvidenceSource.GRAPH,
                    ref=f"tigergraph:shared_devices({customer_id})",
                    entity_ids=shared_cards[:5],
                    evidence_type=EvidenceType.DEVICE,
                    strength=0.85,
                    confidence=0.90,
                    supports=supports,
                    contradicts=contradicts,
                    tool_used="tigergraph:shared_devices",
                    policy_context="Policy R2: Shared device syndicate inspection",
                    graph_path=f"Customer({customer_id}) ──[USES_DEVICE]──> Device ──[SHARED_WITH]──> {len(shared_cards)} Cards",
                )

            elif chosen_tool.inquiry_type == "MERCHANT_TERMINAL_AUDIT":
                # Query transaction details from graph
                txn_details = self.graph.get_transaction(flagged_txn_id)
                amt = float(txn_details.get("amount", 0.0))
                channel = str(txn_details.get("channel", "online"))
                claim = (
                    f"Transaction audit: ${amt:.2f} via {channel} (Product {txn_details.get('product_cd')})"
                )
                supports = "fraud" if amt > 300.0 or channel == "online" else "legitimate"
                contradicts = "legitimate" if supports == "fraud" else "fraud"
                log_lr = 0.5 if supports == "fraud" else -0.4

                new_evidence = EvidenceRecord(
                    case_id=case_id,
                    claim=claim,
                    source=EvidenceSource.GRAPH,
                    ref=f"tigergraph:get_txn({flagged_txn_id})",
                    entity_ids=[flagged_txn_id],
                    evidence_type=EvidenceType.TRANSACTION,
                    strength=0.60,
                    confidence=0.95,
                    supports=supports,
                    contradicts=contradicts,
                    tool_used="tigergraph:get_txn",
                    policy_context="Policy R3: Channel & transaction telemetry",
                    graph_path=f"Transaction({flagged_txn_id}) ──[CHANNEL]──> {channel.upper()}",
                )

            if new_evidence:
                evidence_ledger.append(new_evidence)

                # 4. Bayesian Belief Updating
                prior_log_odds = logit(current_belief)
                posterior_log_odds = prior_log_odds + log_lr
                posterior_belief = sigmoid(posterior_log_odds)
                h_post = self.optimizer.binary_entropy(posterior_belief)

                agent_trace.append(
                    {
                        "step": step,
                        "hypothesis": initial_hypothesis,
                        "selected_tool": chosen_tool.inquiry_type,
                        "expected_info_gain": round(chosen_tool.expected_info_gain_bits, 3),
                        "value_of_information": round(chosen_tool.value_of_information, 2),
                        "evidence_claim": new_evidence.claim,
                        "evidence_supports": new_evidence.supports,
                        "evidence_contradicts": new_evidence.contradicts,
                        "prior_belief": round(current_belief, 3),
                        "posterior_belief": round(posterior_belief, 3),
                        "entropy_reduction": round(max(0.0, h_prior - h_post), 3),
                    }
                )
                current_belief = posterior_belief

        return round(current_belief, 3), evidence_ledger, agent_trace
