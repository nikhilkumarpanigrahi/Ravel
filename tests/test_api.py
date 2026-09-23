"""Tests for FastAPI backend routes."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ravel.domain.enums import ActionType, ApprovalRoute, ApprovalState, TriggerType
from ravel.domain.investigation import Investigation, Trigger
from ravel.domain.policy import ApprovalRecord
from ravel.interfaces.api import app, repo

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["app"] == "RAVEL"


def test_cases_list():
    res = client.get("/api/cases")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_get_case_detail():
    res = client.get("/api/cases/HHG-001")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == "HHG-001"
    assert "case" in data
    assert "next_best_actions" in data
    assert "sar" in data


def test_graph_endpoint():
    res = client.get("/api/graph/3514030")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data


def test_replay_case():
    res = client.post("/api/cases/HHG-001/replay")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == "HHG-001"
    assert data["case"]["written_to_graph"] is True

    persisted = client.get("/api/cases/HHG-001")
    assert persisted.status_code == 200
    assert persisted.json() == data

    timeline = client.get("/api/cases/HHG-001/timeline")
    assert timeline.status_code == 200
    trace = timeline.json()
    assert trace["investigation_id"].startswith("INV-")
    assert trace["state_history"]
    assert trace["steps"]


def test_replay_unknown_case():
    res = client.post("/api/cases/HHG-999/replay")
    assert res.status_code == 404


def test_benchmark_results():
    res = client.get("/api/benchmark/results")
    assert res.status_code == 200
    data = res.json()
    assert "cases_run" in data or "status" in data


def test_approval_post():
    investigation = Investigation(
        case_id="TEST-APPROVAL",
        trigger=Trigger(
            type=TriggerType.ANALYST_REQUEST,
            case_id="TEST-APPROVAL",
            opened_at=datetime.now(UTC),
            trigger_text="approval API test",
            flagged_txn_id="3514030",
        ),
    )
    repo.save_investigation(investigation)
    repo.add_approval(
        investigation.investigation_id,
        ApprovalRecord(
            approval_id="APP-TEST-123",
            action=ActionType.BLOCK_CARD,
            case_id="TEST-APPROVAL",
            route=ApprovalRoute.L1,
            state=ApprovalState.PENDING,
        ),
    )
    res = client.post(
        "/api/approvals",
        json={
            "approval_id": "APP-TEST-123",
            "decision": "APPROVED",
            "reason": "Analyst verified",
            "approver": "test_lead",
            "approver_role": "L1",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "recorded"
    assert res.json()["state"] == "APPROVED"
    execution = res.json()["execution"]
    assert execution["action_id"] == "ACT-APP-TEST-123"
    assert execution["action"] == "BLOCK_CARD"
    assert execution["state"] == "EXECUTED"
    assert execution["simulated"] is True
    assert execution["executed_at"]

    actions = client.get("/api/cases/TEST-APPROVAL/actions")
    assert actions.status_code == 200
    assert [item["action_id"] for item in actions.json()] == ["ACT-APP-TEST-123"]


def test_rejected_approval_does_not_execute_action():
    investigation = Investigation(
        case_id="TEST-REJECTED-APPROVAL",
        trigger=Trigger(
            type=TriggerType.ANALYST_REQUEST,
            case_id="TEST-REJECTED-APPROVAL",
            opened_at=datetime.now(UTC),
            trigger_text="rejected approval API test",
            flagged_txn_id="3514030",
        ),
    )
    repo.save_investigation(investigation)
    repo.add_approval(
        investigation.investigation_id,
        ApprovalRecord(
            approval_id="APP-TEST-REJECTED",
            action=ActionType.BLOCK_CARD,
            case_id="TEST-REJECTED-APPROVAL",
            route=ApprovalRoute.L1,
            state=ApprovalState.PENDING,
        ),
    )
    res = client.post(
        "/api/approvals",
        json={
            "approval_id": "APP-TEST-REJECTED",
            "decision": "REJECTED",
            "reason": "Evidence was insufficient",
            "approver": "test_lead",
            "approver_role": "L1",
        },
    )
    assert res.status_code == 200
    assert res.json()["state"] == "REJECTED"
    assert res.json()["execution"] is None
    assert client.get("/api/cases/TEST-REJECTED-APPROVAL/actions").json() == []


def test_l1_cannot_approve_l2_action():
    investigation = Investigation(
        case_id="TEST-L2-APPROVAL",
        trigger=Trigger(
            type=TriggerType.ANALYST_REQUEST,
            case_id="TEST-L2-APPROVAL",
            opened_at=datetime.now(UTC),
            trigger_text="L2 authorization test",
            flagged_txn_id="3514030",
        ),
    )
    repo.save_investigation(investigation)
    repo.add_approval(
        investigation.investigation_id,
        ApprovalRecord(
            approval_id="APP-TEST-L2",
            action=ActionType.FILE_REPORT,
            case_id="TEST-L2-APPROVAL",
            route=ApprovalRoute.L2,
            state=ApprovalState.PENDING,
        ),
    )
    res = client.post(
        "/api/approvals",
        json={
            "approval_id": "APP-TEST-L2",
            "decision": "APPROVED",
            "approver": "test_lead",
            "approver_role": "L1",
        },
    )
    assert res.status_code == 403
