#!/usr/bin/env python3
"""
Build BM25 index for a completed pipeline run.

Usage:
    python scripts/build_bm25_run.py <run_dir>

Example:
    python scripts/build_bm25_run.py runs/r_20261024_101039

This script:
1. Loads index.json from run_dir/index/
2. Builds searchable chunks from index
3. Builds BM25 index from chunks with k1=1.5, b=0.75
4. Writes bm25_index.json to run_dir/bm25/

Exit codes:
    0: Success
    1: Error (missing files, invalid data, etc.)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.bm25 import BM25Index
from retrieval.bm25_chunks import build_chunks, get_searchable_chunks
from indexer.models import IndexData

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Build BM25 index for a pipeline run')
    parser.add_argument('run_dir', type=Path, help='Path to run directory (e.g., runs/r_20261024_101039)')
    parser.add_argument('--k1', type=float, default=1.5, help='BM25 k1 parameter (default: 1.5)')
    parser.add_argument('--b', type=float, default=0.75, help='BM25 b parameter (default: 0.75)')
    
    args = parser.parse_args()
    
    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        logger.error(f"Run directory not found: {run_dir}")
        return 1
    
    index_path = run_dir / 'index' / 'index.json'
    if not index_path.exists():
        logger.error(f"Index file not found: {index_path}")
        return 1
    
    logger.info(f"Building BM25 index for run: {run_dir.name}")
    logger.info(f"Index path: {index_path}")
    logger.info(f"BM25 parameters: k1={args.k1}, b={args.b}")
    
    # Load index
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        
        repo_index = IndexData.from_dict(index_data)
        logger.info(f"Loaded index: {len(repo_index.symbols)} symbols, {len(repo_index.files)} files")
    except Exception as e:
        logger.error(f"Failed to load index: {e}")
        return 1
    
    # Get repo root from run metadata or infer from run directory
    # The orchestrator was run with --root <fixture_path>, so we need to find that
    # Check if there's a metadata file or infer from directory structure
    run_metadata_path = run_dir / 'run_metadata.json'
    
    if run_metadata_path.exists():
        with open(run_metadata_path, 'r', encoding='utf-8') as f:
            run_metadata = json.load(f)
        repo_root = Path(run_metadata.get('repo_root', '')).resolve()
    else:
        # Infer: if run_dir is runs/r_*/,  check for fixture based on index files
        # Look at file paths in index - they're relative to the fixture root
        file_list = list(repo_index.files.keys()) if isinstance(repo_index.files, dict) else repo_index.files
        first_file = file_list[0] if file_list else None
        if not first_file:
            logger.error("Index has no files, cannot infer repo_root")
            return 1
        
        # Try to find the fixture directory by looking for the first indexed file
        # Check common locations
        backend_dir = Path(__file__).parent.parent
        fixtures_dir = backend_dir / 'tests' / 'fixtures'
        
        # Try each fixture
        found_root = None
        for fixture_name in ['api_server', 'data_processor', 'string_processor', 'sample_bugs']:
            candidate = fixtures_dir / fixture_name
            test_path = candidate / first_file
            if test_path.exists():
                # Verify this is the right fixture by checking ALL files exist
                all_match = all((candidate / f).exists() for f in file_list[:5])  # Check first 5
                if all_match:
                    found_root = candidate.resolve()
                    logger.info(f"Inferred repo_root from file structure: {found_root}")
                    break
        
        if not found_root:
            logger.error(f"Could not find repo root for file: {first_file}")
            return 1
        repo_root = found_root
    
    if not repo_root.exists():
        logger.error(f"Repository root not found: {repo_root}")
        return 1
    
    logger.info(f"Repository root: {repo_root}")
    
    # Build chunks
    try:
        logger.info("Building chunks from index...")
        chunks = build_chunks(index_path, repo_root)
        searchable_chunks = get_searchable_chunks(chunks)
        logger.info(f"Built {len(searchable_chunks)} searchable chunks from {len(chunks)} total chunks")
    except Exception as e:
        logger.error(f"Failed to build chunks: {e}")
        return 1
    
    # Compute file SHA-1 hashes
    try:
        import hashlib
        file_sha1s = {}
        file_list = list(repo_index.files.keys()) if isinstance(repo_index.files, dict) else repo_index.files
        for file_path in file_list:
            full_path = repo_root / file_path
            if full_path.exists():
                with open(full_path, 'rb') as f:
                    file_sha1s[file_path] = hashlib.sha1(f.read()).hexdigest()
        logger.info(f"Computed SHA-1 hashes for {len(file_sha1s)} files")
    except Exception as e:
        logger.error(f"Failed to compute file hashes: {e}")
        return 1
    
    # Compute index content hash (use content hash from index.json)
    try:
        index_content_hash = index_data.get('content_hash', '')
        if not index_content_hash:
            logger.error("Index missing content_hash field")
            return 1
        logger.info(f"Index content hash: {index_content_hash[:16]}...")
    except Exception as e:
        logger.error(f"Failed to get index content hash: {e}")
        return 1
    
    # Build BM25 index
    try:
        from retrieval.bm25 import BM25Params
        logger.info("Building BM25 index...")
        bm25_params = BM25Params(k1=args.k1, b=args.b)
        bm25_index = BM25Index.build(
            chunks=searchable_chunks,
            params=bm25_params,
            index_content_hash=index_content_hash,
            file_sha1s=file_sha1s
        )
        logger.info(f"Built BM25 index: {len(bm25_index.chunks)} chunks, vocab size {len(bm25_index.postings)}")
    except Exception as e:
        logger.error(f"Failed to build BM25 index: {e}")
        return 1
    
    # Write BM25 index
    bm25_dir = run_dir / 'bm25'
    bm25_dir.mkdir(exist_ok=True)
    bm25_path = bm25_dir / 'bm25_index.json'
    
    try:
        logger.info(f"Writing BM25 index to {bm25_path}")
        bm25_index.save(bm25_path)
        
        # Verify written file
        file_size_mb = bm25_path.stat().st_size / (1024 * 1024)
        logger.info(f"BM25 index written: {file_size_mb:.2f} MB")
    except Exception as e:
        logger.error(f"Failed to write BM25 index: {e}")
        return 1
    
    logger.info("BM25 index build complete")
    logger.info(f"Output: {bm25_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
