"""Convenience script to run the complete pipeline on a project.

This script runs all 4 stages in sequence:
1. Repo Indexer
2. Bug Detector  
3. Bug Grouper
4. Context Builder (for each group)
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import load_settings, setup_logging
from common.io import read_json, ensure_dir


def generate_run_id() -> str:
    """Generate a run ID based on current timestamp."""
    now = datetime.now()
    return now.strftime("r_%Y%m%d_%H%M%S")


def main():
    """Main entry point for pipeline runner."""
    parser = argparse.ArgumentParser(
        description="Run the complete 4o4PR pipeline (Steps 1-4)"
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Project root directory to analyze"
    )
    parser.add_argument(
        "--import-root",
        type=str,
        action="append",
        dest="import_roots",
        help="Import root directory (can be specified multiple times)"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: runs/<run_id>)"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run ID (default: auto-generated)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to settings.yaml (default: config/settings.yaml)"
    )
    parser.add_argument(
        "--skip-context",
        action="store_true",
        help="Skip context building (only run indexer, detector, grouper)"
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
        settings = load_settings(config_path=args.config, project_root=args.root)
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        return 1
    
    # Setup logging
    if args.verbose:
        settings.logging.level = "DEBUG"
    setup_logging(settings)
    
    logger = logging.getLogger(__name__)
    
    # Generate run ID
    run_id = args.run_id or generate_run_id()
    
    # Determine output directory
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        backend_dir = Path(__file__).parent
        out_dir = backend_dir / "runs" / run_id
    
    ensure_dir(out_dir)
    
    logger.info("=" * 70)
    logger.info(f"4o4PR PIPELINE - RUN ID: {run_id}")
    logger.info("=" * 70)
    logger.info(f"Project: {args.root}")
    logger.info(f"Output: {out_dir}")
    logger.info("")
    
    # Override import roots if provided
    if args.import_roots:
        settings.import_roots = args.import_roots
    
    # Resolve project root to absolute path
    project_root = Path(args.root).resolve()
    
    # Prepare directories
    index_dir = out_dir / "index"
    detector_dir = out_dir / "detector"
    grouping_dir = out_dir / "grouping"
    context_dir = out_dir / "context" / "analysis"
    
    ensure_dir(index_dir)
    ensure_dir(detector_dir)
    ensure_dir(grouping_dir)
    ensure_dir(context_dir)
    
    # Step 1: Repository Indexer
    logger.info("STEP 1: Repository Indexer")
    logger.info("-" * 70)
    
    index_path = index_dir / "index.json"
    
    sys.argv = [
        "indexer",
        "--root", str(project_root),
        "--out", str(index_path),
        "--run-id", run_id,
        "--config", str(args.config) if args.config else "config/settings.yaml"
    ]
    
    if args.import_roots:
        for root in args.import_roots:
            sys.argv.extend(["--import-root", root])
    
    if args.verbose:
        sys.argv.append("-v")
    
    try:
        from indexer.cli import main as indexer_main
        result = indexer_main()
        if result != 0:
            logger.error("Indexer failed")
            return 1
    except Exception as e:
        logger.error(f"Indexer failed: {e}", exc_info=True)
        return 1
    
    logger.info("")
    
    # Step 2: Bug Detector
    logger.info("STEP 2: Bug Detector")
    logger.info("-" * 70)
    
    sys.argv = [
        "detector",
        "--root", str(project_root),
        "--out-dir", str(detector_dir),
        "--run-id", run_id,
        "--config", str(args.config) if args.config else "config/settings.yaml"
    ]
    
    if args.import_roots:
        for root in args.import_roots:
            sys.argv.extend(["--import-root", root])
    
    if args.verbose:
        sys.argv.append("-v")
    
    try:
        from detector.cli import main as detector_main
        result = detector_main()
        # Detector returns 1 if bugs found, which is expected
    except Exception as e:
        logger.error(f"Detector failed: {e}", exc_info=True)
        return 1
    
    logger.info("")
    
    # Check if any bugs were detected
    bug_report_path = detector_dir / "bug_report.json"
    try:
        bug_report = read_json(bug_report_path)
        num_bugs = bug_report.get('summary', {}).get('bugs_detected', 0)
        
        if num_bugs == 0:
            logger.info("No bugs detected. Pipeline complete.")
            logger.info("=" * 70)
            return 0
    except Exception as e:
        logger.error(f"Failed to read bug report: {e}")
        return 1
    
    # Step 3: Bug Grouper
    logger.info("STEP 3: Bug Grouper")
    logger.info("-" * 70)
    
    groups_path = grouping_dir / "bug_groups.json"
    
    sys.argv = [
        "grouper",
        "--bug-report", str(bug_report_path),
        "--index", str(index_path),
        "--out", str(groups_path),
        "--config", str(args.config) if args.config else "config/settings.yaml"
    ]
    
    if args.verbose:
        sys.argv.append("-v")
    
    try:
        from grouper.cli import main as grouper_main
        result = grouper_main()
        if result != 0:
            logger.error("Grouper failed")
            return 1
    except Exception as e:
        logger.error(f"Grouper failed: {e}", exc_info=True)
        return 1
    
    logger.info("")
    
    if args.skip_context:
        logger.info("Skipping context building (--skip-context)")
        logger.info("=" * 70)
        return 0
    
    # Step 4: Context Builder (for each group)
    logger.info("STEP 4: Context Builder")
    logger.info("-" * 70)
    
    try:
        groups_data = read_json(groups_path)
        groups = groups_data.get('groups', [])
        
        logger.info(f"Building context for {len(groups)} group(s)")
        
        for group in groups:
            group_id = group['group_id']
            logger.info(f"\nBuilding context for {group_id}...")
            
            group_out_dir = context_dir / group_id / "attempt_1"
            ensure_dir(group_out_dir)
            
            sys.argv = [
                "context",
                "--bug-groups", str(groups_path),
                "--bug-report", str(bug_report_path),
                "--index", str(index_path),
                "--group-id", group_id,
                "--out-dir", str(group_out_dir),
                "--root", str(project_root),
                "--config", str(args.config) if args.config else "config/settings.yaml"
            ]
            
            if args.verbose:
                sys.argv.append("-v")
            
            from context.cli import main as context_main
            result = context_main()
            if result != 0:
                logger.warning(f"Context building failed for {group_id}")
    
    except Exception as e:
        logger.error(f"Context building failed: {e}", exc_info=True)
        return 1
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Results saved to: {out_dir}")
    logger.info("")
    logger.info("Next steps:")
    logger.info(f"1. Review bug report: {detector_dir / 'bug_report.md'}")
    logger.info(f"2. Review bug groups: {groups_path}")
    logger.info(f"3. Review context for each group in: {context_dir}")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
