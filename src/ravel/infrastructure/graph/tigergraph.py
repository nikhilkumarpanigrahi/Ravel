"""TigerGraph (Savanna / Community Edition) adapter.

Implements :class:`GraphAdapter` against a real TigerGraph instance through pyTigerGraph.
Each bounded investigation query maps to an installed GSQL query from ``gsql_scripts``.
"""

from __future__ import annotations

import contextlib
import json
import time
from datetime import UTC
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
        for _key, value in (packet or {}).items():
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict):
                        attrs = row.get("attributes")
                        if isinstance(attrs, dict):
                            flattened = {k: _clean(v) for k, v in attrs.items()}
                            flattened["v_id"] = str(row.get("v_id", ""))
                            flattened["v_type"] = str(row.get("v_type", ""))
                            out.append(flattened)
                        else:
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


def _edge_target(edges: list[dict[str, Any]], *edge_types: str) -> str:
    """Return the first adjacent vertex reached through one of ``edge_types``."""
    wanted = set(edge_types)
    return str(next((edge.get("to_id", "") for edge in edges if edge.get("e_type") in wanted), ""))


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
        install_on_start: bool = False,
    ):
        self.host = host
        self.graphname = graphname
        self.username = username
        self.password = password
        self.token = token
        self.secret = secret
        self.use_token = use_token
        self.query_timeout = query_timeout
        self.data_dir = data_dir
        self.conn = None
        self._installed_cache: set[str] | None = None
        self._shared_devices_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._refresh_conn()
        if install_on_start:
            try:
                self._ensure_installed()
            except Exception as exc:  # noqa: BLE001
                print(f"[tigergraph] install deferred: {exc}")

    def _refresh_conn(self) -> None:
        from pyTigerGraph import TigerGraphConnection

        # Handle TG 4.x / Savanna Cloud JWT token exchange
        if self.secret and not self.token:
            try:
                import requests

                url = f"{self.host.rstrip('/')}/gsql/v1/tokens"
                resp = requests.post(url, json={"secret": self.secret}, timeout=self.query_timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data.get("token") or ""
            except Exception as exc:  # noqa: BLE001
                print(f"[tigergraph] JWT token exchange failed: {exc}")

        is_tg_cloud = "tgcloud.io" in self.host
        conn_kwargs: dict[str, Any] = dict(
            host=self.host,
            graphname=self.graphname,
            username=self.username,
            password=self.password,
            apiToken=self.token or self.secret,
            tgCloud=is_tg_cloud,
        )
        self.conn = TigerGraphConnection(**conn_kwargs)
        if self.token:
            self.conn.apiToken = self.token
            self.conn.authHeader = {"Authorization": f"Bearer {self.token}"}

    def _ensure_installed(self) -> None:
        installed = {q["name"] for q in self.conn.queryInstalledQueries()}
        required = {
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
        }
        if required - installed:
            script = gsql.QUERIES_GSQL.replace("@@graphname@@", self.graphname)
            self.conn.gsql(script)
            self._installed_cache = None

    # --------------------------------------------------------------- lifecycle
    def health(self) -> dict[str, Any]:
        try:
            echo = self.conn.echo()
            version: Any = None
            with contextlib.suppress(Exception):
                version = self.conn.getVersion()
            return {
                "backend": "tigergraph",
                "status": "ok",
                "echo": echo,
                "version": version,
            }
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
        self.data_dir = Path(self.data_dir)
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
        missing: list[str] = []
        for job, tags in files.items():
            for tag, filename in tags.items():
                path = self.data_dir / filename
                if not path.exists():
                    missing.append(filename)
                    continue
                try:
                    resp = self.conn.runLoadingJobWithFile(
                        job, str(path), tag, timeout=self.query_timeout * 10
                    )
                    results[filename] = {"status": "ok", "resp": resp}
                except Exception as exc_category:  # noqa: BLE001
                    results[filename] = {"status": "error", "error": str(exc_category)}
        failed = [name for name, result in results.items() if result["status"] == "error"]
        return {
            "backend": "tigergraph",
            "loaded": not missing and not failed,
            "files": results,
            "missing_files": missing,
            "failed_files": failed,
        }

    def is_loaded(self) -> bool:
        try:
            return int(self.conn.getVertexCount("Transaction")) > 0
        except Exception:
            return False

    def _has_query(self, name: str) -> bool:
        if self._installed_cache is None:
            try:
                installed = self.conn.getInstalledQueries() or {}
                self._installed_cache = {k.split("/")[-1] for k in installed}
            except Exception:
                self._installed_cache = set()
        return name in self._installed_cache

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
        if self._has_query("get_txn"):
            with contextlib.suppress(Exception):
                rows = self._run("get_txn", txn_id=txn_id)
                if rows:
                    r = rows[0]
                    return {
                        "txn_id": str(r.get("txn_id") or txn_id),
                        "ts": r.get("ts", ""),
                        "amount": float(r.get("amount", 0.0)),
                        "product_cd": r.get("product_cd", ""),
                        "channel": r.get("channel", ""),
                        "risk_score": float(r.get("risk_score", 0.0)),
                        "customer_id": r.get("customer_id", ""),
                        "card_id": r.get("card_id", ""),
                        "card6": r.get("card6", ""),
                        "addr1": str(r.get("addr1", "")),
                        "addr2": str(r.get("addr2", "")),
                        "p_email_domain": r.get("p_email", ""),
                        "device_id": r.get("device_id", ""),
                        "device_profile": "",
                        "device_new": "",
                        "device_type": "",
                        "device_proxy": "",
                        "email_conflict": bool(r.get("email_conflict", False)),
                    }

        # Native REST++ query fallback
        try:
            tid = int(txn_id) if txn_id.isdigit() else txn_id
            res = self.conn.getVerticesById("Transaction", tid)
            if not res:
                raise KeyError(f"transaction {txn_id} not found")
            attrs = res[0].get("attributes", {})
            edges = self.conn.getEdges("Transaction", tid) or []
            # The supplied HHGOA graph uses the lower-case names; the upper-case
            # aliases keep compatibility with graphs created by older RAVEL scripts.
            cust_id = _edge_target(edges, "transaction_of_customer", "CARD_OF")
            card_id = _edge_target(edges, "transaction_of_card", "MADE_BY")
            dev_id = _edge_target(edges, "transaction_uses_device", "FROM_DEVICE")
            p_email = _edge_target(edges, "transaction_has_p_emaildomain", "PURCHASER_EMAIL")

            return {
                "txn_id": str(attrs.get("transaction_id", txn_id)),
                "ts": str(attrs.get("ts", "")),
                "amount": float(attrs.get("transaction_amt", 0.0)),
                "product_cd": str(attrs.get("product_cd", "")),
                "channel": str(attrs.get("channel", "")),
                "risk_score": float(attrs.get("risk_score", 0.0)),
                "customer_id": cust_id,
                "card_id": card_id,
                "card6": str(attrs.get("card6", "")),
                "addr1": str(attrs.get("addr1", "")),
                "addr2": str(attrs.get("addr2", "")),
                "p_email_domain": p_email,
                "device_id": dev_id,
                "device_profile": str(attrs.get("device_profile", "")),
                "device_new": str(attrs.get("device_new", "")),
                "device_type": str(attrs.get("device_type", "")),
                "device_proxy": str(attrs.get("device_proxy", "")),
                "email_conflict": bool(attrs.get("email_conflict", 0)),
            }
        except Exception as exc:
            raise KeyError(f"transaction {txn_id} not found: {exc}") from exc

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        if not customer_id:
            return {
                "customer_id": "",
                "card_label": "",
                "n_transactions": 0,
                "n_online": 0,
            }
        if self._has_query("degree_of"):
            with contextlib.suppress(Exception):
                n_txns = self._run("degree_of", entity_id=customer_id, kind=0)
                deg = n_txns[0].get("value", 0) if n_txns else 0
                return {
                    "customer_id": customer_id,
                    "card_label": f"{customer_id}-K1",
                    "n_transactions": deg,
                    "n_online": 0,
                }
        edges = self.conn.getEdges("Customer", customer_id) or []
        txn_edges = [e for e in edges if e.get("e_type") == "transaction_of_customer"]
        return {
            "customer_id": customer_id,
            "card_label": f"{customer_id}-K1",
            "n_transactions": len(txn_edges),
            "n_online": 0,
        }

    def card_history(self, customer_id: str, limit: int = 25) -> list[dict[str, Any]]:
        if not customer_id:
            return []
        if self._has_query("card_history"):
            with contextlib.suppress(Exception):
                rows = self._run("card_history", customer_id=customer_id, limit=limit)
                return self._txns(rows)

        # Native REST++ query fallback
        edges = self.conn.getEdges("Customer", customer_id) or []
        txn_ids = [
            int(e["to_id"]) if e["to_id"].isdigit() else e["to_id"]
            for e in edges
            if e.get("e_type") == "transaction_of_customer"
        ]
        if not txn_ids:
            return []
        v_list = self.conn.getVerticesById("Transaction", txn_ids[: limit * 3]) or []
        rows = []
        for v in v_list:
            a = v.get("attributes", {})
            rows.append(
                {
                    "txn_id": str(a.get("transaction_id", v.get("v_id", ""))),
                    "ts": str(a.get("ts", "")),
                    "amount": float(a.get("transaction_amt", 0.0)),
                    "product_cd": str(a.get("product_cd", "")),
                    "channel": str(a.get("channel", "")),
                    "risk_score": float(a.get("risk_score", 0.0)),
                    "customer_id": customer_id,
                    "card_id": f"{customer_id}-K1",
                    "card6": str(a.get("card6", "")),
                    "addr1": str(a.get("addr1", "")),
                    "addr2": str(a.get("addr2", "")),
                    "p_email_domain": "",
                    "device_id": "",
                    "device_profile": str(a.get("device_profile", "")),
                    "device_new": str(a.get("device_new", "")),
                    "device_type": str(a.get("device_type", "")),
                    "device_proxy": str(a.get("device_proxy", "")),
                    "email_conflict": bool(a.get("email_conflict", 0)),
                }
            )
        rows.sort(key=lambda x: str(x.get("ts", "")), reverse=True)
        return rows[:limit]

    def card_window(
        self,
        customer_id: str,
        anchor_ts: str = "",
        hours: float = 2.0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        anchor_str = anchor_ts
        if not anchor_str:
            latest = self.card_history(customer_id=customer_id, limit=1)
            if not latest:
                return []
            anchor_str = latest[0]["ts"]
        if self._has_query("card_window"):
            with contextlib.suppress(Exception):
                rows = self._run(
                    "card_window",
                    customer_id=customer_id,
                    anchor_ts=anchor_str,
                    hours=int(hours),
                    limit=limit,
                )
                return self._txns(rows)

        # Native REST++ filtering fallback
        all_hist = self.card_history(customer_id=customer_id, limit=limit * 2)
        try:
            from datetime import datetime, timedelta

            anchor_dt = datetime.fromisoformat(anchor_str[:19])
            start_dt = anchor_dt - timedelta(hours=hours)
            win = [t for t in all_hist if start_dt <= datetime.fromisoformat(t["ts"][:19]) <= anchor_dt]
            win.sort(key=lambda x: str(x.get("ts", "")))
            return win[:limit]
        except Exception:
            return all_hist[:limit]

    def connected_entities(self, customer_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        if not customer_id:
            return []
        if self._has_query("connected_entities"):
            with contextlib.suppress(Exception):
                rows = self._run("connected_entities", customer_id=customer_id, limit=limit)
                out: list[dict[str, Any]] = []
                for r in rows:
                    for k, v in r.items():
                        if isinstance(v, list):
                            for item in v[:limit]:
                                out.append({"id": str(item), "type": k, "label": str(item)})
                return out

        # Native fallback
        edges = self.conn.getEdges("Customer", customer_id) or []
        out = []
        for e in edges[:limit]:
            out.append(
                {"id": str(e.get("to_id")), "type": str(e.get("to_type")), "label": str(e.get("to_id"))}
            )
        return out

    def shared_devices(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        cache_key = (customer_id, limit)
        cache = getattr(self, "_shared_devices_cache", {})
        if cache_key in cache:
            return [dict(row) for row in cache[cache_key]]
        if self._has_query("shared_devices"):
            with contextlib.suppress(Exception):
                rows = self._run("shared_devices", customer_id=customer_id, limit=limit)
                rows_out = [
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
                cache[cache_key] = rows_out
                self._shared_devices_cache = cache
                return [dict(row) for row in rows_out]

        # Bounded native traversal for the supplied HHGOA schema:
        # Customer -> Transaction -> Device -> Transaction -> other Customer/Card.
        customer_edges = self.conn.getEdges("Customer", customer_id) or []
        source_txn_ids = [
            str(edge.get("to_id"))
            for edge in customer_edges
            if edge.get("e_type") == "transaction_of_customer"
        ][:100]
        source_vertices = (
            self.conn.getVerticesById(
                "Transaction",
                [int(txn_id) if txn_id.isdigit() else txn_id for txn_id in source_txn_ids],
            )
            if source_txn_ids
            else []
        ) or []
        online_txn_ids = {
            str(vertex.get("v_id", ""))
            for vertex in source_vertices
            if vertex.get("attributes", {}).get("device_profile")
            or vertex.get("attributes", {}).get("device_type")
        }
        device_ids: set[str] = set()
        for txn_id in source_txn_ids:
            if txn_id not in online_txn_ids:
                continue
            txn_edges = self.conn.getEdges("Transaction", txn_id) or []
            device_id = _edge_target(txn_edges, "transaction_uses_device", "FROM_DEVICE")
            if device_id:
                device_ids.add(device_id)
            if len(device_ids) >= 50:
                break

        shared: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for device_id in sorted(device_ids):
            device_vertices = self.conn.getVerticesById("Device", device_id) or []
            device_attrs = device_vertices[0].get("attributes", {}) if device_vertices else {}
            device_edges = self.conn.getEdges("Device", device_id) or []
            for device_edge in device_edges[: min(max(limit * 4, 20), 200)]:
                if device_edge.get("e_type") != "transaction_uses_device":
                    continue
                other_txn_id = str(device_edge.get("to_id", ""))
                other_edges = self.conn.getEdges("Transaction", other_txn_id) or []
                other_customer = _edge_target(other_edges, "transaction_of_customer", "CARD_OF")
                if not other_customer or other_customer == customer_id:
                    continue
                key = (device_id, other_customer)
                if key in seen:
                    continue
                seen.add(key)
                txn_vertices = self.conn.getVerticesById("Transaction", other_txn_id) or []
                txn_attrs = txn_vertices[0].get("attributes", {}) if txn_vertices else {}
                shared.append(
                    {
                        "device_id": device_id,
                        "device_profile": str(device_attrs.get("dev_profile", "")),
                        "other_customer_id": other_customer,
                        "other_card_id": _edge_target(other_edges, "transaction_of_card", "MADE_BY"),
                        "device_new": str(txn_attrs.get("device_new", "")),
                        "device_proxy": str(txn_attrs.get("device_proxy", "")),
                        "shared_txns": 1,
                        "last_seen": str(txn_attrs.get("ts", "")),
                    }
                )
                if len(shared) >= limit:
                    cache[cache_key] = shared
                    self._shared_devices_cache = cache
                    return shared
        cache[cache_key] = shared
        self._shared_devices_cache = cache
        return shared

    def shared_regions(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self._has_query("shared_regions"):
            with contextlib.suppress(Exception):
                rows = self._run("shared_regions", customer_id=customer_id, limit=limit)
                return self._txns(rows)
        return []

    def related_transactions(
        self, customer_id: str, window_days: float = 7.0, limit: int = 100
    ) -> list[dict[str, Any]]:
        if self._has_query("related_transactions"):
            latest = self.card_history(customer_id=customer_id, limit=1)
            from_ts = "2016-01-01 00:00:00"
            if latest:
                try:
                    from datetime import datetime, timedelta

                    from_ts = (
                        datetime.strptime(latest[0]["ts"][:19], "%Y-%m-%d %H:%M:%S")
                        - timedelta(days=window_days)
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:  # noqa: BLE001
                    pass
            with contextlib.suppress(Exception):
                rows = self._run(
                    "related_transactions", customer_id=customer_id, from_ts=from_ts, limit=limit
                )
                return self._txns(rows)
        return self.card_history(customer_id=customer_id, limit=limit)

    def historical_cases(
        self, customer_id: str = "", outcome: str = "", pattern: str = "", limit: int = 20
    ) -> list[dict[str, Any]]:
        if self._has_query("historical_cases"):
            with contextlib.suppress(Exception):
                rows = self._run(
                    "historical_cases", customer_id=customer_id, outcome=outcome, pattern=pattern, limit=limit
                )
                return [
                    {k: (v if isinstance(v, (str, int, float)) else str(v)) for k, v in r.items()}
                    for r in rows
                ]

        # Native REST++ query fallback. When a customer is supplied, follow the
        # persisted case_of_customer relationship rather than returning arbitrary
        # recent cases and calling them relevant.
        if customer_id:
            customer_edges = self.conn.getEdges("Customer", customer_id) or []
            case_ids = [
                str(edge.get("to_id", ""))
                for edge in customer_edges
                if edge.get("e_type") == "case_of_customer" and edge.get("to_type") == "FraudCase"
            ][: limit * 2]
            cases = self.conn.getVerticesById("FraudCase", case_ids) if case_ids else []
        else:
            cases = self.conn.getVertices("FraudCase", limit=limit * 2) or []
        out_cases: list[dict[str, Any]] = []
        for c in cases:
            attrs = c.get("attributes", {})
            if outcome and attrs.get("outcome") != outcome:
                continue
            if pattern and attrs.get("pattern") != pattern:
                continue
            out_cases.append(
                {k: (v if isinstance(v, (str, int, float)) else str(v)) for k, v in attrs.items()}
            )
            if len(out_cases) >= limit:
                break
        return out_cases

    def transaction_neighborhood(self, txn_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        root = self.get_transaction(txn_id)
        cust_id = root.get("customer_id")
        if cust_id:
            hist = self.card_history(customer_id=cust_id, limit=limit - 1)
            return [root, *[t for t in hist if t.get("txn_id") != root.get("txn_id")]]
        return [root]

    def high_degree_check(self, entity_id: str) -> bool:
        if not entity_id:
            return False
        kind = 1 if entity_id.startswith("DEV-") else 0
        if self._has_query("degree_of"):
            with contextlib.suppress(Exception):
                rows = self._run("degree_of", entity_id=entity_id, kind=kind)
                deg = rows[0].get("value", 0) if rows else 0
                return int(deg) > 2000
        edges = self.conn.getEdges("Customer" if kind == 0 else "Device", entity_id) or []
        return len(edges) > 2000

    def write_case(self, case: dict[str, Any]) -> str:
        import uuid

        gid = case.get("graph_case_id") or f"CASE-2016-{uuid.uuid4().hex[:8].upper()}"
        if self._has_query("write_fraud_case"):
            with contextlib.suppress(Exception):
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
                return gid

        # Native REST++ upsert
        try:
            from datetime import datetime

            now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            self.conn.upsertVertex(
                "FraudCase",
                gid,
                attributes={
                    "opened_at": now_str,
                    "closed_at": now_str,
                    "outcome": case.get("verdict", "investigated"),
                    "pattern": case.get("pattern", "none"),
                    "txn_ids": json.dumps(case.get("affected_txn_ids", [])),
                    "n_txns": len(case.get("affected_txn_ids", [])),
                    "exposure_usd": float(case.get("exposure_usd", 0.0)),
                    "connected_card_ids": json.dumps(case.get("connected_card_ids", [])),
                    "actions_taken": json.dumps(case.get("actions_taken", [])),
                    "report_filed": bool(case.get("report_filed", False)),
                    "summary": (case.get("summary") or "")[:1000],
                },
            )
            customer_id = str(case.get("customer_id", ""))
            if customer_id:
                self.conn.upsertEdge("FraudCase", gid, "case_of_customer", "Customer", customer_id)
            card_ids = {
                str(card_id)
                for card_id in [case.get("card_id"), *case.get("connected_card_ids", [])]
                if card_id
            }
            for card_id in card_ids:
                self.conn.upsertEdge("FraudCase", gid, "case_of_card", "Card", card_id)
            txn_ids = [str(txn_id) for txn_id in case.get("affected_txn_ids", []) if txn_id]
            if txn_ids:
                self.conn.upsertEdge(
                    "FraudCase",
                    gid,
                    "case_first_fraud_transaction",
                    "Transaction",
                    txn_ids[0],
                )
        except Exception as exc:  # noqa: BLE001
            raise GraphUnavailableError(f"case memory write failed: {exc}") from exc
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
        cust_id = txn.get("customer_id")
        if cust_id:
            nodes.append({"id": cust_id, "type": "customer", "label": cust_id})
            edges.append({"from": root, "to": cust_id, "type": "MADE_BY"})
            for r in self.card_history(customer_id=cust_id, limit=min(15, limit)):
                nid = str(r.get("txn_id", ""))
                if nid:
                    nodes.append(
                        {"id": nid, "type": "transaction", "label": f"${r.get('amount', 0):.2f}", "risk": 0}
                    )
                    edges.append({"from": nid, "to": cust_id, "type": "MADE_BY"})
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
