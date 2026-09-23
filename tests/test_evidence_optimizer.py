from ravel.application.evidence_value_optimizer import EvidenceValueOptimizer


def test_evidence_value_optimizer():
    optimizer = EvidenceValueOptimizer()

    # Case: Medium-high fraud probability ($1,200 exposure)
    options = optimizer.rank_evidence_inquiries(
        current_fraud_prob=0.75,
        exposure_usd=1200.0,
        customer_id="C12382",
        txn_id="3514030",
    )

    assert len(options) >= 3
    # First option should be cardholder SMS or high-EIG inquiry
    top_option = options[0]
    assert top_option.expected_info_gain_bits > 0.0
    assert top_option.value_of_information > 0.0
    assert top_option.recommended_order == 1
    assert "Rank #1" in top_option.rationale


def test_entropy_calculation():
    # Maximum uncertainty at p = 0.5 (1 bit of entropy)
    h_mid = EvidenceValueOptimizer.binary_entropy(0.5)
    assert round(h_mid, 2) == 1.0

    # Low uncertainty near 0 or 1
    h_low = EvidenceValueOptimizer.binary_entropy(0.05)
    assert h_low < 0.3
