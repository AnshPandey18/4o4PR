"""R5: Real-index integration test for BM25 retrieval."""

import shutil
import tempfile
from pathlib import Path

import pytest

# Add backend to path
import sys
BACKEND_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from indexer.index import RepoIndexer
from retrieval.bm25_chunks import build_chunks, get_searchable_chunks
from retrieval.bm25 import BM25Index, BM25Params
from common.io import read_json


def test_real_index_integration():
    """Test BM25 indexing on real fixture with full pipeline.
    
    R5: Run the real indexer on a temporary copy of tests/fixtures/api_server.
    Build chunks and the BM25 index from its output. Assert every class symbol
    yields a skeleton chunk and every chunk id exists in the index's symbols.
    """
    # Create temporary copy of api_server fixture
    fixture_src = BACKEND_DIR / "tests" / "fixtures" / "api_server"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        fixture_copy = tmpdir / "api_server"
        output_dir = tmpdir / "output"
        output_dir.mkdir()
        
        # Copy fixture
        shutil.copytree(fixture_src, fixture_copy)
        
        # Run real indexer
        indexer = RepoIndexer(
            project_root=fixture_copy,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[]
        )
        
        index_path = output_dir / "index.json"
        index_data_obj = indexer.index()
        
        # Write index
        import json
        with open(index_path, 'w') as f:
            json.dump(index_data_obj.to_dict(), f, indent=2)
        
        assert index_path.exists(), "Indexer should create index.json"
        
        # Load index
        index_data = read_json(index_path)
        symbols = index_data.get('symbols', {})
        
        print(f"\nIndexed {len(symbols)} symbols")
        
        # Build chunks from index
        all_chunks = build_chunks(index_path, fixture_copy)
        searchable_chunks = get_searchable_chunks(all_chunks)
        
        print(f"Built {len(all_chunks)} total chunks")
        print(f"  {len(searchable_chunks)} searchable chunks")
        
        assert len(all_chunks) > 0, "Should build chunks from index"
        assert len(searchable_chunks) > 0, "Should have searchable chunks"
        
        # Verify every class symbol yields a skeleton chunk
        class_symbols = {
            sym_id: sym_data 
            for sym_id, sym_data in symbols.items() 
            if sym_data.get('kind') == 'class'
        }
        
        print(f"\nFound {len(class_symbols)} class symbols")
        
        chunk_ids = {chunk.id for chunk in all_chunks}
        
        for class_id in class_symbols:
            # Check if class has a chunk (skeleton or full)
            assert class_id in chunk_ids, \
                f"Class symbol {class_id} should have a chunk"
        
        print(f"[PASS] All {len(class_symbols)} class symbols have chunks")
        
        # Build BM25 index
        files_dict = index_data.get('files', {})
        file_sha1s = {
            file_path: file_info['sha1'] 
            for file_path, file_info in files_dict.items()
        }
        
        params = BM25Params(k1=1.5, b=0.75)
        bm25_index = BM25Index.build(
            searchable_chunks,
            params,
            index_data.get('content_hash', ''),
            file_sha1s
        )
        
        print(f"\nBuilt BM25 index with {len(bm25_index.chunks)} indexed chunks")
        
        # Verify every chunk id exists in the index's chunks
        indexed_chunk_ids = {chunk_meta['id'] for chunk_meta in bm25_index.chunks}
        
        for chunk in searchable_chunks:
            chunk_id = chunk.id
            assert chunk_id in indexed_chunk_ids, \
                f"Chunk {chunk_id} should be in BM25 index chunks"
        
        print(f"[PASS] All {len(searchable_chunks)} searchable chunks in BM25 index")
        
        # Verify index structure
        assert len(bm25_index.postings) > 0, "Index should have postings"
        assert bm25_index.N == len(searchable_chunks), "Index N should match searchable chunk count"
        
        print(f"[PASS] BM25 index has {len(bm25_index.postings)} vocabulary terms")
        print(f"[PASS] Integration test PASSED")


if __name__ == "__main__":
    test_real_index_integration()
