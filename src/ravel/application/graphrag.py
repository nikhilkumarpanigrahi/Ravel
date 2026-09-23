"""GraphRAG context assembly and hybrid retrieval for investigation reasoning."""

from __future__ import annotations

from typing import Any

from ravel.application.policy_retrieval import PolicyRetriever
from ravel.domain.enums import EvidenceSource, EvidenceType
from ravel.domain.evidence import EvidenceRecord
from ravel.infrastructure.graph.base import GraphAdapter


class GraphRAGContext:
    """Structured container of retrieved graph evidence, policies, and historical cases."""

    def __init__(
        self,
        case_id: str,
        customer_id: str,
        card_id: str,
        txn_id: str,
        evidence: list[EvidenceRecord],
        historical_cases: list[dict[str, Any]],
        connected_cards: list[str],
        device_profiles: list[str],
        policy_snippets: list[str],
    ):
        self.case_id = case_id
        self.customer_id = customer_id
        self.card_id = card_id
        self.txn_id = txn_id
        self.evidence = evidence
        self.historical_cases = historical_cases
        self.connected_cards = connected_cards
        self.device_profiles = device_profiles
        self.policy_snippets = policy_snippets

    def to_summary_prompt(self) -> str:
        """Format a bounded, provenance-preserving context string for LLM reasoning."""
        ev_lines = [f"- [{e.source.value.upper()}] {e.claim} (Ref: {e.ref})" for e in self.evidence]
        hist_lines = [
            f"- Case {c.get('case_id')}: outcome={c.get('outcome')}, pattern={c.get('pattern')}, "
            f"exposure=${c.get('exposure_usd')}, notes={c.get('summary', '')[:100]}"
            for c in self.historical_cases[:3]
        ]
        return (
            f"Case: {self.case_id}\n"
            f"Customer: {self.customer_id}, Card: {self.card_id}, Flagged Txn: {self.txn_id}\n\n"
            f"Graph Evidence:\n" + "\n".join(ev_lines or ["- None collected"]) + "\n\n"
            "Historical Memory (Closed Cases):\n" + "\n".join(hist_lines or ["- None retrieved"]) + "\n\n"
            f"Connected Cards: {', '.join(self.connected_cards) or 'None'}\n"
            f"Device Profiles: {', '.join(self.device_profiles) or 'None'}\n"
            "Retrieved Fraud Policy:\n" + "\n".join(f"- {snippet}" for snippet in self.policy_snippets) + "\n"
        )


class GraphRAGService:
    """Retrieves and synthesizes graph neighborhood, historical memory, and policy rules."""

    def __init__(self, graph: GraphAdapter, policy_retriever: PolicyRetriever | None = None):
        self.graph = graph
        self.policy_retriever = policy_retriever or PolicyRetriever()

    def retrieve(self, customer_id: str, card_id: str, txn_id: str, case_id: str = "") -> GraphRAGContext:
        """Query TigerGraph / GraphAdapter to assemble multi-hop evidence with provenance."""
        evidence: list[EvidenceRecord] = []

        # 1. Transaction context
        txn = self.graph.get_transaction(txn_id)
        evidence.append(
            EvidenceRecord(
                case_id=case_id,
                claim=(
                    f"Flagged transaction {txn_id} for ${txn.get('amount', 0):.2f} via {txn.get('channel')} "
                    f"(ProductCD {txn.get('product_cd')}) with initial risk score {txn.get('risk_score', 0):.2f}"
                ),
                source=EvidenceSource.GRAPH,
                ref=f"query:get_transaction({txn_id})",
                entity_ids=[txn_id],
                evidence_type=EvidenceType.TRANSACTION,
                strength=0.7,
                graph_path=(
                    f"Transaction({txn_id}) --transaction_of_customer-- Customer({customer_id}); "
                    f"Transaction({txn_id}) --transaction_of_card-- Card({card_id})"
                ),
            )
        )

        # 2. Customer profile and history
        cust = self.graph.get_customer(customer_id)
        evidence.append(
            EvidenceRecord(
                case_id=case_id,
                claim=(
                    f"Customer {customer_id} holds card {card_id} with {cust.get('n_transactions', 0)} total "
                    f"transactions on file, billed in home region {cust.get('home_region', 'unknown')}"
                ),
                source=EvidenceSource.GRAPH,
                ref=f"query:get_customer({customer_id})",
                entity_ids=[customer_id, card_id],
                evidence_type=EvidenceType.RELATIONSHIP,
                strength=0.5,
                graph_path=f"Customer({customer_id}).home_region={cust.get('home_region', 'unknown')}",
            )
        )

        # 3. Device & Connectivity
        connected = self.graph.connected_entities(customer_id)
        device_profiles: list[str] = []
        for ent in connected:
            if ent.get("type") == "device" and ent.get("label"):
                device_profiles.append(ent["label"])

        shared_devs = (
            self.graph.shared_devices(customer_id)
            if (txn.get("channel") or "").lower() != "in_person"
            else []
        )
        shared_cards = list({r["other_card_id"] for r in shared_devs if r.get("other_card_id")})
        if shared_cards:
            primary_dev = device_profiles[0] if device_profiles else "DEVICE_SHARED"
            evidence.append(
                EvidenceRecord(
                    case_id=case_id,
                    claim=f"Device shared across {len(shared_cards)} other card(s): {', '.join(shared_cards[:3])}",
                    source=EvidenceSource.GRAPH,
                    ref=f"query:shared_devices({customer_id})",
                    entity_ids=shared_cards,
                    evidence_type=EvidenceType.DEVICE,
                    strength=0.85,
                    graph_path=(
                        f"Customer({customer_id}) --transaction_of_customer-- Transaction "
                        f"--transaction_uses_device-- Device({primary_dev}) "
                        f"--transaction_uses_device-- Transaction --transaction_of_card-- Card({shared_cards[0]})"
                    ),
                )
            )

        # 4. Historical memory retrieval
        history_cases = self.graph.historical_cases(customer_id)
        if not history_cases:
            history_cases = self.graph.similar_cases(pattern="", limit=3)

        if history_cases:
            top_closed = history_cases[0].get("case_id", "CC-HIST")
            evidence.append(
                EvidenceRecord(
                    case_id=case_id,
                    claim=f"Retrieved {len(history_cases)} similar closed case(s) from case memory: "
                    f"{', '.join(c.get('case_id', '') for c in history_cases[:3])}",
                    source=EvidenceSource.GRAPH,
                    ref="query:historical_cases",
                    entity_ids=[c.get("case_id", "") for c in history_cases[:3] if c.get("case_id")],
                    evidence_type=EvidenceType.HISTORICAL_CASE,
                    strength=0.6,
                    graph_path=f"FraudCase({top_closed}) --case_of_customer--> Customer({customer_id})",
                )
            )

        policy_query = " ".join(
            [
                *(record.claim for record in evidence),
                *(str(case.get("summary", "")) for case in history_cases[:3]),
                str(txn.get("channel", "")),
            ]
        )
        policy_snippets = self.policy_retriever.retrieve(policy_query)

        return GraphRAGContext(
            case_id=case_id,
            customer_id=customer_id,
            card_id=card_id,
            txn_id=txn_id,
            evidence=evidence,
            historical_cases=history_cases,
            connected_cards=shared_cards,
            device_profiles=device_profiles,
            policy_snippets=policy_snippets,
        )
