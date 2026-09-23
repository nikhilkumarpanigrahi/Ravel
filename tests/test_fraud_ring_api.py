from fastapi.testclient import TestClient

from ravel.interfaces.api import app

client = TestClient(app)


def test_fraud_ring_endpoint():
    res = client.get("/api/fraud-rings/C12382")
    assert res.status_code == 200
    data = res.json()
    assert data["seed_customer_id"] == "C12382"
    assert "ring_detected" in data
    assert "subgraph" in data
    assert "nodes" in data["subgraph"]
    assert "edges" in data["subgraph"]


def test_evidence_optimizer_endpoint():
    res = client.get("/api/cases/HHG-001/evidence-optimizer")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        assert "expected_info_gain_bits" in data[0]
        assert "value_of_information" in data[0]
        assert "recommended_order" in data[0]
