"""CLI debug tool for retrieval system.

Usage:
    python -m retrieval walk --index PATH --seed SYMBOL [--seed SYMBOL ...] [--json]
"""

import argparse
import json
import sys
from pathlib import Path

from .graph import Graph, walk, explain
from .config import RetrievalConfig


def main():
    parser = argparse.ArgumentParser(description='Debug retrieval system')
    subparsers = parser.add_parsers(dest='command', help='Command')
    
    # Walk command
    walk_parser = subparsers.add_parser('walk', help='Perform graph walk')
    walk_parser.add_argument('--index', required=True, help='Path to index.json')
    walk_parser.add_argument('--seed', action='append', dest='seeds', required=True,
                            help='Seed symbol ID (can be specified multiple times)')
    walk_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    if args.command == 'walk':
        do_walk(args)
    else:
        parser.print_help()
        return 1
    
    return 0


def do_walk(args):
    """Execute the walk command."""
    # Load graph
    index_path = Path(args.index)
    if not index_path.exists():
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        return 1
    
    graph = Graph.load(index_path)
    
    # Build seeds dict
    seeds = {}
    for seed_id in args.seeds:
        if seed_id not in graph.symbols:
            print(f"Warning: Seed {seed_id} not found in index", file=sys.stderr)
            continue
        seeds[seed_id] = 1.0
    
    if not seeds:
        print("Error: No valid seeds", file=sys.stderr)
        return 1
    
    # Perform walk
    cfg = RetrievalConfig()
    hits = walk(graph, seeds, cfg)
    
    # Output
    if args.json:
        output = []
        for hit in hits:
            output.append({
                'symbol_id': hit.symbol_id,
                'score': round(hit.score, 2),
                'hop': hit.hop,
                'tier': hit.tier.value,
                'path': explain(hit)
            })
        print(json.dumps(output, indent=2))
    else:
        # Table format
        print(f"{'SCORE':<8} {'HOP':<5} {'TIER':<12} {'SYMBOL':<40} {'PATH'}")
        print("-" * 120)
        for hit in hits:
            symbol_name = hit.symbol_id.split('::')[-1]
            path_str = explain(hit)
            print(f"{hit.score:<8.2f} {hit.hop:<5} {hit.tier.value:<12} {symbol_name:<40} {path_str}")
        
        print(f"\nTotal hits: {len(hits)}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
