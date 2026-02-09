#!/usr/bin/env python3
"""Test script for hybrid search utilities."""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.hybrid_search import (
    SearchFilters,
    fuse_rankings,
    normalize_query,
    validate_search_request
)


def test_normalize_query():
    print("[TEST] normalize_query")
    result = normalize_query("AI ethics and tech")
    print(f"normalized_query: {result['normalized_query']}")
    print(f"expanded_terms: {result['expanded_terms']}")
    print(f"topic_ids: {result['topic_ids']}")
    assert "artificial intelligence" in result["expanded_terms"], "synonym expansion missing"
    assert "domain-technology" in result["topic_ids"], "alias mapping missing"


def test_validate_search_request():
    print("[TEST] validate_search_request")
    payload = {
        "query": "philosophy of mind",
        "limit": 5,
        "filters": {
            "trust_tier": ["secondary"]
        },
        "options": {
            "use_embeddings": True,
            "use_keywords": False
        }
    }
    req = validate_search_request(payload)
    assert req.query == "philosophy of mind"
    assert req.limit == 5
    assert req.filters.trust_tier == ("secondary",)
    assert req.options.use_keywords is False


def test_fuse_rankings():
    print("[TEST] fuse_rankings")
    keyword = [
        {"source_path": "a", "score": 4.0},
        {"source_path": "b", "score": 2.0}
    ]
    embedding = [
        {"source_path": "a", "score": 0.6},
        {"source_path": "c", "score": 0.9}
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        weights_path = Path(temp_dir) / "weights.json"
        weights_path.write_text(
            json.dumps({"weights": {"keyword": 0.4, "embedding": 0.6}}),
            encoding="utf-8"
        )
        results = fuse_rankings(keyword, embedding, weights_path=weights_path, limit=3)

    assert results, "fusion returned no results"
    assert results[0]["score"] >= results[-1]["score"], "results not sorted"


def run_tests():
    print("=" * 60)
    print("TESTING HYBRID SEARCH")
    print("=" * 60)

    test_normalize_query()
    test_validate_search_request()
    test_fuse_rankings()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
