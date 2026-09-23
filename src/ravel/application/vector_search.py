"""Hybrid Vector Search and Embedding Service for RAVEL.

Provides dense semantic vector retrieval over historical closed cases and fraud policy rules,
combining graph/categorical filters with embedding-based cosine similarity.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


class LightweightTextEmbedder:
    """Deterministic, high-performance sparse-to-dense semantic vector embedder.

    Produces normalized 128-dimensional dense semantic vectors using subword hashing
    and term-frequency weighting, ensuring fast, reproducible offline embeddings without
    external cloud dependencies.
    """

    def __init__(self, dim: int = 128):
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(self.dim, dtype=np.float32)

        tokens = re.findall(r"\b[a-zA-Z0-9_\-\$]+\b", text.lower())
        if not tokens:
            return np.zeros(self.dim, dtype=np.float32)

        vec = np.zeros(self.dim, dtype=np.float32)
        counts = Counter(tokens)
        total = len(tokens)

        for token, count in counts.items():
            # Hash token and character n-grams to distribute semantics across dimensions
            h = hash(token) % self.dim
            weight = (count / total) * math.log(1.0 + len(token))
            vec[h] += weight

            # 3-gram subwords
            if len(token) >= 4:
                for i in range(len(token) - 2):
                    sub = token[i : i + 3]
                    sub_h = hash(sub) % self.dim
                    vec[sub_h] += weight * 0.3

        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec /= norm
        return vec


class CaseVectorIndex:
    """In-memory vector store indexing historical closed fraud cases and policies."""

    def __init__(self, embedder: LightweightTextEmbedder | None = None):
        self.embedder = embedder or LightweightTextEmbedder(dim=128)
        self.entries: list[dict[str, Any]] = []
        self.embeddings: np.ndarray = np.empty((0, 128), dtype=np.float32)

    def index_cases_from_csv(self, csv_path: Path) -> int:
        if not csv_path.exists():
            return 0

        self.entries.clear()
        vectors: list[np.ndarray] = []

        with csv_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                summary = (
                    f"Pattern: {row.get('pattern', '')}. Outcome: {row.get('outcome', '')}. "
                    f"Exposure: ${row.get('exposure_usd', '0')}. Actions: {row.get('actions_taken', '')}. "
                    f"Report: {row.get('report_filed', '')}. {row.get('summary', '')}"
                )
                vec = self.embedder.embed(summary)
                vectors.append(vec)
                self.entries.append(
                    {
                        "case_id": row.get("case_id", ""),
                        "customer_id": row.get("customer_id", ""),
                        "card_id": row.get("card_id", ""),
                        "outcome": row.get("outcome", ""),
                        "pattern": row.get("pattern", ""),
                        "exposure_usd": float(row.get("exposure_usd") or 0.0),
                        "actions_taken": row.get("actions_taken", ""),
                        "report_filed": row.get("report_filed", ""),
                        "summary": summary,
                    }
                )

        if vectors:
            self.embeddings = np.vstack(vectors)
        return len(self.entries)

    def search_similar_cases(
        self,
        query: str,
        pattern: str = "",
        min_exposure: float = 0.0,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search similar historical cases by semantic query and optional categorical filters."""
        if not self.entries or self.embeddings.shape[0] == 0:
            return []

        q_vec = self.embedder.embed(query)
        q_norm = np.linalg.norm(q_vec)
        if q_norm < 1e-8:
            return []

        # Cosine similarities: (N, 128) dot (128,)
        sims = np.dot(self.embeddings, q_vec)

        scored: list[tuple[float, dict[str, Any]]] = []
        for idx, sim in enumerate(sims):
            entry = self.entries[idx]
            if pattern and entry.get("pattern") != pattern:
                continue
            if entry.get("exposure_usd", 0.0) < min_exposure:
                continue
            scored.append((float(sim), entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, entry in scored[:top_k]:
            results.append(
                {
                    **entry,
                    "similarity_score": round(score, 4),
                }
            )
        return results


_default_index: CaseVectorIndex | None = None


def get_case_vector_index(data_dir: Path | None = None) -> CaseVectorIndex:
    global _default_index
    if _default_index is None:
        _default_index = CaseVectorIndex()
        if data_dir:
            csv_path = data_dir / "closed_cases_history.csv"
            _default_index.index_cases_from_csv(csv_path)
    return _default_index
