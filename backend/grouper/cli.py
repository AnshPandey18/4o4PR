"""Command-line interface for bug grouper."""

import argparse
import logging
import sys
from pathlib import Path

from common.io import write_json, ensure_dir, read_json
from common.tokens import create_token_counter
from config import load_settings, setup_logging
from indexer.query import RepoIndex
from .group import BugGrouper


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Group related bugs for efficient analysis"
    )
    parser.add_argument(
        "--bug-report",
        type=Path,
        required=True,
        help="Path to bug_report.json"
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="Optional path to index.json for call graph analysis"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output path for bug_groups.json"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to settings.yaml (default: config/settings.yaml)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Load settings
    try:
        settings = load_settings(config_path=args.config)
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        return 1
    
    # Setup logging
    if args.verbose:
        settings.logging.level = "DEBUG"
    setup_logging(settings)
    
    logger = logging.getLogger(__name__)
    
    # Load bug report to get run_id
    try:
        bug_report = read_json(args.bug_report)
        run_id = bug_report.get('run_id', 'unknown')
    except Exception as e:
        logger.error(f"Failed to load bug report: {e}")
        return 1
    
    logger.info(f"Run ID: {run_id}")
    
    # Load index if provided
    index = None
    if args.index:
        try:
            logger.info(f"Loading index from {args.index}")
            index = RepoIndex.load(args.index, settings.project_root)
        except Exception as e:
            logger.warning(f"Failed to load index: {e}")
    
    # Create token counter
    token_counter = create_token_counter(
        method=settings.context.token_counter,
        model=settings.context.tiktoken_model
    )
    
    # Create grouper
    grouper = BugGrouper(
        max_bugs_per_group=settings.grouper.max_bugs_per_group,
        token_counter=token_counter,
        analysis_budget=settings.context.analysis.input_budget
    )
    
    # Run grouping
    try:
        logger.info(f"Grouping bugs from {args.bug_report}")
        result = grouper.group(
            bug_report_path=args.bug_report,
            run_id=run_id,
            index=index,
            schema_version=settings.schema_versions.bug_groups
        )
        
        # Write output
        out_path = Path(args.out)
        ensure_dir(out_path.parent)
        write_json(out_path, result.to_dict())
        
        logger.info(f"Bug groups written to {out_path}")
        logger.info("")
        logger.info("=" * 60)
        logger.info("BUG GROUPING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Bugs: {result.totals.bugs}")
        logger.info(f"Groups Created: {result.totals.groups}")
        logger.info(f"Bugs Excluded: {result.totals.excluded}")
        
        # Show group breakdown
        by_kind = {}
        for group in result.groups:
            kind = group.kind
            by_kind[kind] = by_kind.get(kind, 0) + 1
        
        logger.info("")
        logger.info("Groups by kind:")
        for kind, count in sorted(by_kind.items()):
            logger.info(f"  {kind}: {count}")
        
        logger.info("=" * 60)
        
        return 0
    
    except Exception as e:
        logger.error(f"Bug grouping failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
