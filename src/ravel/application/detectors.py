"""The five documented fraud-pattern detectors plus modular base.

Definitions drawn from the HHGOA_IEEE README "known fraud patterns" section. Every detector
returns a :class:`PatternResult` with evidence, satisfied/missing conditions and contradictions.
No detector is benchmark-case specific (Open/Closed: new detectors plug in by subclassing).
"""

from __future__ import annotations

from ravel.domain.enums import FraudPattern, PatternStatus
from ravel.domain.pattern import InvestigationContext, PatternDetector, PatternResult

SMALL_AUTH_LIMIT = 5.0
SMALL_WINDOW_HOURS = 1.0
LARGE_PURCHASE_LIMIT = 100.0
BURST_WINDOW_HOURS = 48.0
BURST_MIN_TXNS = 2


class CardTestingDetector(PatternDetector):
    pattern = FraudPattern.CARD_TESTING

    def detect(self, ctx: InvestigationContext) -> PatternResult:
        result = PatternResult(pattern=self.pattern)
        window = ctx.card_window
        if not window:
            result.missing_conditions.append("no card_window evidence")
            return result
        online = [t for t in window if (t.get("channel") or "").lower() != "in_person"]
        small = [t for t in online if float(t.get("amount") or 0) <= SMALL_AUTH_LIMIT]
        # cluster the window by time (the window is time-bounded already)
        result.evidence.append(
            f"{len(small)} online authorizations at or under ${SMALL_AUTH_LIMIT:.2f} found in window"
        )
        if len(small) < 3:
            result.missing_conditions.append(f"fewer than 3 small online authorizations (found {len(small)})")
        big = [t for t in online if float(t.get("amount") or 0) > SMALL_AUTH_LIMIT]
        large = [t for t in big if float(t.get("amount") or 0) >= LARGE_PURCHASE_LIMIT]
        a_big_purchase_after = any(
            big_t.get("ts") and all(small_t.get("ts") and big_t["ts"] >= small_t["ts"] for small_t in small)
            for big_t in big
        )
        if not a_big_purchase_after:
            result.missing_conditions.append("no larger purchase after the small authorizations")
        if len(small) >= 3 and large:
            result.satisfied_conditions = [
                f"{len(small)} small online authorizations",
                f"larger purchase present (${large[0].get('amount', 0):.2f})",
            ]
            result.status = PatternStatus.DETECTED
            result.candidate = True
            result.confidence = min(
                0.95,
                0.55
                + 0.10 * (len(small) - 3)
                + (0.10 if large[0].get("amount", 0) > SMALL_AUTH_LIMIT else 0),
            )
            result.affected_txn_ids = [str(t.get("txn_id")) for t in window if t.get("txn_id")]
            if window:
                result.first_suspicious_txn_id = str(window[0].get("txn_id", ""))
            result.contradictions = [
                c for c in result.contradictions if not c
            ]  # preserve editor's empty list
        elif len(small) >= 3 or (len(small) >= 2 and large):
            result.status = PatternStatus.PARTIAL
            result.confidence = 0.35
        return result


class CardNotPresentDetector(PatternDetector):
    pattern = FraudPattern.CARD_NOT_PRESENT_FRAUD

    def detect(self, ctx: InvestigationContext) -> PatternResult:
        result = PatternResult(pattern=self.pattern)
        flagged = ctx.txn
        if not flagged:
            result.missing_conditions.append("no flagged transaction")
            return result
        channel = (flagged.get("channel") or "").lower()
        if channel == "in_person":
            result.contradictions.append("flagged transaction is card-present")
            return result
        history = ctx.card_history or []
        window = ctx.card_window or []
        online_burst = [t for t in window if (t.get("channel") or "").lower() != "in_person"]
        amount = float(flagged.get("amount") or 0)
        hist_amounts = [float(t.get("amount") or 0) for t in history]
        p95 = sorted(hist_amounts)[int(len(hist_amounts) * 0.95)] if hist_amounts else amount
        amount_anomaly = amount > p95 and p95 > 0
        products = {t.get("product_cd") for t in history}
        product_anomaly = bool(flagged.get("product_cd")) and flagged["product_cd"] not in products
        signal_count = sum(
            [
                amount_anomaly,
                product_anomaly,
                bool(flagged.get("email_conflict")),
                len(online_burst) >= BURST_MIN_TXNS,
            ]
        )
        result.evidence.append(
            f"amount {amount:.2f} vs historical p95 {p95:.2f} -> {'anomalous' if amount_anomaly else 'in line'}"
        )
        result.evidence.append(f"product_cd {flagged.get('product_cd')} seen before -> {not product_anomaly}")
        if len(online_burst) >= BURST_MIN_TXNS:
            result.satisfied_conditions.append(
                f"burst of {len(online_burst)} online transactions within the window"
            )
            result.evidence.append(f"{len(online_burst)} online transactions in a burst window")
        else:
            result.missing_conditions.append("no online burst (2+ online txns in window)")
        if amount_anomaly:
            result.satisfied_conditions.append("amount inconsistent with the cardholder's history")
        else:
            result.missing_conditions.append("amount in line with history")
        if product_anomaly:
            result.satisfied_conditions.append("product/category not used before")
        else:
            result.missing_conditions.append("product/category seen before")
        n = sum(1 for c in result.satisfied_conditions if c)
        if n >= 2:
            result.status = PatternStatus.DETECTED
            result.candidate = True
            result.confidence = min(0.85, 0.45 + 0.15 * n + (0.05 if flagged.get("email_conflict") else 0))
            result.affected_txn_ids = [str(t.get("txn_id")) for t in online_burst if t.get("txn_id")]
            result.first_suspicious_txn_id = (
                str(online_burst[0].get("txn_id", "")) if online_burst else str(flagged.get("txn_id", ""))
            )
        elif n == 1 and signal_count >= 1:
            result.status = PatternStatus.PARTIAL
            result.confidence = 0.3
            result.missing_conditions.append("single unusual purchase only -> verify before acting (R1)")
        return result


