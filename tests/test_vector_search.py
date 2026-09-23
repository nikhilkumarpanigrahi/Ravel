from ravel.application.vector_search import CaseVectorIndex, LightweightTextEmbedder


def test_lightweight_embedder():
    embedder = LightweightTextEmbedder(dim=128)
    vec1 = embedder.embed("Card testing velocity attack across multiple merchants")
    vec2 = embedder.embed("Card testing with rapid transactions")
    vec3 = embedder.embed("Account takeover password reset")

    assert vec1.shape == (128,)
    assert vec2.shape == (128,)
    assert vec3.shape == (128,)

    # Cosine similarity between card testing texts should be higher than with account takeover
    import numpy as np

    sim_testing = np.dot(vec1, vec2)
    sim_ato = np.dot(vec1, vec3)
    assert sim_testing > sim_ato


def test_case_vector_index(tmp_path):
    csv_file = tmp_path / "closed_cases_history.csv"
    csv_file.write_text(
        "case_id,customer_id,card_id,outcome,pattern,exposure_usd,actions_taken,report_filed,summary\n"
        "CC-101,C101,K1,confirmed_fraud,card_testing,120.50,BLOCK_CARD,true,Rapid card testing attack on checkout\n"
        "CC-102,C102,K2,confirmed_fraud,account_takeover,4500.00,STEP_UP_AUTH,true,Account takeover after credential stuffing\n"
        "CC-103,C103,K3,cleared,none,0.00,ALLOW_TRANSACTION,false,Legitimate holiday shopping confirmed by cardholder\n",
        encoding="utf-8",
    )

    index = CaseVectorIndex()
    indexed_count = index.index_cases_from_csv(csv_file)
    assert indexed_count == 3

    results = index.search_similar_cases("card testing attack", top_k=2)
    assert len(results) > 0
    assert results[0]["case_id"] == "CC-101"
    assert "similarity_score" in results[0]
