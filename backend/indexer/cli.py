"""Command-line interface for repository indexer."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from common.io import write_json, ensure_dir
from config import load_settings, setup_logging
from .index import RepoIndexer


def generate_run_id() -> str:
    """Generate a run ID based on current timestamp.
    
    Returns:
        Run ID in format r_YYYYMMDD_HHMMSS
    """
    now = datetime.now()
    return now.strftime("r_%Y%m%d_%H%M%S")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Index a Python repository for static analysis"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root directory (default: from config)"
    )
    parser.add_argument(
        "--import-root",
        type=str,
        action="append",
        dest="import_roots",
        help="Import root directory (can be specified multiple times)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output path for index.json"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run ID (default: auto-generated)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache lookup and writing"
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
        settings = load_settings(
            config_path=args.config,
            project_root=args.root
        )
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        return 1
    
    # Setup logging
    if args.verbose:
        settings.logging.level = "DEBUG"
    setup_logging(settings)
    
    logger = logging.getLogger(__name__)
    
    # Override import roots if provided
    if args.import_roots:
        settings.import_roots = args.import_roots
        logger.info(f"Using import roots from command line: {args.import_roots}")
    
    # Generate run ID if not provided
    run_id = args.run_id or generate_run_id()
    logger.info(f"Run ID: {run_id}")
    
    # Determine cache directory
    cache_dir = None if args.no_cache else settings.cache_dir
    
    # Create indexer
    indexer = RepoIndexer(
        project_root=settings.project_root,
        import_roots=settings.import_roots,
        test_dirs=settings.test_dirs,
        exclude_patterns=settings.exclude_dirs,
        schema_version=settings.schema_versions.index
    )
    
    # Run indexing
    try:
        logger.info(f"Indexing project at {settings.project_root}")
        index_data = indexer.index(run_id=run_id, cache_dir=cache_dir)
        
        # Write output
        out_path = Path(args.out)
        ensure_dir(out_path.parent)
        write_json(out_path, index_data.to_dict())
        
        logger.info(f"Index written to {out_path}")
        logger.info(f"Summary: {len(index_data.files)} files, "
                   f"{len(index_data.symbols)} symbols, "
                   f"{len(index_data.parse_errors)} parse errors")
        
        # Print warnings for parse errors
        if index_data.parse_errors:
            logger.warning(f"Parse errors in {len(index_data.parse_errors)} files:")
            for error in index_data.parse_errors[:5]:  # Show first 5
                logger.warning(f"  {error.file}:{error.line}: {error.message}")
            if len(index_data.parse_errors) > 5:
                logger.warning(f"  ... and {len(index_data.parse_errors) - 5} more")
        
        return 0
    
    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
