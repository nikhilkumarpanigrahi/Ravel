"""SQLite-backed graph adapter.

Provides the full :class:`GraphAdapter` contract over the normalized level0 datasets so the
application, agent, benchmark, and UI work identically with or without a live TigerGraph
instance (dev / test / demo mode). The TigerGraph adapter implements the same contract
against Savanna.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from ravel.infrastructure.graph.base import GraphAdapter, GraphUnavailableError

PROFILE = "profile"


class MockGraphAdapter(GraphAdapter):
    def __init__(self, data_dir: Path, rebuild: bool = False, high_degree_threshold: int = 2000):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "ravel_mock.db"
        self.high_degree_threshold = high_degree_threshold
        self._conn: sqlite3.Connection | None = None
        if rebuild or not self.db_path.exists():
            self._build()
        else:
            self._open()
            if not self._schema_exists():
                self._conn.close()
                self._build()

    # ------------------------------------------------------------------ setup
    def _open(self) -> None:
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-64000")
        self._conn.execute("PRAGMA temp_store=MEMORY")
        if self._schema_exists():
            self._ensure_runtime_indexes()

    def _schema_exists(self) -> bool:
        """Whether this SQLite database has been initialized with the graph schema."""
        row = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'transactions'"
        ).fetchone()
        return row is not None

    def _ensure_runtime_indexes(self) -> None:
        """Install indexes added after the initial schema, once tables exist."""
        with self._conn:
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_txn_cust_ts ON transactions(customer_id, ts DESC)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_txn_dev_cust ON transactions(device_id, customer_id)"
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS ix_txn_card ON transactions(card_id)")

    def _build(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        self._open()
        cur = self._conn
        cur.executescript(
            """
            CREATE TABLE transactions(
                TransactionID INTEGER PRIMARY KEY,
                TransactionDT INTEGER, ts TEXT, TransactionAmt REAL, ProductCD TEXT,
                channel TEXT, risk_score REAL, customer_id TEXT, card_id TEXT, card1 TEXT,
                card6 TEXT, addr1 TEXT, addr2 TEXT, P_emaildomain TEXT, R_emaildomain TEXT,
                device_id TEXT, device_profile TEXT, device_type TEXT, device_new TEXT,
                device_proxy TEXT, email_conflict INTEGER
            );
            CREATE TABLE customers(
                customer_id TEXT PRIMARY KEY, card_label TEXT, card1 TEXT, card6 TEXT, home_region TEXT
            );
            CREATE TABLE devices(device_id TEXT PRIMARY KEY, dev_profile TEXT, device_type TEXT);
            CREATE TABLE email_domains(email_domain TEXT PRIMARY KEY);
            CREATE TABLE billing_regions(region_id TEXT PRIMARY KEY);
            CREATE TABLE closed_cases(
                case_id TEXT PRIMARY KEY, customer_id TEXT, card_id TEXT, opened_at TEXT,
                closed_at TEXT, outcome TEXT, pattern TEXT, first_fraud_txn_id TEXT,
                txn_ids TEXT, n_txns INTEGER, exposure_usd REAL, connected_card_ids TEXT,
                actions_taken TEXT, report_filed TEXT, summary TEXT
            );
            CREATE TABLE closed_case_txn(case_id TEXT, txn_id TEXT);
            CREATE TABLE next_edges(from_txn INTEGER, to_txn INTEGER, card_id TEXT, secs REAL);
            CREATE TABLE graph_cases(
                graph_case_id TEXT PRIMARY KEY, case_id TEXT, customer_id TEXT, verdict TEXT,
                pattern TEXT, exposure_usd REAL, affected_txn_ids TEXT, connected_card_ids TEXT,
                device_profiles TEXT, summary TEXT, created_at TEXT, payload TEXT
            );
            CREATE INDEX ix_txn_customer ON transactions(customer_id);
            CREATE INDEX ix_txn_device ON transactions(device_id);
            CREATE INDEX ix_txn_ts ON transactions(ts);
            CREATE INDEX ix_txn_addr1 ON transactions(addr1);
            CREATE INDEX ix_cct_case ON closed_case_txn(case_id);
            CREATE INDEX ix_cct_txn ON closed_case_txn(txn_id);
            CREATE INDEX ix_cc_customer ON closed_cases(customer_id);
            """
        )
        self._ensure_runtime_indexes()
        self._load()
        self._conn.commit()

    def _load(self) -> None:
        self._load_csv("transactions.csv", "transactions")
        self._load_csv("customers.csv", "customers")
        self._load_csv("devices.csv", "devices")
        self._load_csv("email_domains.csv", "email_domains")
        self._load_csv("billing_regions.csv", "billing_regions")
        self._load_csv("closed_cases.csv", "closed_cases")
        self._load_csv("next_edges.csv", "next_edges")
        # closed_case_txn links
        closed = self.data_dir / "closed_cases.csv"
        if closed.exists():
            with open(closed, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    for t in row.get("txn_ids", "").split("|"):
                        if t:
                            self._conn.execute(
                                "INSERT OR IGNORE INTO closed_case_txn VALUES (?, ?)", (row["case_id"], t)
                            )

    def _load_csv(self, name: str, table: str) -> None:
        path = self.data_dir / name
        if not path.exists():
            return
        cols = []
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                cols = header
        if not cols:
            return
        placeholders = ",".join("?" * len(cols))
        stmt = f"INSERT OR IGNORE INTO {table}({','.join(cols)}) VALUES ({placeholders})"
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            batch: list[list[str]] = []
            for row in reader:
                batch.append(row)
                if len(batch) >= 50000:
                    self._conn.executemany(stmt, batch)
                    batch = []
            if batch:
                self._conn.executemany(stmt, batch)

    # ------------------------------------------------------------------ base
    def health(self) -> dict[str, Any]:
        try:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()
            return {"backend": "mock", "status": "ok", "transactions": row["n"]}
        except Exception as exc:  # noqa: BLE001
            raise GraphUnavailableError(f"mock db unavailable: {exc}") from exc

    def install_schema(self) -> None:
        return None

    def load_dataset(self) -> dict[str, Any]:
        return {"backend": "mock", "loaded": True}

    def is_loaded(self) -> bool:
        try:
            return self.health()["transactions"] > 0
        except Exception:
            return False

    def _q(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _q1(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _tx2dict(self, r: dict[str, Any]) -> dict[str, Any]:
        return {
            "txn_id": str(r["TransactionID"]),
            "ts": r["ts"],
            "amount": r["TransactionAmt"],
            "product_cd": r["ProductCD"],
            "channel": r["channel"],
            "risk_score": r["risk_score"],
            "customer_id": r["customer_id"],
            "card_id": r["card_id"],
            "card6": r["card6"],
            "addr1": r["addr1"],
            "addr2": r["addr2"],
            "p_email_domain": r["P_emaildomain"],
            "r_email_domain": r["R_emaildomain"],
            "device_id": r["device_id"],
            "device_profile": r["device_profile"],
            "device_type": r["device_type"],
            "device_new": r["device_new"],
            "device_proxy": r["device_proxy"],
            "email_conflict": r["email_conflict"] == 1,
        }

    # ----------------------------------------------------------- investigation
    def get_transaction(self, txn_id: str) -> dict[str, Any]:
        r = self._q1("SELECT * FROM transactions WHERE TransactionID = ?", (int(txn_id),))
        if not r:
            raise KeyError(f"transaction {txn_id} not found")
        return self._tx2dict(r)

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        r = self._q1("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
        if not r:
            raise KeyError(f"customer {customer_id} not found")
        d = dict(r)
        d["n_transactions"] = self._q1(
            "SELECT COUNT(*) AS n FROM transactions WHERE customer_id = ?", (customer_id,)
        )["n"]
        d["n_online"] = self._q1(
            "SELECT COUNT(*) AS n FROM transactions WHERE customer_id = ? AND channel='online'",
            (customer_id,),
        )["n"]
        return d

    def card_history(self, customer_id: str, limit: int = 25) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT * FROM transactions WHERE customer_id = ? ORDER BY ts DESC LIMIT ?",
            (customer_id, limit),
        )
        return [self._tx2dict(r) for r in rows]

    def card_window(self, customer_id: str, hours: float = 2.0, limit: int = 50) -> list[dict[str, Any]]:
        anchor = self._q1("SELECT MAX(ts) AS tmax FROM transactions WHERE customer_id = ?", (customer_id,))
        if not anchor or not anchor["tmax"]:
            return []
        rows = self._q(
            "SELECT * FROM transactions WHERE customer_id = ? AND ts >= datetime(?, ?) ORDER BY ts ASC LIMIT ?",
            (customer_id, anchor["tmax"], f"-{int(hours * 3600)} seconds", limit),
        )
        return [self._tx2dict(r) for r in rows]

    def connected_entities(self, customer_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        # devices
        for r in self._q(
            "SELECT device_id, device_profile, device_new, device_proxy, COUNT(*) AS n FROM transactions "
            "WHERE customer_id = ? AND device_id != '' GROUP BY device_id ORDER BY n DESC LIMIT ?",
            (customer_id, min(limit, 50)),
        ):
            out[r["device_id"]] = {
                "id": r["device_id"],
                "type": "device",
                "label": r["device_profile"][:60],
                "device_new": r["device_new"],
                "device_proxy": r["device_proxy"],
                "n": r["n"],
            }
        # regions
        for r in self._q(
            "SELECT addr1, COUNT(*) AS n FROM transactions WHERE customer_id = ? AND addr1 != '' "
            "GROUP BY addr1 ORDER BY n DESC LIMIT ?",
            (customer_id, 20),
        ):
            out["REG-" + r["addr1"]] = {
                "id": "REG-" + r["addr1"],
                "type": "region",
                "label": f"region {r['addr1']}",
                "n": r["n"],
            }
        # email domains
        for r in self._q(
            "SELECT P_emaildomain AS d, COUNT(*) AS n FROM transactions WHERE customer_id = ? AND P_emaildomain != '' "
            "GROUP BY P_emaildomain ORDER BY n DESC LIMIT 10",
            (customer_id,),
        ):
            out["DOM-" + r["d"]] = {
                "id": "DOM-" + r["d"],
                "type": "email_domain",
                "label": r["d"],
                "n": r["n"],
            }
        # devices shared with other customers
        for r in self._q(
            "SELECT t.device_id, t.card_id, COUNT(*) AS n FROM transactions t "
            "WHERE t.device_id IN (SELECT DISTINCT device_id FROM transactions WHERE customer_id = ? AND device_id != '') "
            "AND t.customer_id != ? GROUP BY t.device_id, t.card_id ORDER BY n DESC LIMIT ?",
            (customer_id, customer_id, limit),
        ):
            key = f"SH:{r['device_id']}:{r['card_id']}"
            out[key] = {
                "id": key,
                "type": "shared_use",
                "label": f"{r['card_id']} via {r['device_id']}",
                "n": r["n"],
            }
        return sorted(out.values(), key=lambda x: -x["n"])[:limit]

    def shared_devices(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        me = self._q(
            "SELECT DISTINCT device_id FROM transactions WHERE customer_id = ? AND device_id != ''",
            (customer_id,),
        )
        my_devices = [r["device_id"] for r in me]
        if not my_devices:
            return []
        marks = ",".join("?" * len(my_devices))
        rows = self._q(
            f"SELECT DeviceTxn.device_id, DeviceTxn.device_profile, DeviceTxn.customer_id, DeviceTxn.card_id, "
            f"DeviceTxn.device_new, DeviceTxn.device_proxy, COUNT(*) AS n, "
            f"(SELECT MAX(ts) FROM transactions WHERE device_id = DeviceTxn.device_id) AS last_ts "
            f"FROM transactions DeviceTxn WHERE DeviceTxn.device_id IN ({marks}) AND DeviceTxn.customer_id != ? "
            f"GROUP BY DeviceTxn.device_id, DeviceTxn.customer_id ORDER BY n DESC LIMIT ?",
            (*my_devices, customer_id, limit),
        )
        return [
            {
                "device_id": r["device_id"],
                "device_profile": r["device_profile"],
                "other_customer_id": r["customer_id"],
                "other_card_id": r["card_id"],
                "device_new": r["device_new"],
                "device_proxy": r["device_proxy"],
                "shared_txns": r["n"],
                "last_seen": r["last_ts"],
            }
            for r in rows
        ]

    def shared_regions(self, customer_id: str, limit: int = 50) -> list[dict[str, Any]]:
        me = self._q(
            "SELECT DISTINCT addr1 FROM transactions WHERE customer_id = ? AND addr1 != ''", (customer_id,)
        )
        my_regions = [r["addr1"] for r in me]
        if not my_regions:
            return []
        marks = ",".join("?" * len(my_regions))
        rows = self._q(
            f"SELECT addr1, customer_id, card_id, COUNT(*) AS n FROM transactions WHERE addr1 IN ({marks}) "
            f"AND customer_id != ? GROUP BY addr1, customer_id ORDER BY n DESC LIMIT ?",
            (*my_regions, customer_id, limit),
        )
        return [dict(r) for r in rows]

    def related_transactions(
        self, customer_id: str, window_days: float = 7.0, limit: int = 100
    ) -> list[dict[str, Any]]:
        me = self._q(
            "SELECT DISTINCT device_id FROM transactions WHERE customer_id = ? AND device_id != ''",
            (customer_id,),
        )
        my_devices = [r["device_id"] for r in me]
        cond = ""
        params: list[object] = []
        if my_devices:
            cond = f"AND t2.device_id IN ({','.join('?' for _ in my_devices)})"
            params.extend(my_devices)
        params.append(customer_id)
        params.append(limit)
        rows = self._q(
            f"SELECT t2.* FROM transactions t2 WHERE t2.customer_id != ? AND t2.ts >= datetime((SELECT MIN(ts) FROM transactions WHERE customer_id = ?), '-{int(window_days * 24)} hours') {cond} "
            f"ORDER BY t2.ts DESC LIMIT ?",
            (customer_id,) + tuple(params),
        )
        return [self._tx2dict(r) for r in rows]

    def historical_cases(
        self, customer_id: str = "", outcome: str = "", pattern: str = "", limit: int = 20
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[object] = []
        if customer_id:
            clauses.append("customer_id = ?")
            params.append(customer_id)
        if outcome:
            clauses.append("outcome = ?")
            params.append(outcome)
        if pattern:
            clauses.append("pattern = ?")
            params.append(pattern)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self._q(f"SELECT * FROM closed_cases {where} ORDER BY closed_at DESC LIMIT ?", tuple(params))
        return [dict(r) for r in rows]

    def transaction_neighborhood(self, txn_id: str, depth: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        root = self.get_transaction(txn_id)
        frontier = {str(root["txn_id"])}
        visited: set[str] = set()
        result: list[dict[str, Any]] = [root]
        for _ in range(depth):
            nxt: set[str] = set()
            for fx in frontier:
                visited.add(fx)
                for r in self._q(
                    "SELECT customer_id, device_id, addr1 FROM transactions WHERE TransactionID = ?",
                    (int(fx),),
                ):
                    for r2 in self._q(
                        "SELECT TransactionID, ts, TransactionAmt, product_cd, channel, risk_score, customer_id, card_id, device_id, device_profile FROM transactions WHERE customer_id = ? OR (device_id != '' AND device_id = ?)",
                        (r["customer_id"], r["device_id"] or ""),
                    ):
                        rid = str(r2["TransactionID"])
                        if rid not in visited and len(result) < limit:
                            result.append(self._tx2dict(r2))
                            nxt.add(rid)
            frontier = nxt
            if not frontier:
                break
        return result

    def high_degree_check(self, entity_id: str) -> bool:
        if entity_id.startswith("DEV-"):
            n = self._q1("SELECT COUNT(*) AS n FROM transactions WHERE device_id = ?", (entity_id,))["n"]
        else:
            n = self._q1("SELECT COUNT(*) AS n FROM transactions WHERE customer_id = ?", (entity_id,))["n"]
        return n > self.high_degree_threshold

    def write_case(self, case: dict[str, Any]) -> str:
        import uuid

        gid = case.get("graph_case_id") or f"CASE-2016-{uuid.uuid4().hex[:8].upper()}"
        self._conn.execute(
            "INSERT OR REPLACE INTO graph_cases(graph_case_id, case_id, customer_id, verdict, pattern, "
            "exposure_usd, affected_txn_ids, connected_card_ids, device_profiles, summary, created_at, payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'),?)",
            (
                gid,
                case.get("case_id", ""),
                case.get("customer_id", ""),
                case.get("verdict", ""),
                case.get("pattern", ""),
                case.get("exposure_usd", 0.0),
                json.dumps(case.get("affected_txn_ids", [])),
                json.dumps(case.get("connected_card_ids", [])),
                json.dumps(case.get("connected_device_profiles", [])),
                case.get("summary", ""),
                json.dumps(case, default=str),
            ),
        )
        self._conn.commit()
        return gid

    def subgraph_for_viz(self, root: str, depth: int = 2, limit: int = 100) -> dict[str, Any]:
        nodes: dict[str, Any] = {}
        edges: list[dict[str, Any]] = []
        try:
            txn = self.get_transaction(root)
        except KeyError:
            txn = None
        if txn:
            nodes[root] = {
                "id": root,
                "type": "transaction",
                "label": f"${txn['amount']:.2f}",
                "risk": txn.get("risk_score", 0),
            }
            for r in [txn]:
                nodes.setdefault(
                    r["customer_id"], {"id": r["customer_id"], "type": "customer", "label": r["customer_id"]}
                )
                edges.append({"from": root, "to": r["customer_id"], "type": "MADE_BY"})
                if r.get("device_id") and r["device_id"].startswith("DEV-"):
                    nodes.setdefault(
                        r["device_id"], {"id": r["device_id"], "type": "device", "label": "device"}
                    )
                    edges.append({"from": root, "to": r["device_id"], "type": "FROM_DEVICE"})
            if "customer_id" in txn:
                for r in self._q(
                    "SELECT TransactionID, TransactionAmt, ts FROM transactions WHERE customer_id = ? ORDER BY ts DESC LIMIT ?",
                    (txn["customer_id"], min(20, limit)),
                ):
                    nid = str(r["TransactionID"])
                    nodes.setdefault(
                        nid,
                        {"id": nid, "type": "transaction", "label": f"${r['TransactionAmt']:.2f}", "risk": 0},
                    )
                    edges.append({"from": nid, "to": txn["customer_id"], "type": "MADE_BY"})
        return {"nodes": list(nodes.values()), "edges": edges}
