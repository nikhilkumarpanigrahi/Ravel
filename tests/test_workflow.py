"""Integration tests for GraphAdapter and AgentWorkflow."""

from ravel.application.benchmark_service import BenchmarkService
from ravel.application.workflow import AgentWorkflow
from ravel.config import settings
from ravel.domain.enums import Verdict
from ravel.infrastructure.graph.mock import MockGraphAdapter
from ravel.infrastructure.persistence import InvestigationRepository


def test_mock_graph_adapter():
    data_dir = settings.data_dir.parent / "data" / "level0"
    graph = MockGraphAdapter(data_dir)
    health = graph.health()
    assert health["status"] == "ok"
    assert health["transactions"] > 500_000

    # Get sample transaction
    txn = graph.get_transaction("3514030")
    assert txn["txn_id"] == "3514030"
    assert txn["amount"] > 0
    assert "customer_id" in txn

    window = graph.card_window(txn["customer_id"], anchor_ts=txn["ts"], hours=3, limit=50)
    assert window
    assert all(row["ts"] <= txn["ts"] for row in window)

    # Customer profile
    cust = graph.get_customer(txn["customer_id"])
    assert cust["customer_id"] == txn["customer_id"]
    assert cust["n_transactions"] > 0

    # Subgraph for viz
    sub = graph.subgraph_for_viz("3514030")
    assert "nodes" in sub
    assert "edges" in sub
    assert len(sub["nodes"]) > 0


def test_agent_workflow_single_case():
    data_dir = settings.data_dir.parent / "data" / "level0"
    graph = MockGraphAdapter(data_dir)
    repo = InvestigationRepository("sqlite:///:memory:")
    workflow = AgentWorkflow(graph=graph, repo=repo)

    case_pack_row = {
        "case_id": "TEST-001",
        "opened_at": "2016-12-05 01:55:28",
        "trigger_type": "risk_score",
        "trigger_text": "High risk test alert",
        "flagged_txn_id": "3514030",
        "card_id": "C12382-K1",
        "customer_id": "C12382",
        "risk_score": "0.61",
    }

    ans = workflow.run_investigation(case_pack_row)
    assert ans.case_id == "TEST-001"
    assert ans.case.verdict in (Verdict.LEGITIMATE, Verdict.FRAUD, Verdict.UNCERTAIN)
    assert len(ans.case.evidence) > 0
    assert ans.tool_calls > 0
    assert ans.latency_s > 0
    assert "initial" in ans.next_best_actions
    assert "final" in ans.next_best_actions


def test_benchmark_service_limit():
    service = BenchmarkService(settings)
    output_dir = settings.data_dir.parent / "data" / "test-output" / "cases"
    report = service.run_all(limit=2, output_dir=str(output_dir))
    assert report["cases_run"] == 2
    assert len(report["cases"]) == 2
    assert report["avg_latency_s"] >= 0
    assert report["scorecard"]["answer_key_accuracy"] is None
    assert report["scorecard"]["answer_key_status"] == "unavailable_by_challenge_design"
    assert "ground_truth_accuracy" not in report["scorecard"]
