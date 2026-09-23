"""Graph adapter contract.

RAVEL's investigation engine is TigerGraph. Every caller depends on this interface,
not on a specific implementation (Dependency Inversion / ISP). Two implementations live
beside this contract:

- ``TigerGraphAdapter``  -> Savanna / TigerGraph via pyTigerGraph + GSQL
- ``MockGraphAdapter``   -> SQLite-backed reimplementation for tests, dev, and demo mode
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GraphAdapterError(RuntimeError):
    """Base error for graph operations."""


class GraphTimeoutError(GraphAdapterError):
    """Query exceeded its bound."""


class GraphUnavailableError(GraphAdapterError):
    """Graph backend is not reachable."""


class GraphAdapter(ABC):
    """Bounded, purpose-built investigation queries against the relationship graph."""

    # --------------------------------------------------------------- lifecycle
    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return backend health info."""

    @abstractmethod
    def install_schema(self) -> None:
        """Idempotently install the graph schema / loading jobs."""

    @abstractmethod
    def load_dataset(self) -> dict[str, Any]:
        """Run loading jobs from the normalized level0 datasets."""

    @abstractmethod
    def is_loaded(self) -> bool: ...

    # ----------------------------------------------------------- investigation
    @abstractmethod
    def get_transaction(self, txn_id: str) -> dict[str, Any]:
        """Transaction context for one transaction."""

    @abstractmethod
    def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Customer + card profile."""

    @abstractmethod
    def card_history(self, customer_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Recent transactions for a card (chronological)."""

    @abstractmethod
    def card_window(
        self,
        customer_id: str,
        anchor_ts: str = "",
        hours: float = 2.0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Transactions on one card inside a bounded window ending at anchor_ts."""

    @abstractmethod
    def connected_entities(self, customer_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        """Entities connected to the customer/card with their role."""

    @abstractmethod
    def shared_devices(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Device profiles shared with OTHER cards, with counterparty card/customer context."""

    @abstractmethod
    def shared_regions(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Billing regions in common with other cards in a window."""

    @abstractmethod
    def related_transactions(
        self, customer_id: str, window_days: float = 7.0, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Transactions on connected cards sharing a device/region (ring activity)."""

    @abstractmethod
    def historical_cases(
        self, customer_id: str = "", outcome: str = "", pattern: str = "", limit: int = 20
    ) -> list[dict[str, Any]]:
        """Closed-case memory retrievable by customer / outcome / pattern."""

    def similar_cases(self, pattern: str = "", limit: int = 5) -> list[dict[str, Any]]:
        """Convenience method returning cases matching pattern or recent."""
        return self.historical_cases(pattern=pattern, limit=limit)

    @abstractmethod
    def transaction_neighborhood(self, txn_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        """Breadth-first, bounded neighborhood around a transaction."""

    @abstractmethod
    def high_degree_check(self, entity_id: str) -> bool:
        """True if an entity has an unusually high degree (safeguard)."""

    @abstractmethod
    def write_case(self, case: dict[str, Any]) -> str:
        """Persist a closed case into the graph; returns the graph_case_id."""

    @abstractmethod
    def subgraph_for_viz(self, root: str, depth: int = 2, limit: int = 100) -> dict[str, Any]:
        """Nodes + edges for the UI graph panel."""

    # ---------------------------------------------------------------- algs
    def connected_components(self, seed_entities: list[str], limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError
