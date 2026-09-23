"""Tests for graph backend selection and configuration."""

from pathlib import Path
from types import SimpleNamespace

from ravel.infrastructure import graph as graph_module
from ravel.infrastructure.graph.tigergraph import TigerGraphAdapter


class HealthyTigerGraph:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def health(self):
        return {"status": "ok"}


class UnavailableTigerGraph(HealthyTigerGraph):
    def health(self):
        raise RuntimeError("offline")


class EchoOnlyConnection:
    def echo(self):
        return "Hello GSQL"

    def getVersion(self):
        raise RuntimeError("version endpoint unavailable")


def _settings():
    root = Path("data/test-output/factory")
    data_dir = root / "HHGOA_IEEE"
    data_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        graph_adapter="tigergraph",
        data_dir=data_dir,
        tg_host="https://example.invalid",
        tg_graphname="ravel",
        tg_username="tigergraph",
        tg_password="secret",
        tg_token="token",
        tg_secret="secret-id",
        tg_use_token=True,
        tg_query_timeout=7,
    )


def test_factory_passes_complete_tigergraph_configuration(monkeypatch):
    monkeypatch.setattr(graph_module, "TigerGraphAdapter", HealthyTigerGraph)
    adapter = graph_module.create_graph_adapter(_settings())
    assert isinstance(adapter, HealthyTigerGraph)
    assert adapter.kwargs["token"] == "token"
    assert adapter.kwargs["use_token"] is True
    assert adapter.kwargs["data_dir"] == Path("data/test-output/factory/data/level0")


def test_factory_falls_back_only_after_failed_health_check(monkeypatch):
    monkeypatch.setattr(graph_module, "TigerGraphAdapter", UnavailableTigerGraph)
    adapter = graph_module.create_graph_adapter(_settings())
    assert adapter.health()["backend"] == "mock"


def test_tigergraph_health_uses_echo_and_tolerates_missing_version():
    adapter = object.__new__(TigerGraphAdapter)
    adapter.conn = EchoOnlyConnection()

    assert adapter.health() == {
        "backend": "tigergraph",
        "status": "ok",
        "echo": "Hello GSQL",
        "version": None,
    }
