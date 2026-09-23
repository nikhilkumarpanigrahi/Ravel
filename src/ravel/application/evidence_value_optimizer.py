"""Evidence-Value Optimizer for Forensic Fraud Investigations.

Ranks and justifies potential next-investigation steps using Information-Theoretic
Expected Information Gain (EIG), customer friction costs, and expected loss reduction:
    VoI = (EIG * Exposure) / FrictionCost
Mathematically demonstrates why the agent seeks specific evidence first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceInquiryOption:
    inquiry_type: str
    channel: str
    target_entity: str
    expected_info_gain_bits: float
    friction_cost_usd: float
    expected_loss_reduction_usd: float
    value_of_information: float
    recommended_order: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "inquiry_type": self.inquiry_type,
            "channel": self.channel,
            "target_entity": self.target_entity,
            "expected_info_gain_bits": round(self.expected_info_gain_bits, 4),
            "friction_cost_usd": round(self.friction_cost_usd, 2),
            "expected_loss_reduction_usd": round(self.expected_loss_reduction_usd, 2),
            "value_of_information": round(self.value_of_information, 4),
            "recommended_order": self.recommended_order,
            "rationale": self.rationale,
        }


class EvidenceValueOptimizer:
    """Calculates information-theoretic Value of Information (VoI) across inquiry actions."""

    @staticmethod
    def binary_entropy(p: float) -> float:
        """Compute binary Shannon entropy H(p) in bits."""
        p = max(1e-6, min(1.0 - 1e-6, p))
        return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))

    def rank_evidence_inquiries(
        self,
        current_fraud_prob: float,
        exposure_usd: float,
        customer_id: str,
        txn_id: str,
        has_device: bool = True,
        has_cardholder_contact: bool = True,
    ) -> list[EvidenceInquiryOption]:
        """Rank candidate investigation actions by expected information gain per unit cost."""
        h_prior = self.binary_entropy(current_fraud_prob)
        candidates: list[dict[str, Any]] = []

        # 1. Cardholder Outbound Verification (SMS / Push)
        if has_cardholder_contact:
            # If customer confirms -> p drops to ~0.05; if denies -> p rises to ~0.95
            p_conf = 0.05
            p_deny = 0.95
            p_legit_prior = 1.0 - current_fraud_prob
            h_posterior = p_legit_prior * self.binary_entropy(
                p_conf
            ) + current_fraud_prob * self.binary_entropy(p_deny)
            eig = max(0.0, h_prior - h_posterior)
            cost = 8.0  # friction cost of disturbing cardholder
            candidates.append(
                {
                    "inquiry_type": "CARDHOLDER_TRANSACTION_VERIFICATION",
                    "channel": "SMS_SECURE_LINK",
                    "target_entity": customer_id,
                    "eig": eig,
                    "cost": cost,
                    "loss_reduction": current_fraud_prob * exposure_usd * 0.90,
                    "rationale": (
                        f"Direct cardholder confirmation provides maximum entropy reduction "
                        f"({eig:.3f} bits) resolving transaction legitimacy with definitive signal."
                    ),
                }
            )

        # 2. Device Fingerprint & Proxy Telemetry Lookup
        if has_device:
            p_dev_clean = max(0.1, current_fraud_prob - 0.25)
            p_dev_proxy = min(0.9, current_fraud_prob + 0.35)
            h_post_dev = 0.7 * self.binary_entropy(p_dev_clean) + 0.3 * self.binary_entropy(p_dev_proxy)
            eig_dev = max(0.0, h_prior - h_post_dev)
            cost_dev = 1.5  # passive backend query cost
            candidates.append(
                {
                    "inquiry_type": "DEVICE_REPUTATION_TELEMETRY",
                    "channel": "INTERNAL_GRAPH_TELEMETRY",
                    "target_entity": f"DEVICE_FOR_{customer_id}",
                    "eig": eig_dev,
                    "cost": cost_dev,
                    "loss_reduction": current_fraud_prob * exposure_usd * 0.40,
                    "rationale": (
                        f"Passive device reputation check provides {eig_dev:.3f} bits of information gain "
                        f"at near-zero customer friction ($1.50)."
                    ),
                }
            )

        # 3. Merchant Category & Terminal Deep Dive
        candidates.append(
            {
                "inquiry_type": "MERCHANT_TERMINAL_AUDIT",
                "channel": "PAYMENT_GATEWAY_LOOKUP",
                "target_entity": f"TXN_{txn_id}",
                "eig": 0.15,
                "cost": 3.0,
                "loss_reduction": current_fraud_prob * exposure_usd * 0.15,
                "rationale": "Merchant terminal lookup offers modest information gain for chargeback history.",
            }
        )

        # 4. Manual Senior Analyst Escalation
        candidates.append(
            {
                "inquiry_type": "HUMAN_ANALYST_DESK_REVIEW",
                "channel": "INTERNAL_TICKET",
                "target_entity": customer_id,
                "eig": 0.45,
                "cost": 45.0,  # expensive operational labor cost
                "loss_reduction": current_fraud_prob * exposure_usd * 0.70,
                "rationale": "Human manual review provides thorough context but incurs high labor operational cost ($45.00).",
            }
        )

        results: list[EvidenceInquiryOption] = []
        for c in candidates:
            voi = (c["eig"] * max(exposure_usd, 50.0)) / c["cost"]
            results.append(
                EvidenceInquiryOption(
                    inquiry_type=c["inquiry_type"],
                    channel=c["channel"],
                    target_entity=c["target_entity"],
                    expected_info_gain_bits=c["eig"],
                    friction_cost_usd=c["cost"],
                    expected_loss_reduction_usd=c["loss_reduction"],
                    value_of_information=voi,
                    recommended_order=0,
                    rationale=c["rationale"],
                )
            )

        # Sort by Value of Information descending
        results.sort(key=lambda x: x.value_of_information, reverse=True)

        ordered_results: list[EvidenceInquiryOption] = []
        for rank, r in enumerate(results, start=1):
            ordered_results.append(
                EvidenceInquiryOption(
                    inquiry_type=r.inquiry_type,
                    channel=r.channel,
                    target_entity=r.target_entity,
                    expected_info_gain_bits=r.expected_info_gain_bits,
                    friction_cost_usd=r.friction_cost_usd,
                    expected_loss_reduction_usd=r.expected_loss_reduction_usd,
                    value_of_information=r.value_of_information,
                    recommended_order=rank,
                    rationale=f"Rank #{rank}: {r.rationale}",
                )
            )

        return ordered_results
