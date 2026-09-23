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


def test_schema_is_created_from_global_scope():
    assert SCHEMA_GSQL.lstrip().startswith("USE GLOBAL")
    assert "USE GRAPH @@graphname@@" not in SCHEMA_GSQL


def test_queries_use_supported_output_and_datetime_syntax():
    assert "PRETTY_PRINT" not in QUERIES_GSQL
    assert " RETURN " not in QUERIES_GSQL
    assert 'datetime_add(anchor_ts, INTERVAL -hours HOUR)' in QUERIES_GSQL
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
