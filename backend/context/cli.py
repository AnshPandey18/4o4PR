"""Command-line interface for context builder."""

import argparse
import logging
import sys
from pathlib import Path

from common.io import read_json, ensure_dir
from common.tokens import create_token_counter
from config import load_settings, setup_logging
from indexer.query import RepoIndex
from .builder import ContextBuilder, save_context_artifacts
from .models import ContextStatus


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build analysis context for a bug group"
    )
    parser.add_argument(
        "--bug-groups",
        type=Path,
        required=True,
        help="Path to bug_groups.json"
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
        required=True,
        help="Path to index.json"
    )
    parser.add_argument(
        "--group-id",
        type=str,
        required=True,
        help="Group ID to build context for (e.g., G1)"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for context artifacts"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root directory (default: from config)"
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
        settings = load_settings(config_path=args.config, project_root=args.root)
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        return 1
    
    # Setup logging
    if args.verbose:
        settings.logging.level = "DEBUG"
    setup_logging(settings)
    
    logger = logging.getLogger(__name__)
    
    # Load bug groups
    try:
        bug_groups_data = read_json(args.bug_groups)
        run_id = bug_groups_data['run_id']
        groups = {g['group_id']: g for g in bug_groups_data['groups']}
    except Exception as e:
        logger.error(f"Failed to load bug groups: {e}")
        return 1
    
    # Find the requested group
    if args.group_id not in groups:
        logger.error(f"Group {args.group_id} not found in bug_groups.json")
        logger.info(f"Available groups: {', '.join(groups.keys())}")
        return 1
    
    group = groups[args.group_id]
    logger.info(f"Building context for {args.group_id} (run_id: {run_id})")
    
    # Load bug report
    try:
        bug_report_data = read_json(args.bug_report)
        bugs = {bug['bug_id']: bug for bug in bug_report_data['bugs']}
    except Exception as e:
        logger.error(f"Failed to load bug report: {e}")
        return 1
    
    # Load index
    try:
        logger.info(f"Loading index from {args.index}")
        index = RepoIndex.load(args.index, settings.project_root)
    except Exception as e:
        logger.error(f"Failed to load index: {e}")
        return 1
    
    # Create token counter
    token_counter = create_token_counter(
        method=settings.context.token_counter,
        model=settings.context.tiktoken_model
    )
    
    # Create context builder
    prompts_dir = Path(__file__).parent.parent / "prompts" / "analysis_v1"
    
    builder = ContextBuilder(
        project_root=settings.project_root,
        prompts_dir=prompts_dir,
        token_counter=token_counter,
        input_budget=settings.context.analysis.input_budget,
        output_reserved=settings.context.analysis.output_reserved,
        tier_budgets=settings.context.tier_budgets,
        redact_patterns=settings.context.redact_patterns,
        denylist_files=settings.context.denylist_files
    )
    
    # Build context
    try:
        logger.info(f"Building context for group {args.group_id}")
        context = builder.build(
            group=group,
            bugs=bugs,
            index=index,
            run_id=run_id,
            attempt=1
        )
        
        # Save artifacts
        out_dir = Path(args.out_dir)
        ensure_dir(out_dir)
        save_context_artifacts(context, out_dir)
        
        logger.info(f"Context artifacts written to {out_dir}")
        
        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("CONTEXT BUILDING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Status: {context.status.value}")
        logger.info(f"Group: {args.group_id}")
        logger.info(f"Bugs: {len(group['bug_ids'])}")
        
        if context.status == ContextStatus.OK:
            logger.info(f"Token Budget: {context.manifest.budget['input']}")
            logger.info(f"Tokens Used: {context.manifest.budget['used']}")
            logger.info(f"Utilization: {context.manifest.budget['used'] / context.manifest.budget['input'] * 100:.1f}%")
            logger.info(f"Included Items: {len(context.manifest.included)}")
            logger.info(f"Dropped Items: {len(context.manifest.dropped)}")
            
            if context.manifest.sanitization:
                san = context.manifest.sanitization
                logger.info(f"Sanitization:")
                logger.info(f"  Docstrings removed: {san.docstrings_removed}")
                logger.info(f"  Comments removed: {san.comments_removed}")
                logger.info(f"  Secrets redacted: {san.secrets_redacted}")
        else:
            logger.error("Context building failed (overflow)")
            if context.manifest.dropped:
                logger.info("Reasons:")
                for item in context.manifest.dropped[:5]:
                    logger.info(f"  {item.reason}")
        
        if context.manifest.warnings:
            logger.warning("Warnings:")
            for warning in context.manifest.warnings:
                logger.warning(f"  {warning}")
        
        logger.info("=" * 60)
        
        return 0 if context.status == ContextStatus.OK else 1
    
    except Exception as e:
        logger.error(f"Context building failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
