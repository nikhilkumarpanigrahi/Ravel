"""TigerGraph (Savanna / Community Edition) adapter.

Implements :class:`GraphAdapter` against a real TigerGraph instance through pyTigerGraph.
Each bounded investigation query maps to an installed GSQL query from ``gsql_scripts``.
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path
from typing import Any

from ravel.infrastructure.graph import gsql_scripts as gsql
from ravel.infrastructure.graph.base import GraphAdapter, GraphTimeoutError, GraphUnavailableError


def _norm_list(raw: Any) -> list[dict[str, Any]]:
    """Flatten pyTigerGraph runInstalledQuery output (list of packets) into dict rows."""
    if isinstance(raw, dict):
        raw = [raw]
    out: list[dict[str, Any]] = []
    for packet in raw or []:
        for key, value in (packet or {}).items():
            if key in ("results",):
                continue
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict):
                        out.append({k: _clean(v) for k, v in row.items()})
            elif value is not None:
                out.append({"value": _clean(value)})
    return out


def _clean(v: Any) -> Any:
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return v
    try:
        return json.loads(json.dumps(v))
    except Exception:
        return str(v)


class TigerGraphAdapter(GraphAdapter):
    def __init__(
        self,
        host: str,
        graphname: str,
        username: str = "",
        password: str = "",
        token: str = "",
        secret: str = "",
        use_token: bool = False,
        query_timeout: int = 30,
        data_dir: Path | None = None,
        install_on_start: bool = True,
    ):
        self.host = host
        self.graphname = graphname
        self.conn = None
        self.query_timeout = query_timeout
        self.data_dir = data_dir
        self._conn_kwargs = dict(
            host=host,
            graphname=graphname,
            username=username,
            password=password,
            token=token,
            apiToken=secret,
            useToken=use_token,
        )
        self._refresh_conn()
        if install_on_start:
            try:
                self._ensure_installed()
            except Exception as exc:  # noqa: BLE001
                print(f"[tigergraph] install deferred: {exc}")

    def _refresh_conn(self) -> None:
        from pyTigerGraph import TigerGraphConnection

        self.conn = TigerGraphConnection(**self._conn_kwargs)
        with contextlib.suppress(Exception):
            self.conn.getToken(self.conn.createSecret())

    def _ensure_installed(self) -> None:
        installed = {q["name"] for q in self.conn.queryInstalledQueries()}
        for name in (
            "get_txn",
            "card_history",
            "card_window",
            "shared_devices",
            "shared_regions",
            "related_transactions",
            "historical_cases",
            "degree_of",
            "connected_entities",
            "write_fraud_case",
        ):
            if name not in installed:
                script = gsql.SCHEMA_GSQL.replace("@@graphname@@", self.graphname)
                self.conn.gsql(script)
                break
        # queries
        script = gsql.QUERIES_GSQL.replace("@@graphname@@", self.graphname)
        self.conn.gsql(script)

    # --------------------------------------------------------------- lifecycle
    def health(self) -> dict[str, Any]:
        try:
            ver = self.conn.getVersion()
            return {"backend": "tigergraph", "status": "ok", "version": ver}
        except Exception as exc:  # noqa: BLE001
            raise GraphUnavailableError(f"tigergraph unreachable: {exc}") from exc

    def install_schema(self) -> None:
        script = gsql.SCHEMA_GSQL.replace("@@graphname@@", self.graphname)
        self.conn.gsql(script)
        self.conn.gsql(gsql.LOAD_JOBS_GSQL.replace("@@graphname@@", self.graphname))
        self.conn.gsql(gsql.QUERIES_GSQL.replace("@@graphname@@", self.graphname))

    def load_dataset(self) -> dict[str, Any]:
        if not self.data_dir:
            return {"backend": "tigergraph", "loaded": False, "error": "no data_dir configured"}
        files = {
            "load_ravel": {
                "f_customer": "customers.csv",
                "f_card": "cards.csv",
                "f_txn": "transactions.csv",
                "f_device": "devices.csv",
                "f_email": "email_domains.csv",
                "f_region": "billing_regions.csv",
                "f_closed": "closed_cases.csv",
                "f_closed_txn": "closed_case_txn.csv",
                "f_next": "next_edges.csv",
            }
        }
        results = {}
        for job, tags in files.items():
            for tag, filename in tags.items():
                path = self.data_dir / filename
                if not path.exists():
                    continue
                try:
                    resp = self.conn.runLoadingJobWithFile(
                        job, str(path), tag, timeout=self.query_timeout * 10
                    )
                    results[filename] = {"status": "ok", "resp": resp}
                except Exception as exc_category:  # noqa: BLE001
                    results[filename] = {"status": "error", "error": str(exc_category)}
        return {"backend": "tigergraph", "loaded": True, "files": results}

    def is_loaded(self) -> bool:
        try:
            stats = self.conn.getVertexStats()
            return stats.get(self.graphname, {}).get("Transaction", {}).get("count", 0) > 0
        except Exception:
            return False

    def _run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        start = time.time()
        try:
            res = self.conn.runInstalledQuery(query, params, timeout=self.query_timeout)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "timeout" in msg.lower() or "timed out" in msg.lower():
                raise GraphTimeoutError(f"{query} timed out") from exc
            raise GraphUnavailableError(f"{query} failed: {msg}") from exc
        time.time() - start
        return _norm_list(res)

    # ----------------------------------------------------------- investigation
    def get_transaction(self, txn_id: str) -> dict[str, Any]:
        rows = self._run("get_txn", txn_id=txn_id)
        if not rows:
            raise KeyError(f"transaction {txn_id} not found")
        r = rows[0]
        return {
            "txn_id": r.get("txn_id") or txn_id,
            "ts": r.get("ts", ""),
            "amount": r.get("amount", 0.0),
            "product_cd": r.get("product_cd", ""),
            "channel": r.get("channel", ""),
            "risk_score": r.get("risk_score", 0.0),
            "customer_id": r.get("customer_id", ""),
            "card_id": r.get("card_id", ""),
            "card6": r.get("card6", ""),
            "addr1": r.get("addr1", ""),
            "addr2": r.get("addr2", ""),
            "p_email_domain": r.get("p_email", ""),
            "device_id": r.get("device_id", ""),
            "device_profile": "",
            "device_new": "",
            "device_type": "",
            "device_proxy": "",
            "email_conflict": bool(r.get("email_conflict", False)),
        }

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        self._run("card_history", customer_id=customer_id, limit=1)
        n_txns = self._run("degree_of", entity_id=customer_id, kind=0)
        deg = n_txns[0].get("value", 0) if n_txns else 0
        return {
            "customer_id": customer_id,
            "card_label": f"{customer_id}-K1",
            "n_transactions": deg,
            "n_online": 0,
        }

    def card_history(self, customer_id: str, limit: int = 25) -> list[dict[str, Any]]:
        rows = self._run("card_history", customer_id=customer_id, limit=limit)
        return self._txns(rows)

    def card_window(self, customer_id: str, hours: float = 2.0, limit: int = 50) -> list[dict[str, Any]]:
        latest = self._run("card_history", customer_id=customer_id, limit=1)
        if not latest:
            return []
        anchor = latest[0]["ts"]
        rows = self._run(
            "card_window", customer_id=customer_id, anchor_ts=anchor, hours=int(hours), limit=limit
        )
        return self._txns(rows)

    def connected_entities(self, customer_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._run("connected_entities", customer_id=customer_id, limit=limit)
        out: list[dict[str, Any]] = []
        for r in rows:
            for k, v in r.items():
                if isinstance(v, list):
                    for item in v[:limit]:
                        out.append({"id": str(item), "type": k, "label": str(item)})
        return out

    def shared_devices(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._run("shared_devices", customer_id=customer_id, limit=limit)
        return [
            {
                "device_id": r.get("device_id", ""),
                "device_profile": r.get("device_profile", r.get("dev_profile", "")),
                "other_customer_id": r.get("customer_id", ""),
                "other_card_id": r.get("card_id", ""),
                "device_new": r.get("device_new", ""),
                "device_proxy": r.get("device_proxy", ""),
                "shared_txns": r.get("shared_txns", 1),
                "last_seen": r.get("ts", ""),
            }
            for r in rows
        ]

    def shared_regions(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._run("shared_regions", customer_id=customer_id, limit=limit)
        return self._txns(rows)

    def related_transactions(
        self, customer_id: str, window_days: float = 7.0, limit: int = 100
    ) -> list[dict[str, Any]]:
        latest = self._run("card_history", customer_id=customer_id, limit=1)
        from_ts = "2016-01-01 00:00:00"
        if latest:
            try:
                from datetime import datetime, timedelta

                from_ts = (
                    datetime.strptime(latest[0]["ts"][:19], "%Y-%m-%d %H:%M:%S") - timedelta(days=window_days)
                ).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:  # noqa: BLE001
                pass
        rows = self._run("related_transactions", customer_id=customer_id, from_ts=from_ts, limit=limit)
        return self._txns(rows)

    def historical_cases(
        self, customer_id: str = "", outcome: str = "", pattern: str = "", limit: int = 20
    ) -> list[dict[str, Any]]:
        rows = self._run(
            "historical_cases", customer_id=customer_id, outcome=outcome, pattern=pattern, limit=limit
        )
        return [{k: (v if isinstance(v, (str, int, float)) else str(v)) for k, v in r.items()} for r in rows]

    def transaction_neighborhood(self, txn_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        root = self.get_transaction(txn_id)
        # shared-device expansion for the customer
        rows = self._run(
            "related_transactions",
            customer_id=root["customer_id"],
            from_ts="2016-07-01 00:00:00",
            limit=limit,
        )
        return [root, *self._txns(rows[: limit - 1])]

    def high_degree_check(self, entity_id: str) -> bool:
        kind = 1 if entity_id.startswith("DEV-") else 0
        rows = self._run("degree_of", entity_id=entity_id, kind=kind)
        deg = rows[0].get("value", 0) if rows else 0
        return int(deg) > 2000

    def write_case(self, case: dict[str, Any]) -> str:
        import uuid

        gid = case.get("graph_case_id") or f"CASE-2016-{uuid.uuid4().hex[:8].upper()}"
        try:
            self._run(
                "write_fraud_case",
                graph_case_id=gid,
                case_id=case.get("case_id", ""),
                customer_id=case.get("customer_id", ""),
                verdict=case.get("verdict", ""),
                pattern=case.get("pattern", ""),
                exposure_usd=float(case.get("exposure_usd", 0.0)),
                summary=case.get("summary", ""),
                card_ids=case.get("connected_card_ids", []),
                txn_ids=case.get("affected_txn_ids", []),
            )
        except GraphUnavailableError:
            raise
        return gid

    def subgraph_for_viz(self, root: str, depth: int = 2, limit: int = 100) -> dict[str, Any]:
        try:
            txn = self.get_transaction(root)
        except KeyError:
            return {"nodes": [], "edges": []}
        nodes = [
            {
                "id": root,
                "type": "transaction",
                "label": f"${txn['amount']:.2f}",
                "risk": txn.get("risk_score", 0),
            }
        ]
        edges: list[dict[str, Any]] = []
        nodes.append({"id": txn["customer_id"], "type": "customer", "label": txn["customer_id"]})
        edges.append({"from": root, "to": txn["customer_id"], "type": "MADE_BY"})
        for r in self._run("card_history", customer_id=txn["customer_id"], limit=min(15, limit)):
            nid = str(r.get("txn_id", ""))
            if nid:
                nodes.append(
                    {"id": nid, "type": "transaction", "label": f"${r.get('amount', 0):.2f}", "risk": 0}
                )
                edges.append({"from": nid, "to": txn["customer_id"], "type": "MADE_BY"})
        return {"nodes": nodes, "edges": edges}

    def _txns(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "txn_id": r.get("txn_id", ""),
                "ts": r.get("ts", ""),
                "amount": r.get("amount", 0.0),
                "product_cd": r.get("product_cd", ""),
                "channel": r.get("channel", ""),
                "risk_score": r.get("risk_score", 0.0),
                "customer_id": r.get("customer_id", ""),
                "card_id": r.get("card_id", ""),
                "card6": r.get("card6", ""),
                "addr1": r.get("addr1", ""),
                "addr2": r.get("addr2", ""),
                "p_email_domain": r.get("p_email", ""),
                "device_id": r.get("device_id", ""),
                "device_profile": r.get("device_profile", ""),
                "email_conflict": bool(r.get("email_conflict", False)),
            }
            for r in rows
        ]
