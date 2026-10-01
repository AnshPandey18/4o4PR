"""Command-line interface for bug detector."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from common.io import write_json, write_text, ensure_dir
from common.hashing import content_hash
from config import load_settings, setup_logging
from .detector import BugDetector
from .markdown import generate_markdown_report


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
        description="Detect bugs in a Python project by running pytest"
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
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for bug reports"
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
        "--no-baseline",
        action="store_true",
        help="Don't generate baseline_results.json"
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
    
    # Compute content hash
    try:
        chash = content_hash(
            settings.project_root,
            settings.import_roots,
            settings.exclude_dirs,
            settings.schema_versions.bug_report
        )
        logger.info(f"Content hash: {chash[:16]}...")
    except Exception as e:
        logger.warning(f"Failed to compute content hash: {e}")
        chash = None
    
    # Create detector
    detector = BugDetector(
        project_root=settings.project_root,
        import_roots=settings.import_roots,
        timeout_seconds=settings.detector.timeout_seconds,
        flaky_reruns=settings.detector.flaky_reruns,
        embed_source_snapshot=settings.detector.embed_source_snapshot,
        snapshot_max_lines=settings.detector.snapshot_max_lines
    )
    
    # Run detection
    try:
        logger.info(f"Running bug detection on {settings.project_root}")
        result = detector.detect(
            run_id=run_id,
            schema_version=settings.schema_versions.bug_report,
            content_hash=chash
        )
        
        # Ensure output directory exists
        out_dir = Path(args.out_dir)
        ensure_dir(out_dir)
        
        # Write bug_report.json
        bug_report_path = out_dir / "bug_report.json"
        write_json(bug_report_path, result.to_dict())
        logger.info(f"Bug report written to {bug_report_path}")
        
        # Write bug_report.md
        bug_report_md_path = out_dir / "bug_report.md"
        markdown_content = generate_markdown_report(result)
        write_text(bug_report_md_path, markdown_content)
        logger.info(f"Markdown report written to {bug_report_md_path}")
        
        # Generate baseline if requested
        if not args.no_baseline:
            logger.info("Generating baseline results")
            baseline = detector.generate_baseline(run_id=run_id, content_hash=chash)
            baseline_path = out_dir / "baseline_results.json"
            write_json(baseline_path, baseline.to_dict())
            logger.info(f"Baseline results written to {baseline_path}")
        
        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("BUG DETECTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {result.summary.tests_run}")
        logger.info(f"Passed: {result.summary.passed}")
        logger.info(f"Failed: {result.summary.failed}")
        logger.info(f"Errors: {result.summary.errors}")
        logger.info(f"Bugs Detected: {result.summary.bugs_detected}")
        
        flaky_count = sum(1 for bug in result.bugs if bug.flaky)
        if flaky_count > 0:
            logger.info(f"Flaky Tests: {flaky_count}")
        
        if not result.summary.consistency_ok:
            logger.warning("⚠️  Consistency check FAILED")
        else:
            logger.info("✓ Consistency check passed")
        
        logger.info("=" * 60)
        
        # Return non-zero if bugs detected
        return 1 if result.summary.bugs_detected > 0 else 0
    
    except Exception as e:
        logger.error(f"Bug detection failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
