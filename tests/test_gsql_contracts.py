"""Static contracts for installable GSQL and TigerGraph result normalization."""

from ravel.infrastructure.graph.gsql_scripts import QUERIES_GSQL, SCHEMA_GSQL
from ravel.infrastructure.graph.tigergraph import TigerGraphAdapter, _edge_target, _norm_list


class QueryOnlyConnection:
    def __init__(self):
        self.scripts: list[str] = []

    def queryInstalledQueries(self):
        return []

    def gsql(self, script: str):
        self.scripts.append(script)


class SharedDeviceConnection:
    edges = {
        ("Customer", "C1"): [
            {"e_type": "transaction_of_customer", "to_id": "T1"},
        ],
        ("Transaction", "T1"): [
            {"e_type": "transaction_uses_device", "to_id": "D1"},
        ],
        ("Device", "D1"): [
            {"e_type": "transaction_uses_device", "to_id": "T1"},
            {"e_type": "transaction_uses_device", "to_id": "T2"},
        ],
        ("Transaction", "T2"): [
            {"e_type": "transaction_of_customer", "to_id": "C2"},
            {"e_type": "transaction_of_card", "to_id": "C2-K1"},
        ],
    }

    def getEdges(self, vertex_type, vertex_id):
        return self.edges.get((vertex_type, str(vertex_id)), [])

    def getVerticesById(self, vertex_type, vertex_id):
        if vertex_type == "Device":
            return [{"attributes": {"dev_profile": "profile-1"}}]
        if vertex_type == "Transaction":
            return [
                {
                    "v_id": str(vertex_id[0]) if isinstance(vertex_id, list) else str(vertex_id),
                    "attributes": {
                        "ts": "2016-12-01 10:00:00",
                        "device_profile": "profile-1",
                        "device_proxy": "true",
                    },
                }
            ]
        return []


class CaseMemoryConnection:
    def __init__(self):
        self.vertex = None
        self.edges = []

    def upsertVertex(self, vertex_type, vertex_id, attributes):
        self.vertex = (vertex_type, vertex_id, attributes)

    def upsertEdge(self, from_type, from_id, edge_type, to_type, to_id):
        self.edges.append((from_type, from_id, edge_type, to_type, to_id))


def test_schema_is_created_from_global_scope():
    assert SCHEMA_GSQL.lstrip().startswith("USE GLOBAL")
    assert "USE GRAPH @@graphname@@" not in SCHEMA_GSQL


def test_queries_use_supported_output_and_datetime_syntax():
    assert "PRETTY_PRINT" not in QUERIES_GSQL
    assert " RETURN " not in QUERIES_GSQL
    assert "datetime_add(anchor_ts, INTERVAL -hours HOUR)" in QUERIES_GSQL
    assert QUERIES_GSQL.count("CREATE OR REPLACE QUERY") == 10


def test_every_global_accumulator_is_declared():
    for declaration in (
        "SumAccum<INT> @@deg;",
        "SetAccum<STRING> @@devs;",
        "SetAccum<STRING> @@regions;",
        "SetAccum<STRING> @@emails;",
    ):
        assert declaration in QUERIES_GSQL


def test_normalizer_flattens_printed_vertex_attributes():
    raw = [
        {
            "results": [
                {
                    "v_id": "TXN-1",
                    "v_type": "Transaction",
                    "attributes": {"txn_id": "TXN-1", "amount": 42.5},
                }
            ]
        }
    ]
    assert _norm_list(raw) == [
        {
            "txn_id": "TXN-1",
            "amount": 42.5,
            "v_id": "TXN-1",
            "v_type": "Transaction",
        }
    ]


def test_edge_target_supports_live_hhgoa_edge_names():
    edges = [
        {"e_type": "transaction_of_card", "to_id": "C12382-K1"},
        {"e_type": "transaction_of_customer", "to_id": "C12382"},
    ]

    assert _edge_target(edges, "transaction_of_customer", "CARD_OF") == "C12382"
    assert _edge_target(edges, "transaction_of_card", "MADE_BY") == "C12382-K1"
    assert _edge_target(edges, "transaction_uses_device", "FROM_DEVICE") == ""


def test_normalizer_keeps_scalar_accumulator_results():
    assert _norm_list([{"@@deg": 17}]) == [{"value": 17}]


def test_query_install_does_not_attempt_to_recreate_schema():
    adapter = object.__new__(TigerGraphAdapter)
    adapter.graphname = "FraudDetectionGraph"
    adapter.conn = QueryOnlyConnection()
    adapter._installed_cache = {"stale"}

    adapter._ensure_installed()

    assert len(adapter.conn.scripts) == 1
    assert "CREATE OR REPLACE QUERY" in adapter.conn.scripts[0]
    assert "CREATE VERTEX" not in adapter.conn.scripts[0]
    assert adapter._installed_cache is None


def test_shared_devices_native_fallback_finds_other_customer():
    adapter = object.__new__(TigerGraphAdapter)
    adapter.conn = SharedDeviceConnection()
    adapter._installed_cache = set()

    assert adapter.shared_devices("C1") == [
        {
            "device_id": "D1",
            "device_profile": "profile-1",
            "other_customer_id": "C2",
            "other_card_id": "C2-K1",
            "device_new": "",
            "device_proxy": "true",
            "shared_txns": 1,
            "last_seen": "2016-12-01 10:00:00",
        }
    ]


def test_native_case_write_persists_live_schema_attributes_and_relationships():
    adapter = object.__new__(TigerGraphAdapter)
    adapter.conn = CaseMemoryConnection()
    adapter._installed_cache = set()

    case_id = adapter.write_case(
        {
            "graph_case_id": "CASE-TEST",
            "customer_id": "C1",
            "card_id": "C1-K1",
            "connected_card_ids": ["C2-K1"],
            "affected_txn_ids": ["T1", "T2"],
            "verdict": "fraud",
            "pattern": "account_takeover",
            "actions_taken": ["CREATE_CASE", "FILE_REPORT"],
            "report_filed": True,
        }
    )

    assert case_id == "CASE-TEST"
    assert adapter.conn.vertex[0:2] == ("FraudCase", "CASE-TEST")
    attributes = adapter.conn.vertex[2]
    assert "case_id" not in attributes
    assert attributes["n_txns"] == 2
    assert attributes["report_filed"] == "true"
    assert (
        "FraudCase",
        "CASE-TEST",
        "case_of_customer",
        "Customer",
        "C1",
    ) in adapter.conn.edges
    assert (
        "FraudCase",
        "CASE-TEST",
        "case_first_fraud_transaction",
        "Transaction",
        "T1",
    ) in adapter.conn.edges
