"""Tests for source-grounded policy retrieval."""

from pathlib import Path

from ravel.application.graphrag import GraphRAGContext
from ravel.application.policy_retrieval import PolicyRetriever

POLICY_SOURCE = Path("HHGOA_IEEE/README.md")


def test_retriever_returns_exact_rule_with_source_provenance():
    snippets = PolicyRetriever(POLICY_SOURCE).retrieve(
        "single weak risk score signal verify before block",
        limit=2,
    )
    assert any("R1. Verify before you block on a weak signal" in item for item in snippets)
    assert all("[source: HHGOA_IEEE/README.md#fraud-policy]" in item for item in snippets)


def test_retriever_selects_shared_origin_rule():
    snippets = PolicyRetriever(POLICY_SOURCE).retrieve(
        "several cards share the same device profile and connected fraud",
        limit=2,
    )
    assert any("R6. Shared origin" in item for item in snippets)


def test_graphrag_prompt_includes_retrieved_policy():
    context = GraphRAGContext(
        case_id="CASE-1",
        customer_id="CUSTOMER-1",
        card_id="CARD-1",
        txn_id="TXN-1",
        evidence=[],
        historical_cases=[],
        connected_cards=[],
        device_profiles=[],
        policy_snippets=["R1 exact clause [source: policy.md#fraud-policy]"],
    )
    prompt = context.to_summary_prompt()
    assert "Retrieved Fraud Policy" in prompt
    assert "R1 exact clause" in prompt
    assert "policy.md#fraud-policy" in prompt
