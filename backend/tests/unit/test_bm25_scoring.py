"""Tests for BM25 scoring and index."""

import json
import math
import tempfile
import time
from pathlib import Path

import pytest

from retrieval.bm25 import BM25Index, BM25Params, SearchHit, QUERY_TERM_CAP
from retrieval.bm25_chunks import Chunk, StaleIndexError


def test_hand_computed_score():
    """Test BM25 score with hand-computed expected values."""
    # Create a simple 3-chunk corpus
    chunks = [
        Chunk(
            id="doc1",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'apple': 2, 'banana': 1}
        ),
        Chunk(
            id="doc2",
            kind="function",
            file="test.py",
            line_start=11,
            line_end=20,
            is_test=False,
            token_count=10,
            term_frequencies={'apple': 1, 'cherry': 2}
        ),
        Chunk(
            id="doc3",
            kind="function",
            file="test.py",
            line_start=21,
            line_end=30,
            is_test=False,
            token_count=10,
            term_frequencies={'banana': 1, 'cherry': 1}
        )
    ]
    
    params = BM25Params(k1=1.5, b=0.75)
    index = BM25Index.build(chunks, params, "test_hash", {})
    
    # Verify index construction
    assert index.N == 3
    assert index.avgdl == 10.0
    
    # Query: "apple"
    # df(apple) = 2 (doc1, doc2)
    # IDF(apple) = ln((3 - 2 + 0.5) / (2 + 0.5) + 1)
    N = 3
    df_apple = 2
    idf_apple = math.log((N - df_apple + 0.5) / (df_apple + 0.5) + 1)
    
    # Score for doc1:
    # tf = 2, len = 10, avgdl = 10
    # numerator = 2 * (1.5 + 1) = 5.0
    # denominator = 2 + 1.5 * (1 - 0.75 + 0.75 * 10/10) = 2 + 1.5 = 3.5
    # contribution = idf_apple * 5.0 / 3.5
    expected_doc1_score = idf_apple * (2 * 2.5) / (2 + 1.5 * 1.0)
    
    # Score for doc2:
    # tf = 1
    # numerator = 1 * 2.5 = 2.5
    # denominator = 1 + 1.5 = 2.5
    # contribution = idf_apple * 2.5 / 2.5 = idf_apple
    expected_doc2_score = idf_apple * (1 * 2.5) / (1 + 1.5 * 1.0)
    
    results = index.search(['apple'], k=10)
    
    assert len(results) == 2
    assert results[0].symbol_id == 'doc1'  # Higher tf
    assert abs(results[0].score - expected_doc1_score) < 1e-5  # Tolerance for rounding
    assert results[1].symbol_id == 'doc2'
    assert abs(results[1].score - expected_doc2_score) < 1e-5


def test_rare_term_outranks_common():
    """Test that rare terms score higher than common terms."""
    chunks = [
        Chunk(
            id="doc1",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'rare': 1, 'common': 1}
        ),
        Chunk(
            id="doc2",
            kind="function",
            file="test.py",
            line_start=11,
            line_end=20,
            is_test=False,
            token_count=10,
            term_frequencies={'common': 1}
        ),
        Chunk(
            id="doc3",
            kind="function",
            file="test.py",
            line_start=21,
            line_end=30,
            is_test=False,
            token_count=10,
            term_frequencies={'common': 1}
        )
    ]
    
    params = BM25Params(k1=1.5, b=0.75)
    index = BM25Index.build(chunks, params, "test_hash", {})
    
    # Query for "rare" should rank doc1 high
    rare_results = index.search(['rare'], k=10)
    assert len(rare_results) == 1
    assert rare_results[0].symbol_id == 'doc1'
    
    # Query for "common" returns all 3, but with lower scores
    common_results = index.search(['common'], k=10)
    assert len(common_results) == 3
    
    # Rare term should score higher than common term (comparing doc1)
    assert rare_results[0].score > common_results[0].score


