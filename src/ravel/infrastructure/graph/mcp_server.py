"""TigerGraph Model Context Protocol (MCP) Server for RAVEL.

Exposes bounded graph investigation tools, GSQL pattern matchers,
and case write-back operations to any MCP client (Claude Desktop, Antigravity,
LangGraph, OpenAI Agents SDK).

Works with both live TigerGraph Savanna instances and local high-performance graph adapter.
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from ravel.config import settings
from ravel.infrastructure.graph import create_graph_adapter

mcp = MCPServer("tigergraph-ravel")
adapter = create_graph_adapter(settings)


@mcp.tool()
def get_transaction(txn_id: str) -> str:
    """Retrieve full attributes of a single transaction from the graph."""
    try:
        txn = adapter.get_transaction(txn_id)
    except KeyError:
        return json.dumps({"error": f"Transaction {txn_id} not found."})
    return json.dumps(txn)


@mcp.tool()
def card_history(customer_id: str, limit: int = 20) -> str:
    """Retrieve recent chronological transactions on a customer card."""
    txns = adapter.card_history(customer_id, limit=limit)
    return json.dumps(txns, default=str)


@mcp.tool()
def card_window(customer_id: str, anchor_ts: str, hours: int = 72, limit: int = 50) -> str:
    """Retrieve transactions in the time window preceding anchor_ts on a card."""
    txns = adapter.card_window(customer_id, anchor_ts, hours=hours, limit=limit)
    return json.dumps(txns, default=str)


@mcp.tool()
def shared_devices(customer_id: str, limit: int = 20) -> str:
    """Find other customer accounts that share device hardware profiles with this customer."""
    devs = adapter.shared_devices(customer_id, limit=limit)
    return json.dumps(devs, default=str)


@mcp.tool()
def shared_regions(customer_id: str, limit: int = 20) -> str:
    """Find other customer accounts operating in the exact same billing postal/regions."""
    regions = adapter.shared_regions(customer_id, limit=limit)
    return json.dumps(regions, default=str)


@mcp.tool()
def related_transactions(customer_id: str, limit: int = 50) -> str:
    """Find 2-hop related transactions linked via shared device hardware."""
    txns = adapter.related_transactions(customer_id, limit=limit)
    return json.dumps(txns, default=str)


@mcp.tool()
def historical_cases(customer_id: str = "", outcome: str = "", pattern: str = "", limit: int = 10) -> str:
    """Query closed historical fraud investigation cases from graph memory."""
    cases = adapter.historical_cases(customer_id=customer_id, outcome=outcome, pattern=pattern, limit=limit)
    return json.dumps(cases, default=str)


@mcp.tool()
def check_high_degree(entity_id: str) -> str:
    """Check if an entity has unusually high connectivity (high degree safeguard)."""
    is_high = adapter.high_degree_check(entity_id)
    return json.dumps({"entity_id": entity_id, "is_high_degree": is_high})


@mcp.tool()
def connected_entities(customer_id: str, limit: int = 50) -> str:
    """List all devices, billing regions, and email domains connected to a customer account."""
    ents = adapter.connected_entities(customer_id, limit=limit)
    return json.dumps(ents, default=str)


@mcp.tool()
def write_fraud_case(
    graph_case_id: str,
    case_id: str,
    customer_id: str,
    verdict: str,
    pattern: str,
    exposure_usd: float,
    summary: str,
    card_ids: list[str],
    txn_ids: list[str],
) -> str:
    """Persist a completed fraud investigation verdict and lineage back into the graph."""
    res = adapter.write_case(
        {
            "graph_case_id": graph_case_id,
            "case_id": case_id,
            "customer_id": customer_id,
            "outcome": verdict,
            "verdict": verdict,
            "pattern": pattern,
            "exposure_usd": exposure_usd,
            "summary": summary,
            "connected_card_ids": card_ids,
            "involves_txns": txn_ids,
        }
    )
    return json.dumps({"status": "written", "graph_case_id": res}, default=str)


def run_mcp_stdio() -> None:
    """Run the MCP server over stdio transport."""
    import asyncio

    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    run_mcp_stdio()