class CardNotPresentNewDeviceDetector(CardNotPresentDetector):
    pattern = FraudPattern.CARD_NOT_PRESENT_NEW_DEVICE

    def detect(self, ctx: InvestigationContext) -> PatternResult:
        result = super().detect(ctx)
        result.pattern = self.pattern
        flagged = ctx.txn or {}
        device_new = (flagged.get("device_new") or "").lower() == "new"
        proxy = bool(flagged.get("device_proxy"))
        if not device_new and not proxy:
            result.missing_conditions.append("device not marked New and no proxy signal")
        if device_new:
            result.satisfied_conditions.append("device marked New for this account (id_15)")
            result.evidence.append("identity record marks device as New for this account")
        if proxy:
            result.satisfied_conditions.append("proxy/anonymous connection flagged (id_23)")
        if result.status == PatternStatus.DETECTED and (device_new or proxy):
            result.candidate = True
            result.confidence = min(0.95, result.confidence + 0.15)
        return result


class OutOfRegionDetector(PatternDetector):
    pattern = FraudPattern.OUT_OF_REGION_USE

    def detect(self, ctx: InvestigationContext) -> PatternResult:
        result = PatternResult(pattern=self.pattern)
        flagged = ctx.txn or {}
        channel = (flagged.get("channel") or "").lower()
        if channel != "in_person":
            result.contradictions.append("flagged transaction is an online transaction, not card-present")
            return result
        history = ctx.card_history or []
        hist_regions = {t.get("addr1") for t in history if t.get("addr1")}
        region = flagged.get("addr1") or ""
        home_region = ctx.customer.get("home_region") or (history[0].get("addr1") if history else "")
        out_of_region = bool(region) and region not in hist_regions
        if not out_of_region:
            result.missing_conditions.append("flagged region seen before in this card's history")
            return result
        result.satisfied_conditions.append(f"card-present use in region {region} with no history")
        result.evidence.append(
            f"card-present transaction in billing region {region}; history regions: {sorted(hist_regions)[:5]}"
        )
        # concurrent normal activity at home?
        recent = [t for t in history if t.get("addr1") == home_region]
        if recent:
            result.satisfied_conditions.append("normal home-region activity continues in the same period")
        # number of txns in the new region across the card (trip vs clone)
        region_txns = [t for t in ctx.related_transactions + ctx.card_window if t.get("addr1") == region]
        n_region = len(region_txns) + 1
        if n_region <= 2:
            result.missing_conditions.append("only one or two purchases in the new region (possible trip)")
        result.evidence.append(f"{n_region} transaction(s) in new region {region}")
        if home_region and recent:
            result.status = PatternStatus.DETECTED
            result.candidate = True
            result.confidence = min(0.9, 0.5 + 0.1 * min(n_region - 1, 3) + (0.1 if out_of_region else 0))
            result.affected_txn_ids = [str(t.get("txn_id")) for t in region_txns if t.get("txn_id")]
            result.first_suspicious_txn_id = str(flagged.get("txn_id", ""))
        else:
            result.status = PatternStatus.PARTIAL
            result.confidence = 0.35
        return result


class AccountTakeoverDetector(PatternDetector):
    pattern = FraudPattern.ACCOUNT_TAKEOVER

    def detect(self, ctx: InvestigationContext) -> PatternResult:
        result = PatternResult(pattern=self.pattern)
        flagged = ctx.txn or {}
        history = ctx.card_history or []
        channels = {(t.get("channel") or "").lower() for t in history}
        flagged_channel = (flagged.get("channel") or "").lower()
        mixed = bool(channels) and flagged_channel not in channels
        device_new = (flagged.get("device_new") or "").lower() == "new"
        proxy = bool(flagged.get("device_proxy"))
        email_conflict = bool(flagged.get("email_conflict"))
        result.evidence.append(f"flagged channel {flagged_channel}; historical channels {sorted(channels)}")
        if mixed:
            result.satisfied_conditions.append("mixed-channel activity inconsistent with the cardholder")
        if device_new:
            result.satisfied_conditions.append("new device for this account")
        if proxy:
            result.satisfied_conditions.append("proxy connection")
        if email_conflict:
            result.satisfied_conditions.append("purchaser/recipient email conflict")
        n = len(result.satisfied_conditions)
        if n >= 2:
            result.status = PatternStatus.DETECTED
            result.candidate = True
            result.confidence = min(0.9, 0.45 + 0.15 * n)
            result.affected_txn_ids = [str(t.get("txn_id")) for t in ctx.card_window if t.get("txn_id")]
            result.first_suspicious_txn_id = str(flagged.get("txn_id", ""))
        elif n == 1:
            result.status = PatternStatus.PARTIAL
            result.confidence = 0.3
        if channels and not mixed and not device_new and not proxy:
            result.contradictions.append("activity matches the cardholder's established channel/device usage")
        return result


DETECTORS: list[PatternDetector] = [
    CardTestingDetector(),
    CardNotPresentDetector(),
    CardNotPresentNewDeviceDetector(),
    OutOfRegionDetector(),
    AccountTakeoverDetector(),
]


def run_detectors(ctx: InvestigationContext) -> list[PatternResult]:
    return [d.detect(ctx) for d in DETECTORS]
