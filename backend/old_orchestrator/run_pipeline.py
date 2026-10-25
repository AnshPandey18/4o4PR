"""Convenience script to run the complete pipeline on a project.

This script runs the available stages in sequence:
1. Repo Indexer
2. Bug Detector  
3. Bug Grouper
4. Context Builder (for each group)
5. Root Cause Analysis (through OmniRoute)
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from config import load_settings, setup_logging
from common.io import read_json, read_text, write_json, ensure_dir
from analysis import (
    OpenAICompatibleClient,
    PatchGenerator,
    RootCauseAnalysisAgent,
)


def load_local_env() -> None:
    """Load backend/.env without overriding existing process variables."""

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def generate_run_id() -> str:
    """Generate a run ID based on current timestamp."""
    now = datetime.now()
    return now.strftime("r_%Y%m%d_%H%M%S")


def main():
    """Main entry point for pipeline runner."""
    load_local_env()

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
        "--generate-patches",
        action="store_true",
        help="Generate patch candidates after RCA (requires OmniRoute)"
    )
    parser.add_argument(
        "--patch-only",
        action="store_true",
        help="Run through patch generation only; never apply, validate, explain, or prepare a PR"
    )
    parser.add_argument(
        "--apply-patches",
        action="store_true",
        help="Deprecated and ignored; patches are only written to JSON files"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run pytest after patch application or against the current project"
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Generate developer explanations through OmniRoute"
    )
    parser.add_argument(
        "--prepare-pr",
        action="store_true",
        help="Prepare a deterministic PR body artifact"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()

    if args.patch_only or args.generate_patches:
        args.generate_patches = True
        args.apply_patches = False
        args.validate = False
        args.explain = False
        args.prepare_pr = False
    
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
    analysis_dir = out_dir / "analysis"
    patch_dir = out_dir / "patches"
    validation_dir = out_dir / "validation"
    reporting_dir = out_dir / "reporting"
    
    ensure_dir(index_dir)
    ensure_dir(detector_dir)
    ensure_dir(grouping_dir)
    ensure_dir(context_dir)
    ensure_dir(analysis_dir)
    ensure_dir(patch_dir)
    ensure_dir(validation_dir)
    ensure_dir(reporting_dir)
    
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
                logger.error(f"Context building failed for {group_id}")
                return 1
    
    except Exception as e:
        logger.error(f"Context building failed: {e}", exc_info=True)
        return 1

    # Step 5: Root Cause Analysis through OmniRoute
    logger.info("")
    logger.info("STEP 5: Root Cause Analysis")
    logger.info("-" * 70)

    try:
        rca_agent = RootCauseAnalysisAgent()

        for group in groups:
            group_id = group['group_id']
            context_path = context_dir / group_id / "attempt_1" / "analysis_context.txt"
            group_analysis_dir = analysis_dir / group_id
            result_path = group_analysis_dir / "analysis_result.json"

            if not context_path.exists():
                logger.error(f"Analysis context not found for {group_id}: {context_path}")
                return 1

            logger.info(f"Analyzing {group_id} with OmniRoute...")
            prompt = read_text(context_path)
            result = rca_agent.analyze(prompt)
            write_json(result_path, result.to_dict())
            logger.info(f"RCA result written to {result_path}")

    except Exception as e:
        logger.error(f"Root cause analysis failed: {e}", exc_info=True)
        return 1

    # Step 6: Patch Generation and optional application
    if args.generate_patches or args.apply_patches:
        logger.info("")
        logger.info("STEP 6: Patch Generation")
        logger.info("-" * 70)

        try:
            patch_client = OpenAICompatibleClient()
            patch_generator = PatchGenerator(client=patch_client)

            for group in groups:
                group_id = group['group_id']
                context_path = context_dir / group_id / "attempt_1" / "analysis_context.txt"
                analysis_path = analysis_dir / group_id / "analysis_result.json"
                group_patch_dir = patch_dir / group_id
                ensure_dir(group_patch_dir)

                analysis_result = read_json(analysis_path)
                context_prompt = read_text(context_path)
                candidate = patch_generator.generate(analysis_result, context_prompt)
                candidate_path = group_patch_dir / "patch_candidate.json"
                write_json(candidate_path, candidate.to_dict())
                logger.info(f"Patch candidate written to {candidate_path}")

        except Exception as e:
            logger.error(f"Patch generation failed: {e}", exc_info=True)
            return 1

        logger.info("Patch candidates generated; no source files were modified")
        if args.patch_only or args.generate_patches:
            logger.info(f"Patch candidates saved to: {patch_dir}")
            return 0

    # Step 7: Validation
    if args.validate:
        logger.info("")
        logger.info("STEP 7: Validation")
        logger.info("-" * 70)
        validation = TestValidator().validate(project_root)
        validation_path = validation_dir / "validation_result.json"
        write_json(validation_path, validation.to_dict())
        logger.info(f"Validation result written to {validation_path}")
        if not validation.passed:
            logger.error("Validation failed")
            return 1

    # Step 8: Explanation and PR artifacts
    if args.explain or args.prepare_pr:
        logger.info("")
        logger.info("STEP 8: Explanation and PR Artifacts")
        logger.info("-" * 70)
        try:
            analyses = {}
            for group in groups:
                group_id = group['group_id']
                analysis_path = analysis_dir / group_id / "analysis_result.json"
                analyses[group_id] = read_json(analysis_path)

            validation_data = None
            validation_path = validation_dir / "validation_result.json"
            if validation_path.exists():
                validation_data = read_json(validation_path)

            if args.explain:
                explainer = ExplanationGenerator(OpenAICompatibleClient())
                for group_id, analysis_data in analyses.items():
                    explanation = explainer.generate(analysis_data, validation_data)
                    explanation_path = reporting_dir / f"{group_id}_explanation.md"
                    from common.io import write_text
                    write_text(explanation_path, explanation)
                    logger.info(f"Explanation written to {explanation_path}")

            if args.prepare_pr:
                pr_path = reporting_dir / "pr_body.md"
                from common.io import write_text
                write_text(pr_path, build_pr_body(analyses, validation_data))
                logger.info(f"PR body written to {pr_path}")
        except Exception as e:
            logger.error(f"Reporting failed: {e}", exc_info=True)
            return 1
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE THROUGH REQUESTED STAGES")
    logger.info("=" * 70)
    logger.info(f"Results saved to: {out_dir}")
    logger.info("")
    logger.info("Next steps:")
    logger.info(f"1. Review bug report: {detector_dir / 'bug_report.md'}")
    logger.info(f"2. Review bug groups: {groups_path}")
    logger.info(f"3. Review context for each group in: {context_dir}")
    logger.info(f"4. Review RCA results in: {analysis_dir}")
    if args.generate_patches or args.apply_patches:
        logger.info(f"5. Review patch candidates in: {patch_dir}")
    if args.validate:
        logger.info(f"6. Review validation in: {validation_dir}")
    if args.explain or args.prepare_pr:
        logger.info(f"7. Review reporting artifacts in: {reporting_dir}")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
