from pathlib import Path

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


def test_lightweight_embedder_is_stable_across_instances():
    first = LightweightTextEmbedder(dim=128).embed("shared proxy device fraud ring")
    second = LightweightTextEmbedder(dim=128).embed("shared proxy device fraud ring")

    import numpy as np

    np.testing.assert_array_equal(first, second)


def test_case_vector_index():
    csv_file = Path(__file__).parent / "fixtures" / "closed_cases_sample.csv"
    index = CaseVectorIndex()
    indexed_count = index.index_cases_from_csv(csv_file)
    assert indexed_count == 3

    results = index.search_similar_cases("card testing attack", top_k=2)
    assert len(results) > 0
    assert results[0]["case_id"] == "CC-101"
    assert "similarity_score" in results[0]
