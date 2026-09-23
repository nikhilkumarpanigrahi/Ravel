from ravel.application.agentic_engine import AgenticInvestigationEngine
from ravel.domain.enums import TriggerType


class PassiveGraph:
    def shared_devices(self, customer_id, limit=50):
        return [
            {"other_card_id": "C2-K1"},
            {"other_card_id": "C3-K1"},
        ]

    def get_transaction(self, txn_id):
        return {"amount": 450.0, "channel": "online", "product_cd": "C"}


def test_agentic_loop_uses_graph_evidence_without_faking_customer_reply():
    engine = AgenticInvestigationEngine(PassiveGraph())

    probability, evidence, trace = engine.run_agentic_loop(
        case_id="HHG-TEST",
        customer_id="C1",
        card_id="C1-K1",
        flagged_txn_id="T1",
        trigger_type=TriggerType.RISK_SCORE,
        risk_score=0.55,
        exposure_usd=450.0,
        max_steps=3,
    )

    assert probability > 0.55
    assert {item.tool_used for item in evidence} == {
        "tigergraph:shared_devices",
        "tigergraph:get_txn",
    }
    assert all(item.source.value == "graph" for item in evidence)
    assert all("customer_inquiry" not in item.ref for item in evidence)
    assert len(trace) == 2
