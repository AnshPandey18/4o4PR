#!/usr/bin/env python3
"""
Evaluate BM25 search against answer keys for Phase 5.

Usage:
    python scripts/eval_bm25_phase5.py <run_dir> <answer_key>

Example:
    python scripts/eval_bm25_phase5.py runs/r_20261024_101039 tests/answer_keys/api_server.json

This script:
1. Loads BM25 index and answer key
2. For each bug in answer key:
   a. Checks if bug is reachable (in index, not test-only)
   b. Builds query from bug metadata
   c. Searches BM25 index
   d. Scores result (HIT@1, HIT@3, HIT@10, MISS)
3. Generates detailed report with PROVISIONAL flag and tokenizer SHA256

Exit codes:
    0: Success
    1: Error (missing files, invalid data, etc.)
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.bm25 import BM25Index
from retrieval.bm25_query import build_query
from retrieval.graph import Graph

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tokenizer SHA256 for PROVISIONAL flag
TOKENIZER_SHA256 = 'b7bb2def1341a2277a9d6d4f23b5f3597c1b0bf1308b56a775f5197cdb41addd'

def compute_tokenizer_hash() -> str:
    """Compute SHA256 of tokenizer.py for verification."""
    tokenizer_path = Path(__file__).parent.parent / 'retrieval' / 'tokenizer.py'
    with open(tokenizer_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_reachability(bug: Dict, index_data: Dict, graph: Graph) -> Tuple[bool, Optional[str]]:
    """Check if bug is reachable (scorable).
    
    Args:
        bug: Bug from answer key with 'file', 'symbol', 'line' fields
        index_data: Loaded index.json data
        graph: Graph instance
        
    Returns:
        (is_reachable, reason) tuple
        - is_reachable: True if bug can be scored
        - reason: Explanation if not reachable
    """
    file_path = bug['file']
    symbol_name = bug['symbol']
    line = bug.get('line')
    
    # Check 1: File exists in index
    if file_path not in index_data.get('files', {}):
        return False, f"file_not_indexed:{file_path}"
    
    # Check 2: Symbol exists in index
    symbol_id = f"{file_path}::{symbol_name}"
    if symbol_id not in index_data.get('symbols', {}):
        return False, f"symbol_not_found:{symbol_id}"
    
    # Check 3: Symbol is not test-only
    symbol_info = index_data['symbols'][symbol_id]
    if symbol_info.get('is_test', False):
        return False, f"test_only_symbol:{symbol_id}"
    
    # Reachable
    return True, None


def score_result(bug_symbol_id: str, search_results: List, k_values: List[int] = [1, 3, 10]) -> str:
    """Score search results for a bug.
    
    Args:
        bug_symbol_id: Expected symbol ID (file::symbol format)
        search_results: List of SearchHit objects from BM25
        k_values: List of k values to check for HIT@k
        
    Returns:
        Score category: HIT@1, HIT@3, HIT@10, or MISS
    """
    # Find rank of correct symbol
    for rank, hit in enumerate(search_results, 1):
        # hit.symbol_id is already in format "file::Class.method" or "file::function"
        hit_symbol_id = hit.symbol_id
        
        if hit_symbol_id == bug_symbol_id:
            # Found it - determine HIT@k
            for k in sorted(k_values):
                if rank <= k:
                    return f"HIT@{k}"
            return "MISS"  # Beyond max k
    
    return "MISS"


def main():
    parser = argparse.ArgumentParser(description='Evaluate BM25 search for Phase 5')
    parser.add_argument('run_dir', type=Path, help='Path to run directory')
    parser.add_argument('answer_key', type=Path, help='Path to answer key JSON')
    parser.add_argument('--output', type=Path, help='Output path for report (default: run_dir/evaluation/phase5_report.json)')
    
    args = parser.parse_args()
    
    run_dir = args.run_dir.resolve()
    answer_key_path = args.answer_key.resolve()
    
    if not run_dir.exists():
        logger.error(f"Run directory not found: {run_dir}")
        return 1
    
    if not answer_key_path.exists():
        logger.error(f"Answer key not found: {answer_key_path}")
        return 1
    
    # Verify tokenizer hash
    actual_hash = compute_tokenizer_hash()
    provisional = (actual_hash != TOKENIZER_SHA256)
    if provisional:
        logger.warning(f"PROVISIONAL: Tokenizer hash mismatch (expected {TOKENIZER_SHA256[:16]}..., got {actual_hash[:16]}...)")
    
    logger.info(f"Evaluating run: {run_dir.name}")
    logger.info(f"Answer key: {answer_key_path.name}")
    logger.info(f"Provisional: {provisional}")
    
    # Load answer key
    try:
        with open(answer_key_path, 'r', encoding='utf-8') as f:
            answer_key = json.load(f)
        logger.info(f"Loaded answer key: {len(answer_key.get('bugs', []))} bugs")
    except Exception as e:
        logger.error(f"Failed to load answer key: {e}")
        return 1
    
    # Load index
    index_path = run_dir / 'index' / 'index.json'
    if not index_path.exists():
        logger.error(f"Index not found: {index_path}")
        return 1
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        logger.info(f"Loaded index: {len(index_data['symbols'])} symbols")
    except Exception as e:
        logger.error(f"Failed to load index: {e}")
        return 1
    
    # Load BM25 index
    bm25_path = run_dir / 'bm25' / 'bm25_index.json'
    if not bm25_path.exists():
        logger.error(f"BM25 index not found: {bm25_path}")
        return 1
    
    try:
        # Infer repo_root (same logic as build script)
        from indexer.models import IndexData
        repo_index = IndexData.from_dict(index_data)
        file_list = list(repo_index.files.keys())
        first_file = file_list[0]
        
        backend_dir = Path(__file__).parent.parent
        fixtures_dir = backend_dir / 'tests' / 'fixtures'
        
        found_root = None
        for fixture_name in ['api_server', 'data_processor', 'string_processor', 'sample_bugs']:
            candidate = fixtures_dir / fixture_name
            all_match = all((candidate / f).exists() for f in file_list[:5])
            if all_match:
                found_root = candidate.resolve()
                break
        
        if not found_root:
            logger.error("Could not infer repo_root")
            return 1
        
        repo_root = found_root
        logger.info(f"Inferred repo_root: {repo_root}")
        
        bm25_index = BM25Index.load(bm25_path, index_path, repo_root)
        logger.info(f"Loaded BM25 index: {len(bm25_index.chunks)} chunks")
    except Exception as e:
        logger.error(f"Failed to load BM25 index: {e}")
        return 1
    
    # Load graph for query building
    try:
        graph = Graph.load(index_path)
        logger.info(f"Loaded graph: {len(graph.symbols)} symbols")
    except Exception as e:
        logger.error(f"Failed to load graph: {e}")
        return 1
    
    # Evaluate each bug
    results = []
    reachability_counts = {'reachable': 0, 'unreachable': 0}
    score_counts = {'HIT@1': 0, 'HIT@3': 0, 'HIT@10': 0, 'MISS': 0}
    
    for bug_idx, bug in enumerate(answer_key.get('bugs', []), 1):
        bug_id = bug.get('id', f'bug_{bug_idx}')
        symbol_id = f"{bug['file']}::{bug['symbol']}"
        
        logger.info(f"[{bug_idx}/{len(answer_key['bugs'])}] Evaluating {bug_id}: {symbol_id}")
        
        # Check reachability
        is_reachable, reason = check_reachability(bug, index_data, graph)
        
        if not is_reachable:
            logger.info(f"  UNREACHABLE: {reason}")
            reachability_counts['unreachable'] += 1
            results.append({
                'bug_id': bug_id,
                'symbol_id': symbol_id,
                'reachable': False,
                'reason': reason,
                'score': 'N/A'
            })
            continue
        
        reachability_counts['reachable'] += 1
        
        # Build query
        try:
            # Create mock bug group dict and bugs dict for build_query
            # CRITICAL: Do NOT use bug['description'] - that would leak answer key data
            # Query should only use information available from actual test run
            mock_bug_dict = {
                'bug_id': bug_id,
                'test_name': f"test_{bug.get('symbol', 'unknown')}",
                'test_file': bug.get('test_file', 'tests/test_unknown.py'),
                'error_type': 'AssertionError',
                'error_message': '',  # FIXED: Was bug.get('description', '') - contamination!
                'code': '',
                'frames': []
            }
            
            bug_group_dict = {
                'bug_ids': [bug_id]
            }
            
            bugs_dict = {bug_id: mock_bug_dict}
            
            query_terms, sources = build_query(bug_group_dict, bugs_dict, graph)
            logger.info(f"  Query: {len(query_terms)} terms from {len(sources)} sources")
        except Exception as e:
            logger.warning(f"  Failed to build query: {e}")
            results.append({
                'bug_id': bug_id,
                'symbol_id': symbol_id,
                'reachable': True,
                'query_error': str(e),
                'score': 'ERROR'
            })
            continue
        
        # Search
        try:
            search_results = bm25_index.search(query_terms, k=10)
            logger.info(f"  Search: {len(search_results)} results")
        except Exception as e:
            logger.warning(f"  Search failed: {e}")
            results.append({
                'bug_id': bug_id,
                'symbol_id': symbol_id,
                'reachable': True,
                'query_terms': query_terms[:20],
                'search_error': str(e),
                'score': 'ERROR'
            })
            continue
        
        # Score
        score = score_result(symbol_id, search_results)
        logger.info(f"  Score: {score}")
        
        if score in score_counts:
            score_counts[score] += 1
        
        results.append({
            'bug_id': bug_id,
            'symbol_id': symbol_id,
            'reachable': True,
            'query_terms': query_terms[:20],  # First 20 for report
            'query_sources': sources,
            'top_results': [
                {
                    'rank': i+1,
                    'symbol_id': hit.symbol_id,
                    'score': round(hit.score, 4)
                }
                for i, hit in enumerate(search_results[:5])
            ],
            'score': score
        })
    
    # Generate report
    output_path = args.output or (run_dir / 'evaluation' / 'phase5_report.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        'schema_version': 'phase5-eval-1.0',
        'provisional': provisional,
        'tokenizer_sha256': actual_hash,
        'run_id': run_dir.name,
        'answer_key': answer_key_path.name,
        'fixture': answer_key.get('fixture', 'unknown'),
        'timestamp': index_data.get('generated_at', ''),
        'summary': {
            'total_bugs': len(answer_key.get('bugs', [])),
            'reachable': reachability_counts['reachable'],
            'unreachable': reachability_counts['unreachable'],
            'hit_at_1': score_counts['HIT@1'],
            'hit_at_3': score_counts['HIT@3'],
            'hit_at_10': score_counts['HIT@10'],
            'miss': score_counts['MISS']
        },
        'results': results
    }
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report written: {output_path}")
    except Exception as e:
        logger.error(f"Failed to write report: {e}")
        return 1
    
    # Print summary
    print("\n" + "="*80)
    print(f"PHASE 5 EVALUATION SUMMARY {'(PROVISIONAL)' if provisional else ''}")
    print("="*80)
    print(f"Run: {run_dir.name}")
    print(f"Fixture: {answer_key.get('fixture', 'unknown')}")
    print(f"Total bugs: {len(answer_key.get('bugs', []))}")
    print(f"Reachable: {reachability_counts['reachable']}")
    print(f"Unreachable: {reachability_counts['unreachable']}")
    print(f"\nScores (reachable only):")
    print(f"  HIT@1:  {score_counts['HIT@1']}")
    print(f"  HIT@3:  {score_counts['HIT@3']}")
    print(f"  HIT@10: {score_counts['HIT@10']}")
    print(f"  MISS:   {score_counts['MISS']}")
    print("="*80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
