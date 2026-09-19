"""Tests for FastAPI backend routes."""

from fastapi.testclient import TestClient

from ravel.interfaces.api import app

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
    res = client.post(
        "/api/approvals",
        json={"approval_id": "APP-123", "decision": "APPROVED", "reason": "Analyst verified"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "recorded"
