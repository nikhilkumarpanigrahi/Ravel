"""Retrieval over the authoritative fraud policy supplied with the challenge data."""

from __future__ import annotations

import re
from pathlib import Path


class PolicyRetriever:
    """Rank exact policy clauses without replacing them with generated summaries."""

    def __init__(self, source_path: Path | None = None):
        self.source_path = source_path or (
            Path(__file__).resolve().parents[3] / "HHGOA_IEEE" / "README.md"
        )
        self._rules, self._approval = self._load()

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9_]+", text.lower())
            if len(token) > 2
        }

    def _load(self) -> tuple[list[str], str]:
        if not self.source_path.exists():
            return [], ""
        document = self.source_path.read_text(encoding="utf-8")
        marker = document.find("# Fraud Policy")
        if marker < 0:
            return [], ""
        policy = document[marker:]
        rules = [
            " ".join(f"{heading} {body}".split())
            for heading, body in re.findall(
                r"(?ms)^\*\*(R\d+\.[^*]+)\*\*\s*(.*?)(?=^\*\*R\d+\.|^### |\Z)",
                policy,
            )
        ]
        approval_match = re.search(
            r"(?ms)^### 2\. Approval routing\s*(.*?)(?=^### )",
            policy,
        )
        approval = " ".join(approval_match.group(1).split()) if approval_match else ""
        return rules, approval

    def retrieve(self, query: str, limit: int = 4) -> list[str]:
        """Return relevant verbatim clauses with an auditable local source reference."""
        query_tokens = self._tokens(query)
        ranked = sorted(
            self._rules,
            key=lambda rule: (len(query_tokens & self._tokens(rule)), rule),
            reverse=True,
        )
        selected = [rule for rule in ranked if query_tokens & self._tokens(rule)][:limit]
        if not selected:
            selected = ranked[: min(limit, len(ranked))]
        if self._approval:
            selected.append(f"Approval routing: {self._approval}")
        source = self.source_path.as_posix()
        return [f"{clause} [source: {source}#fraud-policy]" for clause in selected]
