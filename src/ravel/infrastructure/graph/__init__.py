from __future__ import annotations

from typing import Any

from ravel.infrastructure.graph.base import (
    GraphAdapter,
    GraphAdapterError,
    GraphTimeoutError,
    GraphUnavailableError,
)
from ravel.infrastructure.graph.mock import MockGraphAdapter
from ravel.infrastructure.graph.tigergraph import TigerGraphAdapter


def create_graph_adapter(settings: Any) -> GraphAdapter:
    """Factory to instantiate TigerGraphAdapter or MockGraphAdapter with automatic fallback."""
    level0_dir = settings.data_dir.parent / "data" / "level0"
    if settings.graph_adapter == "tigergraph" and getattr(settings, "tg_host", ""):
        try:
            return TigerGraphAdapter(
                host=settings.tg_host,
                graphname=getattr(settings, "tg_graphname", "ravel"),
                username=getattr(settings, "tg_username", "tigergraph"),
                password=getattr(settings, "tg_password", ""),
                secret=getattr(settings, "tg_secret", ""),
                query_timeout=getattr(settings, "tg_query_timeout", 30),
            )
        except Exception:
            return MockGraphAdapter(level0_dir)
    return MockGraphAdapter(level0_dir)


__all__ = [
    "GraphAdapter",
    "GraphAdapterError",
    "GraphTimeoutError",
    "GraphUnavailableError",
    "MockGraphAdapter",
    "TigerGraphAdapter",
    "create_graph_adapter",
]
