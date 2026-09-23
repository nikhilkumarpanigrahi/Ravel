from sqlalchemy import create_engine

from ravel.application.langgraph_workflow import LangGraphWorkflowRunner
from ravel.config import settings
from ravel.infrastructure.graph.mock import MockGraphAdapter
from ravel.infrastructure.llm import DeterministicSynthesizer
from ravel.infrastructure.persistence import InvestigationRepository


def test_langgraph_workflow_execution():
    level0_dir = settings.data_dir.parent / "data" / "level0"
    graph = MockGraphAdapter(level0_dir)
    engine = create_engine("sqlite:///:memory:")
    repo = InvestigationRepository(engine)
    llm = DeterministicSynthesizer()

    runner = LangGraphWorkflowRunner(
        graph=graph,
        repo=repo,
        llm=llm,
        simulate_customer=True,
    )

    trigger = {
        "case_id": "HHG-001",
        "flagged_txn_id": "3514030",
        "customer_id": "C12382",
        "card_id": "C12382-K1",
        "trigger_type": "risk_score",
        "risk_score": 0.61,
        "trigger_text": "High risk score on in-person transaction",
    }

    ans = runner.run_investigation(trigger)
    assert ans.case_id == "HHG-001"
    assert ans.case.verdict.value in ("legitimate", "fraud", "uncertain")
    assert ans.next_best_actions.get("final") is not None
    assert ans.tool_calls > 0
    assert ans.latency_s >= 0.0
    assert ans.counterfactuals
    assert any(e.ref == "vector:closed_case_similarity" for e in ans.case.evidence)
