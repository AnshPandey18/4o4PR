"""Test script for LLM reviewer on single function."""

import argparse
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from common.io import read_json
from detector.bug_detector import BugDetector
from config import load_settings, setup_logging


def main():
    """Test LLM reviewer on a single function."""
    parser = argparse.ArgumentParser(description="Test LLM reviewer on single function")
    parser.add_argument("--repo-root", type=Path, required=True, help="Repository root")
    parser.add_argument("--run-dir", type=Path, required=True, help="Run directory")
    parser.add_argument("--function", type=str, required=True, help="Qualified function name")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    logger = logging.getLogger(__name__)
    
    # Resolve paths
    index_path = args.run_dir / "index.json"
    graph_path = args.run_dir / "graph.json"
    
    if not index_path.exists():
        logger.error(f"index.json not found: {index_path}")
        return 1
    
    if not graph_path.exists():
        logger.error(f"graph.json not found: {graph_path}")
        return 1
    
    # Create detector
    detector = BugDetector(
        repo_root=args.repo_root,
        run_dir=args.run_dir,
        index_path=index_path,
        graph_path=graph_path,
        llm_enabled=True
    )
    
    # Review single function
    candidate = detector.review_single_function(args.function)
    
    if candidate:
        logger.info("=" * 60)
        logger.info("CANDIDATE FOUND")
        logger.info("=" * 60)
        logger.info(f"Symbol: {candidate.get('symbol')}")
        logger.info(f"Category: {candidate.get('category')}")
        logger.info(f"Lines: {candidate.get('line_start')}-{candidate.get('line_end')}")
        logger.info(f"Description: {candidate.get('description')}")
        logger.info("=" * 60)
    else:
        logger.info("No candidate found (no bugs or error)")
    
    # Print status
    logger.info("\nStatus counters:")
    for key, value in detector.status.items():
        logger.info(f"  {key}: {value}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
