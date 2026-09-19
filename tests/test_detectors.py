"""Unit tests for pattern detectors."""

from ravel.application.detectors import (
    AccountTakeoverDetector,
    CardNotPresentNewDeviceDetector,
    CardTestingDetector,
    OutOfRegionDetector,
)
from ravel.domain.enums import FraudPattern, PatternStatus
from ravel.domain.pattern import InvestigationContext


def test_card_testing_detector_positive():
    detector = CardTestingDetector()
    ctx = InvestigationContext(
        card_window=[
            {"txn_id": "1", "amount": 1.20, "channel": "online", "ts": "2016-11-10 10:00:00"},
            {"txn_id": "2", "amount": 2.50, "channel": "online", "ts": "2016-11-10 10:05:00"},
            {"txn_id": "3", "amount": 0.99, "channel": "online", "ts": "2016-11-10 10:10:00"},
            {"txn_id": "4", "amount": 250.00, "channel": "online", "ts": "2016-11-10 10:30:00"},
        ]
    )
    res = detector.detect(ctx)
    assert res.pattern == FraudPattern.CARD_TESTING
    assert res.status == PatternStatus.DETECTED
    assert res.confidence >= 0.55
    assert len(res.affected_txn_ids) == 4


def test_card_testing_detector_negative():
    detector = CardTestingDetector()
    ctx = InvestigationContext(
        card_window=[
            {"txn_id": "1", "amount": 50.00, "channel": "online", "ts": "2016-11-10 10:00:00"},
        ]
    )
    res = detector.detect(ctx)
    assert res.status == PatternStatus.NOT_DETECTED


def test_card_not_present_new_device_detector():
    detector = CardNotPresentNewDeviceDetector()
    ctx = InvestigationContext(
        txn={
            "txn_id": "10",
            "channel": "online",
            "amount": 350.0,
            "product_cd": "C",
            "device_new": "New",
            "device_proxy": "transparent",
        },
        card_history=[{"txn_id": "1", "amount": 20.0, "product_cd": "W", "channel": "in_person"}],
        card_window=[
            {"txn_id": "10", "amount": 350.0, "channel": "online"},
            {"txn_id": "11", "amount": 200.0, "channel": "online"},
        ],
    )
    res = detector.detect(ctx)
    assert res.pattern == FraudPattern.CARD_NOT_PRESENT_NEW_DEVICE
    assert res.status == PatternStatus.DETECTED
    assert res.confidence > 0.6


def test_out_of_region_detector():
    detector = OutOfRegionDetector()
    ctx = InvestigationContext(
        txn={"txn_id": "20", "channel": "in_person", "addr1": "999"},
        customer={"home_region": "100"},
        card_history=[{"txn_id": "5", "addr1": "100", "channel": "in_person"}],
        card_window=[{"txn_id": "20", "addr1": "999"}],
        related_transactions=[{"txn_id": "21", "addr1": "999"}, {"txn_id": "22", "addr1": "999"}],
    )
    res = detector.detect(ctx)
    assert res.pattern == FraudPattern.OUT_OF_REGION_USE
    assert res.status == PatternStatus.DETECTED


def test_account_takeover_detector():
    detector = AccountTakeoverDetector()
    ctx = InvestigationContext(
        txn={"txn_id": "30", "channel": "online", "device_new": "New", "device_proxy": "proxy"},
        card_history=[{"txn_id": "1", "channel": "in_person"}],
        card_window=[{"txn_id": "30"}],
    )
    res = detector.detect(ctx)
    assert res.pattern == FraudPattern.ACCOUNT_TAKEOVER
    assert res.status == PatternStatus.DETECTED
