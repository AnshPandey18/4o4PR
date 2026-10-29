"""Evaluate BM25 retrieval against fixtures with answer keys.

Builds BM25 indexes from run folders and evaluates ranking performance.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from retrieval.bm25_chunks import build_chunks, get_searchable_chunks
from retrieval.bm25 import BM25Index, BM25Params
from retrieval.bm25_query import build_query
from common.io import read_json


def evaluate_fixture(
    fixture_name: str,
    run_dir: Path,
    fixture_root: Path,
    answer_key_path: Path = None
) -> Dict:
    """Evaluate BM25 on a single fixture.
    
    Args:
        fixture_name: Name of the fixture
        run_dir: Path to run directory
        fixture_root: Path to fixture source code
        answer_key_path: Optional path to answer key JSON
        
    Returns:
        Evaluation results dictionary
    """
    print(f"\n{'='*80}")
    print(f"EVALUATING: {fixture_name}")
    print(f"{'='*80}")
    
    # Load index.json
    index_path = run_dir / "index" / "index.json"
    if not index_path.exists():
        print(f"ERROR: index.json not found at {index_path}")
        return {'error': 'index.json not found'}
    
    print(f"Loading index from {index_path}")
    
    # Build chunks
    print("Building BM25 chunks...")
    all_chunks = build_chunks(index_path, fixture_root)
    searchable_chunks = get_searchable_chunks(all_chunks, include_tests=False)  # ITEM 2.3: Explicit filter
    print(f"  Total chunks: {len(all_chunks)}")
    print(f"  Searchable chunks: {len(searchable_chunks)}")
    
    if len(searchable_chunks) == 0:
        print("ERROR: No searchable chunks")
        return {'error': 'no searchable chunks'}
    
    # Build BM25 index
    print("Building BM25 index...")
    index_data = read_json(index_path)
    files_dict = index_data.get('files', {})
    file_sha1s = {file_path: file_info['sha1'] for file_path, file_info in files_dict.items()}
    params = BM25Params(k1=1.5, b=0.75)
    bm25_index = BM25Index.build(
        searchable_chunks,
        params,
        index_data.get('content_hash', ''),
        file_sha1s
    )
    
    # Save index
    bm25_path = run_dir / "bm25_index.json"
    bm25_index.save(bm25_path)
    print(f"BM25 index saved to {bm25_path}")
    
    # Load bug groups
    bug_groups_path = run_dir / "grouping" / "bug_groups.json"
    if not bug_groups_path.exists():
        print(f"ERROR: bug_groups.json not found")
        return {'error': 'bug_groups.json not found'}
    
    bug_groups_data = read_json(bug_groups_path)
    groups = bug_groups_data.get('groups', [])
    
    # Load bug report
    bug_report_path = run_dir / "detector" / "bug_report.json"
    if not bug_report_path.exists():
        print(f"ERROR: bug_report.json not found")
        return {'error': 'bug_report.json not found'}
    
    bug_report_data = read_json(bug_report_path)
    bugs = {b['bug_id']: b for b in bug_report_data.get('bugs', [])}
    
    # Load answer key if provided
    answer_key = None
    if answer_key_path and answer_key_path.exists():
        answer_key = read_json(answer_key_path)
        print(f"Answer key loaded: {len(answer_key.get('bugs', []))} bugs")
    else:
        print("No answer key available")
    
    # Evaluate each group
    results = []
    
    for group in groups:
        group_id = group['group_id']
        print(f"\n{'-'*80}")
        print(f"Group {group_id}")
        print(f"{'-'*80}")
        
        # Build query
        query_terms, sources = build_query(group, bugs)
        
        print(f"Query terms ({len(query_terms)} total):")
        print(f"  Test names: {sources['test_names']}")
        print(f"  Error info: {sources['error_info']}")
        print(f"  Test body: {sources['test_body']}")
        print(f"  Traceback: {sources['traceback']}")
        
        # Search
        hits = bm25_index.search(query_terms, k=10)
        
        print(f"\nTop 10 results:")
        for hit in hits:
            print(f"  {hit.rank}. {hit.symbol_id} (score: {hit.score:.4f})")
            # Show top 3 contributing terms
            top_terms = sorted(hit.breakdown, key=lambda x: -x['contribution'])[:3]
            for term_info in top_terms:
                print(f"     - {term_info['term']}: {term_info['contribution']:.4f} "
                      f"(tf={term_info['tf']}, df={term_info['df']}, idf={term_info['idf']:.3f})")
        
        # Evaluate against answer key
        group_result = {
            'group_id': group_id,
            'query_term_count': len(query_terms),
            'results_count': len(hits),
            'query_sources': sources
        }
        
        if answer_key:
            # Find expected bugs for this group
            group_bug_ids = group.get('bug_ids', [])
            expected_symbols = set()
            
            for bug in answer_key.get('bugs', []):
                # Match by file and symbol or test expectation
                bug_symbol_id = f"{bug['file']}::{bug['symbol']}"
                expected_symbols.add(bug_symbol_id)
            
            # Find ranks of expected symbols
            hit_symbol_ids = [h.symbol_id for h in hits]
            found_at_ranks = {}
            
            for expected_symbol in expected_symbols:
                if expected_symbol in hit_symbol_ids:
                    rank = hit_symbol_ids.index(expected_symbol) + 1
                    found_at_ranks[expected_symbol] = rank
            
            group_result['expected_symbols'] = list(expected_symbols)
            group_result['found_at_ranks'] = found_at_ranks
            group_result['top1'] = len([r for r in found_at_ranks.values() if r <= 1])
            group_result['top3'] = len([r for r in found_at_ranks.values() if r <= 3])
            group_result['top5'] = len([r for r in found_at_ranks.values() if r <= 5])
            group_result['top10'] = len([r for r in found_at_ranks.values() if r <= 10])
            group_result['misses'] = list(expected_symbols - set(found_at_ranks.keys()))
            
            print(f"\nAnswer key evaluation:")
            print(f"  Expected symbols: {len(expected_symbols)}")
            print(f"  Found in top-1: {group_result['top1']}")
            print(f"  Found in top-3: {group_result['top3']}")
            print(f"  Found in top-5: {group_result['top5']}")
            print(f"  Found in top-10: {group_result['top10']}")
            if group_result['misses']:
                print(f"  Misses: {group_result['misses']}")
        
        results.append(group_result)
    
    return {
        'fixture': fixture_name,
        'chunks_total': len(all_chunks),
        'chunks_searchable': len(searchable_chunks),
        'groups_count': len(groups),
        'has_answer_key': answer_key is not None,
        'results': results
    }


def main():
    """Main evaluation script."""
    print("BM25 EVALUATION")
    print("="*80)
    
    # Define fixtures
    fixtures = [
        ('api_server', BACKEND_DIR / 'tests/fixtures/api_server', 
         BACKEND_DIR / 'tests/answer_keys/api_server.json'),
        ('data_processor', BACKEND_DIR / 'tests/fixtures/data_processor', None),
        ('string_processor', BACKEND_DIR / 'tests/fixtures/string_processor', None),
        ('sample_bugs', BACKEND_DIR / 'tests/fixtures/sample_bugs', None),
    ]
    
    all_results = []
    
    for fixture_name, fixture_root, answer_key_path in fixtures:
        run_dir = BACKEND_DIR / f"runs/bm25_eval/{fixture_name}"
        
        if not run_dir.exists():
            print(f"\nSkipping {fixture_name}: run directory not found")
            continue
        
        result = evaluate_fixture(fixture_name, run_dir, fixture_root, answer_key_path)
        all_results.append(result)
    
    # Generate summary report
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    for result in all_results:
        if 'error' in result:
            print(f"{result.get('fixture', 'unknown')}: ERROR - {result['error']}")
            continue
        
        print(f"\n{result['fixture']}:")
        print(f"  Chunks: {result['chunks_searchable']} searchable / {result['chunks_total']} total")
        print(f"  Groups: {result['groups_count']}")
        
        if result['has_answer_key']:
            # Aggregate metrics
            total_expected = sum(len(r.get('expected_symbols', [])) for r in result['results'])
            total_top1 = sum(r.get('top1', 0) for r in result['results'])
            total_top3 = sum(r.get('top3', 0) for r in result['results'])
            total_top5 = sum(r.get('top5', 0) for r in result['results'])
            total_top10 = sum(r.get('top10', 0) for r in result['results'])
            
            print(f"  Answer key results:")
            print(f"    Total expected: {total_expected}")
            print(f"    Top-1: {total_top1}/{total_expected}")
            print(f"    Top-3: {total_top3}/{total_expected}")
            print(f"    Top-5: {total_top5}/{total_expected}")
            print(f"    Top-10: {total_top10}/{total_expected}")
        else:
            print(f"  No answer key available")
    
    # Write detailed report
    report_path = BACKEND_DIR / "reports" / "bm25_eval_BEFORE.md"
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        f.write("# BM25 Evaluation Report (BEFORE tuning)\n\n")
        f.write("Evaluation of BM25 lexical search on test fixtures.\n\n")
        
        for result in all_results:
            if 'error' in result:
                f.write(f"## {result.get('fixture', 'unknown')}\n\n")
                f.write(f"**ERROR**: {result['error']}\n\n")
                continue
            
            f.write(f"## {result['fixture']}\n\n")
            f.write(f"- **Chunks**: {result['chunks_searchable']} searchable ({result['chunks_total']} total)\n")
            f.write(f"- **Groups**: {result['groups_count']}\n")
            f.write(f"- **Answer Key**: {'Yes' if result['has_answer_key'] else 'No'}\n\n")
            
            for group_result in result['results']:
                f.write(f"### Group {group_result['group_id']}\n\n")
                f.write(f"**Query** ({group_result['query_term_count']} terms):\n")
                for source_name, terms in group_result['query_sources'].items():
                    if terms:
                        f.write(f"- {source_name}: {', '.join(terms)}\n")
                f.write("\n")
                
                if result['has_answer_key']:
                    f.write(f"**Results**:\n")
                    f.write(f"- Expected: {len(group_result.get('expected_symbols', []))}\n")
                    f.write(f"- Top-1: {group_result.get('top1', 0)}\n")
                    f.write(f"- Top-3: {group_result.get('top3', 0)}\n")
                    f.write(f"- Top-5: {group_result.get('top5', 0)}\n")
                    f.write(f"- Top-10: {group_result.get('top10', 0)}\n")
                    
                    if group_result.get('found_at_ranks'):
                        f.write(f"\n**Found at ranks**:\n")
                        for symbol, rank in sorted(group_result['found_at_ranks'].items(), key=lambda x: x[1]):
                            f.write(f"- {symbol}: rank {rank}\n")
                    
                    if group_result.get('misses'):
                        f.write(f"\n**Misses** (not in top-10):\n")
                        for symbol in group_result['misses']:
                            f.write(f"- {symbol}\n")
                    f.write("\n")
    
    print(f"\nDetailed report written to: {report_path}")
    print("\nEvaluation complete!")


if __name__ == "__main__":
    main()