def test_tf_saturation():
    """Test that tf=10 scores less than 10x tf=1."""
    chunks = [
        Chunk(
            id="doc1",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 10}
        ),
        Chunk(
            id="doc2",
            kind="function",
            file="test.py",
            line_start=11,
            line_end=20,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 1}
        )
    ]
    
    params = BM25Params(k1=1.5, b=0.75)
    index = BM25Index.build(chunks, params, "test_hash", {})
    
    results = index.search(['word'], k=10)
    
    assert len(results) == 2
    doc1_score = results[0].score if results[0].symbol_id == 'doc1' else results[1].score
    doc2_score = results[1].score if results[1].symbol_id == 'doc2' else results[0].score
    
    # Saturation: doc1 score should be less than 10x doc2 score
    assert doc1_score < 10 * doc2_score


def test_length_normalization():
    """Test that longer documents with same tf score lower."""
    chunks = [
        Chunk(
            id="short",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 2}
        ),
        Chunk(
            id="long",
            kind="function",
            file="test.py",
            line_start=11,
            line_end=50,
            is_test=False,
            token_count=100,
            term_frequencies={'word': 2}
        )
    ]
    
    params = BM25Params(k1=1.5, b=0.75)
    index = BM25Index.build(chunks, params, "test_hash", {})
    
    results = index.search(['word'], k=10)
    
    assert len(results) == 2
    # Short document should rank higher
    assert results[0].symbol_id == 'short'
    assert results[1].symbol_id == 'long'
    assert results[0].score > results[1].score


def test_query_term_cap():
    """Test that query term repetition is capped."""
    chunks = [
        Chunk(
            id="doc1",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 1}
        )
    ]
    
    params = BM25Params(k1=1.5, b=0.75)
    index = BM25Index.build(chunks, params, "test_hash", {})
    
    # Query with term repeated 5 times should score same as 2 times (cap)
    results_2 = index.search(['word', 'word'], k=10)
    results_5 = index.search(['word'] * 5, k=10)
    
    assert len(results_2) == 1
    assert len(results_5) == 1
    assert abs(results_2[0].score - results_5[0].score) < 1e-9


def test_tie_breaking_by_id():
    """Test that ties are broken by symbol_id ascending."""
    chunks = [
        Chunk(
            id="zzz",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 1}
        ),
        Chunk(
            id="aaa",
            kind="function",
            file="test.py",
            line_start=11,
            line_end=20,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 1}
        )
    ]
    
    params = BM25Params(k1=1.5, b=0.75)
    index = BM25Index.build(chunks, params, "test_hash", {})
    
    results = index.search(['word'], k=10)
    
    assert len(results) == 2
    # Same score, so should be sorted by id
    assert results[0].symbol_id == 'aaa'
    assert results[1].symbol_id == 'zzz'


def test_empty_query_raises():
    """Test that empty query raises ValueError."""
    chunks = [
        Chunk(
            id="doc1",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 1}
        )
    ]
    
    params = BM25Params()
    index = BM25Index.build(chunks, params, "test_hash", {})
    
    with pytest.raises(ValueError, match="Query cannot be empty"):
        index.search([], k=10)


