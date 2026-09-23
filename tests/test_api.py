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
