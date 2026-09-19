"""Reproducible data pipeline: HHGOA_IEEE CSV -> normalized graph-ready datasets.

Design goals (AEP Phase 2 / Product PRD section 23):
- chunked, bounded-memory processing (never load the full file at once)
- resumable via checkpoints on-the-fly derived CSVs
- deterministic, idempotent IDs
- validation before insertion
- provenance for derived evidence
- ingestion metrics (JSON report)
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

TX_COLS = [
    "TransactionID",
    "TransactionDT",
    "TransactionAmt",
    "ProductCD",
    "card1",
    "card4",
    "card6",
    "addr1",
    "addr2",
    "P_emaildomain",
    "R_emaildomain",
    "customer_id",
    "ts",
    "channel",
    "risk_score",
]

NUMERIC_COLS = {"card1", "addr1", "addr2"}


@dataclass
class IngestionMetrics:
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    txn_rows_seen: int = 0
    txn_rows_loaded: int = 0
    txn_rows_dropped: int = 0
    identity_rows_seen: int = 0
    customers: int = 0
    devices: int = 0
    email_domains: int = 0
    regions: int = 0
    closed_cases: int = 0
    closed_txn_links: int = 0
    next_edges: int = 0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {k: v for k, v in vars(self).items()}
        d["elapsed_s"] = round(self.finished_at - self.started_at, 2) if self.finished_at else 0
        return d


def _safe_float(v: object) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_int(v: object) -> int:
    try:
        f = float(v)
        return int(f) if math.isfinite(f) else 0
    except (TypeError, ValueError):
        return 0


def _clean_str(v: object) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


def _normalize_device_info(v: str) -> str:
    return " ".join(v.split())


class DataPipeline:
    """Chunked pipeline producing graph-ready CSVs under `data/level0/`."""

    def __init__(self, data_dir: Path, out_dir: Path, chunksize: int = 200_000):
        self.data_dir = data_dir
        self.out_dir = out_dir
        self.chunksize = chunksize
        self.metrics = IngestionMetrics()
        self.txn_path = data_dir / "transactions.csv"
        self.identity_path = data_dir / "identity.csv"
        self.closed_cases_path = data_dir / "closed_cases_history.csv"
        self.case_pack_path = data_dir / "case_pack.csv"

    # ------------------------------------------------------------------ helpers
    def _w(self, name: str, header: list[str]) -> object:
        f = open(self.out_dir / f"{name}.csv", "w", newline="", encoding="utf-8")  # noqa: SIM115
        w = csv.writer(f)
        w.writerow(header)
        return f, w

    def _log(self, *args: object) -> None:
        print("[ingest]", *args)

    # ------------------------------------------------------------------- steps
    def run(self) -> IngestionMetrics:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._log("validating input files")
        self._validate_inputs()
        self._log("building id maps (customers/cards, identities)")
        id_map, device_map, device_id_map = self._load_id_maps()
        self._log("streaming transactions")
        self._stream_transactions(id_map, device_id_map)
        self._log("loading closed cases")
        self._load_closed_cases()
        self.metrics.finished_at = time.time()
        report = self.out_dir / "ingest_report.json"
        report.write_text(json.dumps(self.metrics.to_dict(), indent=2))
        self._log("metrics", self.metrics.to_dict())
        return self.metrics

    def _validate_inputs(self) -> None:
        for name in ("transactions.csv", "identity.csv", "closed_cases_history.csv", "case_pack.csv"):
            p = self.data_dir / name
            if not p.exists():
                raise FileNotFoundError(f"missing dataset file: {p}")
            if p.stat().st_size == 0:
                raise ValueError(f"empty dataset file: {p}")

    def _load_id_maps(self) -> tuple[dict, dict, dict]:
        """card_label -> {customer_id, card_label}; device profile -> id; txn -> device tuple."""
        card_labels_by_customer: dict[str, set[str]] = {}
        device_map: dict[str, str] = {}  # profile string -> device id
        device_id_map: dict[str, tuple] = {}  # txn id -> device tuple
        identity = pd.read_csv(self.identity_path, dtype=str, keep_default_na=False)
        self.metrics.identity_rows_seen = len(identity)
        seen: set[str] = set()
        for _, row in identity.iterrows():
            txn_id = row.get("TransactionID", "").strip()
            if not txn_id or txn_id in seen:
                continue
            seen.add(txn_id)
            dev_info = _normalize_device_info(_clean_str(row.get("DeviceInfo")))
            os_ = _clean_str(row.get("id_30"))
            browser = _clean_str(row.get("id_31"))
            screen = _clean_str(row.get("id_33"))
            dev_type = _clean_str(row.get("DeviceType"))
            dev_proxy = _clean_str(row.get("id_23"))
            dev_new = _clean_str(row.get("id_15"))
            match_status = _clean_str(row.get("id_34"))
            profile = f"{dev_info} | {os_} | {browser} | {screen}"
            if profile not in device_map:
                device_map[profile] = self._device_id(profile)
            device_id = device_map[profile]
            device_id_map[txn_id] = (device_id, profile, dev_type, dev_proxy, dev_new, match_status)

        # Customer -> card label mapping from closed cases + case pack
        for path, cols in (
            (self.closed_cases_path, ("customer_id", "card_id")),
            (self.case_pack_path, ("customer_id", "card_id")),
        ):
            dfp = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=list(cols))
            for _, row in dfp.iterrows():
                c = row["customer_id"].strip()
                k = row["card_id"].strip()
                if c and k:
                    card_labels_by_customer.setdefault(c, set()).add(k)

        id_map: dict[str, dict] = {}
        for cust, labels in card_labels_by_customer.items():
            for lbl in sorted(labels):
                id_map[lbl] = {"customer_id": cust, "card_label": lbl}
        return id_map, device_map, device_id_map

    @staticmethod
    def _device_id(profile: str) -> str:
        return "DEV-" + hashlib.md5(profile.encode("utf-8")).hexdigest()[:10]

    def _stream_transactions(self, id_map: dict, device_id_map: dict) -> None:
        f, w = self._w(
            "transactions",
            [
                "TransactionID",
                "TransactionDT",
                "ts",
                "TransactionAmt",
                "ProductCD",
                "channel",
                "risk_score",
                "customer_id",
                "card_id",
                "card1",
                "card6",
                "addr1",
                "addr2",
                "P_emaildomain",
                "R_emaildomain",
                "device_id",
                "device_profile",
                "device_type",
                "device_new",
                "device_proxy",
                "email_conflict",
            ],
        )
        customers: dict[str, str] = {}
        emails: set[str] = set()
        regions: set[str] = set()
        devices: dict[str, list[str]] = {}
        seen_ids: set[str] = set()

        for chunk_no, chunk in enumerate(
            pd.read_csv(
                self.txn_path,
                chunksize=self.chunksize,
                usecols=TX_COLS,
                dtype=str,
                keep_default_na=False,
                on_bad_lines="warn",
            )
        ):
            for _, row in chunk.iterrows():
                self.metrics.txn_rows_seen += 1
                tid = row["TransactionID"].strip()
                if not tid or tid in seen_ids:
                    self.metrics.txn_rows_dropped += 1
                    continue
                seen_ids.add(tid)
                cust = _clean_str(row.get("customer_id"))
                if not cust:
                    self.metrics.txn_rows_dropped += 1
                    self.metrics.issues.append(f"row {tid}: missing customer_id")
                    continue
                card1 = _clean_str(row.get("card1"))
                card_label = f"{cust}-K1"
                # a case/closed-case label exists for this customer
                for lbl in (cand for cand in (cust + "-K1", cust + "-K2") if cand in id_map):
                    card_label = lbl
                    break
                customers[cust] = card_label
                pemail = _clean_str(row.get("P_emaildomain")).lower()
                remail = _clean_str(row.get("R_emaildomain")).lower()
                if pemail:
                    emails.add(pemail)
                addr1 = _clean_str(row.get("addr1"))
                if addr1 and addr1 != "0" and not addr1.lower().startswith("nan"):
                    regions.add(addr1)
                dev = device_id_map.get(tid, ("", "", "", "", "", ""))
                device_id, profile, dev_type, dev_proxy, dev_new, _match = dev
                if device_id and device_id not in devices:
                    devices[device_id] = [device_id, profile, dev_type]
                # email conflict: purchaser vs recipient domain differ, cardholders usually use their own
                email_conflict = "1" if (pemail and remail and pemail != remail) else "0"
                w.writerow(
                    [
                        tid,
                        row["TransactionDT"].strip(),
                        row["ts"].strip(),
                        _safe_float(row["TransactionAmt"]),
                        row["ProductCD"].strip(),
                        row["channel"].strip(),
                        _safe_float(row["risk_score"]),
                        cust,
                        card_label,
                        card1,
                        _clean_str(row.get("card6")),
                        _clean_str(row.get("addr1")),
                        _clean_str(row.get("addr2")),
                        pemail,
                        remail,
                        device_id,
                        profile,
                        dev_type,
                        dev_new,
                        dev_proxy,
                        email_conflict,
                    ]
                )
            self._log(
                f"  chunk {chunk_no + 1}: seen={self.metrics.txn_rows_seen} loaded_so_far={self.metrics.txn_rows_seen - self.metrics.txn_rows_dropped}"
            )
        f.close()

        self.metrics.txn_rows_loaded = self.metrics.txn_rows_seen - self.metrics.txn_rows_dropped
        self.metrics.customers = len(customers)
        self.metrics.devices = len(devices)
        self.metrics.email_domains = len(emails)
        self.metrics.regions = len(regions)

        def write_set(name: str, header: list[str], rows: Iterable[list]):
            with open(self.out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as ff:
                ww = csv.writer(ff)
                ww.writerow(header)
                ww.writerows(rows)

        write_set("email_domains", ["email_domain"], [[e] for e in sorted(emails)])
        write_set("billing_regions", ["region_id"], [[r] for r in sorted(regions)])
        write_set("devices", ["device_id", "dev_profile", "device_type"], list(devices.values()))
        self._make_customer_file()

        # NEXT edges (per card ordered by ts)
        next_f, next_w = self._w("next_edges", ["from_txn", "to_txn", "card_id", "secs"])
        prev: dict[str, tuple[str, str]] = {}
        n = 0
        for chunk in pd.read_csv(
            self.out_dir / "transactions.csv",
            chunksize=800_000,
            dtype=str,
            keep_default_na=False,
            usecols=["TransactionID", "ts", "customer_id"],
        ):
            chunk = chunk.sort_values("ts")
            for _, row in chunk.iterrows():
                key = row["customer_id"]
                if key in prev:
                    prev_tid, prev_ts = prev[key]
                    secs = (pd.Timestamp(row["ts"]) - pd.Timestamp(prev_ts)).total_seconds()
                    next_w.writerow([prev_tid, row["TransactionID"], key, secs])
                    n += 1
                prev[key] = (row["TransactionID"], row["ts"])
        next_f.close()
        self.metrics.next_edges = n

    def _make_customer_file(self) -> None:
        f, w = self._w("customers", ["customer_id", "card_label", "card1", "card6", "home_region"])
        home: dict[str, str] = {}
        seen: set[str] = set()
        for chunk in pd.read_csv(
            self.out_dir / "transactions.csv",
            chunksize=800_000,
            dtype=str,
            keep_default_na=False,
            usecols=["customer_id", "card_id", "card1", "card6", "addr1"],
        ):
            for _, row in chunk.iterrows():
                c = row["customer_id"]
                if c not in seen:
                    seen.add(c)
                    home[c] = row["addr1"] if row["addr1"] else ""
                    w.writerow([c, row["card_id"], row["card1"], row["card6"], home[c]])
                elif not home[c] and row["addr1"]:
                    home[c] = row["addr1"]
        f.close()

    def _load_closed_cases(self) -> None:
        df = pd.read_csv(self.closed_cases_path, dtype=str, keep_default_na=False)
        f, w = self._w(
            "closed_cases",
            [
                "case_id",
                "customer_id",
                "card_id",
                "opened_at",
                "closed_at",
                "outcome",
                "pattern",
                "first_fraud_txn_id",
                "txn_ids",
                "n_txns",
                "exposure_usd",
                "connected_card_ids",
                "actions_taken",
                "report_filed",
                "summary",
            ],
        )
        txn_members: list[tuple[str, str]] = []
        for _, row in df.iterrows():
            case_id = row["case_id"].strip()
            txn_ids = "|".join(x.strip() for x in str(row["txn_ids"]).split("|") if x.strip())
            for t in txn_ids.split("|"):
                if t:
                    txn_members.append((case_id, t))
            w.writerow(
                [
                    case_id,
                    row["customer_id"].strip(),
                    row["card_id"].strip(),
                    row["opened_at"].strip(),
                    row["closed_at"].strip(),
                    row["outcome"].strip(),
                    row["pattern"].strip(),
                    row["first_fraud_txn_id"].strip(),
                    txn_ids,
                    _safe_int(row["n_txns"]),
                    _safe_float(row["exposure_usd"]),
                    row["connected_card_ids"].strip(),
                    row["actions_taken"].strip(),
                    row["report_filed"].strip(),
                    row["analyst_notes"].strip(),
                ]
            )
        f.close()
        self.metrics.closed_cases = len(df)
        self.metrics.closed_txn_links = len(txn_members)

    def checkpoint(self) -> Path:
        p = self.out_dir / "CHECKPOINT"
        p.write_text(json.dumps({"status": "complete", "metrics": self.metrics.to_dict()}, indent=2))
        return p


def run_pipeline(data_dir: Path, out_dir: Path, chunksize: int = 200_000) -> IngestionMetrics:
    return DataPipeline(data_dir, out_dir, chunksize).run()