def test_save_and_load():
    """Test round-trip save and load."""
    chunks = [
        Chunk(
            id="doc1",
            kind="function",
            file="src/test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'apple': 2, 'banana': 1}
        ),
        Chunk(
            id="doc2",
            kind="function",
            file="src/test.py",
            line_start=11,
            line_end=20,
            is_test=False,
            token_count=10,
            term_frequencies={'apple': 1, 'cherry': 2}
        )
    ]
    
    params = BM25Params(k1=1.5, b=0.75)
    file_sha1s = {"src/test.py": "abc123"}
    index = BM25Index.build(chunks, params, "content_hash_123", file_sha1s)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save
        bm25_path = Path(tmpdir) / "bm25_index.json"
        index.save(bm25_path)
        
        # Create matching index.json and source file
        index_path = Path(tmpdir) / "index.json"
        with open(index_path, 'w') as f:
            json.dump({'content_hash': 'content_hash_123'}, f)
        
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        test_file = src_dir / "test.py"
        test_file.write_text("def test(): pass")
        
        # Mock sha1_file to return expected value
        import retrieval.bm25 as bm25_module
        original_sha1 = bm25_module.sha1_file
        try:
            bm25_module.sha1_file = lambda p: "abc123"
            
            # Load
            loaded = BM25Index.load(bm25_path, index_path, Path(tmpdir))
            
            # Verify
            assert loaded.N == index.N
            assert loaded.avgdl == index.avgdl
            assert loaded.params.k1 == params.k1
            assert loaded.params.b == params.b
            
            # Search should give same results
            original_results = index.search(['apple'], k=10)
            loaded_results = loaded.search(['apple'], k=10)
            
            assert len(original_results) == len(loaded_results)
            for orig, load in zip(original_results, loaded_results):
                assert orig.symbol_id == load.symbol_id
                assert abs(orig.score - load.score) < 1e-9
        finally:
            bm25_module.sha1_file = original_sha1


def test_stale_content_hash_raises():
    """Test that mismatched content hash raises StaleIndexError."""
    chunks = [
        Chunk(
            id="doc1",
            kind="function",
            file="test.py",
            line_start=1,
            line_end=10,
            is_test=False,
            token_count=10,
            term_frequencies={'word': 1}
        )
    ]
    
    params = BM25Params()
    index = BM25Index.build(chunks, params, "old_hash", {})
    
    with tempfile.TemporaryDirectory() as tmpdir:
        bm25_path = Path(tmpdir) / "bm25_index.json"
        index.save(bm25_path)
        
        # Create index.json with different hash
        index_path = Path(tmpdir) / "index.json"
        with open(index_path, 'w') as f:
            json.dump({'content_hash': 'new_hash'}, f)
        
        with pytest.raises(StaleIndexError, match="content hash mismatch"):
            BM25Index.load(bm25_path, index_path, Path(tmpdir))


def test_performance_synthetic():
    """Test performance with synthetic 50K chunk corpus."""
    import random
    
    # Generate synthetic vocabulary (Zipf-like distribution)
    vocab_size = 10000
    vocab = [f"word{i}" for i in range(vocab_size)]
    
    # Create 50K chunks
    num_chunks = 50000
    chunks = []
    
    random.seed(42)
    for i in range(num_chunks):
        # Generate random term frequencies with Zipf-like distribution
        num_terms = random.randint(5, 50)
        term_freq = {}
        for _ in range(num_terms):
            # Zipf: more common words selected more often
            word_idx = int(random.paretovariate(1.5)) % vocab_size
            term = vocab[word_idx]
            term_freq[term] = term_freq.get(term, 0) + 1
        
        token_count = sum(term_freq.values())
        
        chunks.append(Chunk(
            id=f"doc{i}",
            kind="function",
            file="test.py",
            line_start=i * 10,
            line_end=(i + 1) * 10,
            is_test=False,
            token_count=token_count,
            term_frequencies=term_freq
        ))
    
    # Build index
    params = BM25Params()
    build_start = time.perf_counter()
    index = BM25Index.build(chunks, params, "test_hash", {})
    build_time = time.perf_counter() - build_start
    
    print(f"\nBuild time for {num_chunks} chunks: {build_time:.3f}s")
    
    # Query with 6 terms
    query_terms = [vocab[i] for i in [0, 10, 100, 500, 1000, 5000]]
    
    # Run 20 times and get median
    times = []
    for _ in range(20):
        start = time.perf_counter()
        results = index.search(query_terms, k=10)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    times.sort()
    median_time = times[len(times) // 2]
    
    print(f"Median query time (20 runs, 6 terms): {median_time:.6f}s")
    print(f"Returned {len(results)} results")
    
    # Assert median < 0.1s
    assert median_time < 0.1, f"Query too slow: {median_time:.6f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
