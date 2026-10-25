"""End-to-end orchestrator for 4o4PR pipeline.

Runs all steps independently without dependencies on run_pipeline.py or run_bug_detector.py:
1. Repo Indexer - Parse and index all symbols
2. Bug Detector - Run tests and detect failures
3. Bug Grouper - Group related bugs
4. Context Builder - Build analysis context for each group
5. Root Cause Analysis - Analyze root causes
6. Patch Generator - Generate fix candidates
7. Optional: Validation, Explanation, PR preparation

Usage:
    python orchestrator.py --root /path/to/project
    python orchestrator.py --root /path/to/project --import-root src --skip-patches
    python orchestrator.py --help
"""

import argparse
import logging
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

# Configure path
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

from config import load_settings, setup_logging
from common.io import read_json, read_text, write_json, write_text, ensure_dir
from indexer.index import RepoIndexer, make_run_id
from detector.cli import main as detector_cli_main
from grouper.cli import main as grouper_cli_main
from context.cli import main as context_cli_main


logger = logging.getLogger(__name__)


# Stage registry: ordered list of (name, method_name, uses_llm)
STAGE_REGISTRY = [
    ("indexer", "_run_indexer", False),
    ("detector", "_run_detector", False),
    ("grouper", "_run_grouper", False),
    ("context", "_run_context_builder", False),
    ("patches", "_run_patch_generation", True),  # Would use LLM if fully implemented
]


def load_local_env() -> None:
    """Load backend/.env without overriding existing process variables."""
    env_path = BACKEND_DIR / ".env"
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


class StandaloneOrchestrator:
    """Orchestrates all pipeline steps independently."""
    
    def __init__(
        self,
        project_root: Path,
        import_roots: List[str],
        test_dirs: List[str],
        exclude_patterns: List[str],
        output_dir: Path,
        run_id: Optional[str] = None,
        now_utc: Optional[datetime] = None,
        settings: Optional[Any] = None
    ):
        """Initialize orchestrator.
        
        Args:
            project_root: Root directory of project to analyze
            import_roots: List of import root directories
            test_dirs: List of test directory names
            exclude_patterns: Patterns to exclude from indexing
            output_dir: Output directory for all results
            run_id: Optional run ID (auto-generated if not provided)
            now_utc: Optional UTC datetime (uses current if not provided)
            settings: Optional settings object
        """
        self.project_root = project_root.resolve()
        self.import_roots = import_roots
        self.test_dirs = test_dirs
        self.exclude_patterns = exclude_patterns
        self.output_dir = output_dir.resolve()
        self.settings = settings
        
        # Ensure UTC datetime
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        elif now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)
        
        self.now_utc = now_utc
        self.run_id = run_id or make_run_id(now_utc)
        
        # Create output directories
        self.index_dir = self.output_dir / "index"
        self.detector_dir = self.output_dir / "detector"
        self.grouping_dir = self.output_dir / "grouping"
        self.context_dir = self.output_dir / "context" / "analysis"
        self.analysis_dir = self.output_dir / "analysis"
        self.patch_dir = self.output_dir / "patches"
        self.validation_dir = self.output_dir / "validation"
        self.reporting_dir = self.output_dir / "reporting"
        
        for d in [self.index_dir, self.detector_dir, self.grouping_dir, 
                  self.context_dir, self.analysis_dir, self.patch_dir, 
                  self.validation_dir, self.reporting_dir]:
            ensure_dir(d)
    
    def run_all(
        self,
        skip_context: bool = False,
        skip_patches: bool = False,
        skip_validation: bool = False,
        skip_explanation: bool = False,
        skip_pr: bool = False,
        stop_after: Optional[str] = None
    ) -> int:
        """Run all pipeline steps.
        
        Args:
            skip_context: Skip context building
            skip_patches: Skip patch generation
            skip_validation: Skip validation
            skip_explanation: Skip explanation generation
            skip_pr: Skip PR preparation
            stop_after: Stop after completing this stage (requires non-LLM stage)
            
        Returns:
            0 on success, non-zero on failure, 2 for invalid stage, 3 for LLM stage
        """
        # Validate stop_after before creating any output
        if stop_after:
            stage_names = [name for name, _, _ in STAGE_REGISTRY]
            if stop_after not in stage_names:
                logger.error(f"Invalid stage '{stop_after}'. Valid stages: {', '.join(stage_names)}")
                return 2
            
            # Check if stop point or any stage before it uses LLM
            for name, _, uses_llm in STAGE_REGISTRY:
                if uses_llm:
                    logger.error(f"Cannot stop after '{stop_after}': stage '{name}' requires LLM")
                    return 3
                if name == stop_after:
                    break
            
            # Set LLM kill switch
            os.environ['LLM_DISABLED'] = '1'
            logger.info(f"LLM kill switch enabled (LLM_DISABLED=1)")
        
        stop_stage_index = None
        if stop_after:
            for idx, (name, _, _) in enumerate(STAGE_REGISTRY):
                if name == stop_after:
                    stop_stage_index = idx
                    break
        logger.info("=" * 80)
        logger.info(f"4o4PR STANDALONE PIPELINE - RUN ID: {self.run_id}")
        logger.info("=" * 80)
        logger.info(f"Project: {self.project_root}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Timestamp: {self.now_utc.isoformat()}Z")
        if stop_after:
            logger.info(f"Stop after: {stop_after}")
        logger.info("")
        
        completed_stages = []
        
        # Step 1: Repository Indexer
        current_stage_idx = 0
        if stop_stage_index is None or current_stage_idx <= stop_stage_index:
            logger.info("STEP 1: Repository Indexer")
            logger.info("-" * 80)
            try:
                if not self._run_indexer():
                    return 1
                completed_stages.append("indexer")
            except Exception as e:
                logger.error(f"Indexer failed: {e}", exc_info=True)
                return 1
            logger.info("")
            
            if stop_after == "indexer":
                return self._write_stop_marker(completed_stages, stop_after)
        
        # Step 2: Bug Detector
        current_stage_idx = 1
        if stop_stage_index is None or current_stage_idx <= stop_stage_index:
            logger.info("STEP 2: Bug Detector")
            logger.info("-" * 80)
            try:
                bug_report_path = self._run_detector()
                if not bug_report_path:
                    return 1
                
                # Check if any bugs detected
                bug_report = read_json(bug_report_path)
                num_bugs = bug_report.get('summary', {}).get('bugs_detected', 0)
                logger.info(f"Found {num_bugs} bugs")
                
                if num_bugs == 0:
                    logger.info("No bugs detected. Pipeline complete.")
                    completed_stages.append("detector")
                    if stop_after:
                        return self._write_stop_marker(completed_stages, stop_after)
                    logger.info("=" * 80)
                    return 0
                completed_stages.append("detector")
            except Exception as e:
                logger.error(f"Detector failed: {e}", exc_info=True)
                return 1
            logger.info("")
            
            if stop_after == "detector":
                return self._write_stop_marker(completed_stages, stop_after)
        
        # Step 3: Bug Grouper
        current_stage_idx = 2
        if stop_stage_index is None or current_stage_idx <= stop_stage_index:
            logger.info("STEP 3: Bug Grouper")
            logger.info("-" * 80)
            try:
                groups_path = self._run_grouper(bug_report_path)
                if not groups_path:
                    return 1
                
                groups_data = read_json(groups_path)
                num_groups = len(groups_data.get('groups', []))
                logger.info(f"Created {num_groups} bug group(s)")
                completed_stages.append("grouper")
            except Exception as e:
                logger.error(f"Grouper failed: {e}", exc_info=True)
                return 1
            logger.info("")
            
            if stop_after == "grouper":
                return self._write_stop_marker(completed_stages, stop_after)
        
        # Step 4: Context Builder (for each group)
        current_stage_idx = 3
        if stop_stage_index is None or current_stage_idx <= stop_stage_index:
            if not skip_context:
                logger.info("STEP 4: Context Builder")
                logger.info("-" * 80)
                try:
                    if not self._run_context_builder(groups_path, bug_report_path):
                        return 1
                    completed_stages.append("context")
                except Exception as e:
                    logger.error(f"Context building failed: {e}", exc_info=True)
                    return 1
                logger.info("")
                
                if stop_after == "context":
                    return self._write_stop_marker(completed_stages, stop_after)
            else:
                logger.info("Skipping context building (--skip-context)")
                logger.info("")
        
        # Step 5: Patch Generation
        current_stage_idx = 4
        if stop_stage_index is None or current_stage_idx <= stop_stage_index:
            if not skip_patches:
                logger.info("STEP 5: Patch Generation")
                logger.info("-" * 80)
                try:
                    if not self._run_patch_generation(groups_path):
                        logger.warning("Patch generation skipped (context required)")
                    else:
                        completed_stages.append("patches")
                except Exception as e:
                    logger.error(f"Patch generation failed: {e}", exc_info=True)
                    return 1
                logger.info("")
                
                if stop_after == "patches":
                    return self._write_stop_marker(completed_stages, stop_after)
            else:
                logger.info("Skipping patch generation (--skip-patches)")
                logger.info("")
        
        # Success
        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Results saved to: {self.output_dir}")
        logger.info("")
        logger.info("Output artifacts:")
        logger.info(f"  - Index: {self.index_dir / 'index.json'}")
        logger.info(f"  - Bug Report: {self.detector_dir / 'bug_report.json'}")
        logger.info(f"  - Bug Groups: {self.grouping_dir / 'bug_groups.json'}")
        if not skip_context:
            logger.info(f"  - Context: {self.context_dir}")
        if not skip_patches:
            logger.info(f"  - Patches: {self.patch_dir}")
        logger.info("")
        
        return 0
    
    def _run_indexer(self) -> bool:
        """Run repository indexer.
        
        Returns:
            True on success, False on failure
        """
        logger.info(f"Indexing repository: {self.project_root}")
        
        try:
            indexer = RepoIndexer(
                project_root=self.project_root,
                import_roots=self.import_roots,
                test_dirs=self.test_dirs,
                exclude_patterns=self.exclude_patterns
                # schema_version uses SCHEMA_VERSION constant by default
            )
            
            index_data = indexer.index(
                run_id=self.run_id,
                now_utc=self.now_utc
            )
            
            # Write index to file
            index_path = self.index_dir / "index.json"
            index_dict = index_data.to_dict()
            write_json(index_path, index_dict)
            
            logger.info(f"Index written to: {index_path}")
            logger.info(f"  - Symbols: {len(index_data.symbols)}")
            logger.info(f"  - Files: {len(index_data.files)}")
            logger.info(f"  - Parse errors: {len(index_data.parse_errors)}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to run indexer: {e}", exc_info=True)
            return False
    
    def _run_detector(self) -> Optional[Path]:
        """Run bug detector.
        
        Returns:
            Path to bug report JSON, or None on failure
        """
        logger.info(f"Running tests: {self.project_root}")
        
        # Set sys.argv for detector CLI
        original_argv = sys.argv
        try:
            sys.argv = [
                "detector",
                "--root", str(self.project_root),
                "--out-dir", str(self.detector_dir),
                "--run-id", self.run_id
            ]
            
            if self.settings and self.settings.logging.level == "DEBUG":
                sys.argv.append("-v")
            
            result = detector_cli_main()
            
            bug_report_path = self.detector_dir / "bug_report.json"
            if bug_report_path.exists():
                logger.info(f"Bug report written to: {bug_report_path}")
                return bug_report_path
            else:
                logger.error("Bug report not found after detector run")
                return None
        except Exception as e:
            logger.error(f"Failed to run detector: {e}", exc_info=True)
            return None
        finally:
            sys.argv = original_argv
    
    def _run_grouper(self, bug_report_path: Path) -> Optional[Path]:
        """Run bug grouper.
        
        Args:
            bug_report_path: Path to bug report JSON
            
        Returns:
            Path to bug groups JSON, or None on failure
        """
        logger.info(f"Grouping bugs from: {bug_report_path}")
        
        index_path = self.index_dir / "index.json"
        groups_path = self.grouping_dir / "bug_groups.json"
        
        # Set sys.argv for grouper CLI
        original_argv = sys.argv
        try:
            sys.argv = [
                "grouper",
                "--bug-report", str(bug_report_path),
                "--index", str(index_path),
                "--out", str(groups_path)
            ]
            
            if self.settings and self.settings.logging.level == "DEBUG":
                sys.argv.append("-v")
            
            result = grouper_cli_main()
            
            if groups_path.exists():
                logger.info(f"Bug groups written to: {groups_path}")
                return groups_path
            else:
                logger.error("Bug groups not found after grouper run")
                return None
        except Exception as e:
            logger.error(f"Failed to run grouper: {e}", exc_info=True)
            return None
        finally:
            sys.argv = original_argv
    
    def _run_context_builder(self, groups_path: Path, bug_report_path: Path) -> bool:
        """Run context builder for all groups.
        
        Args:
            groups_path: Path to bug groups JSON
            bug_report_path: Path to bug report JSON
            
        Returns:
            True on success, False on failure
        """
        try:
            groups_data = read_json(groups_path)
            groups = groups_data.get('groups', [])
            index_path = self.index_dir / "index.json"
            
            logger.info(f"Building context for {len(groups)} group(s)")
            
            for i, group in enumerate(groups, 1):
                group_id = group.get('group_id', f'group_{i}')
                logger.info(f"  [{i}/{len(groups)}] {group_id}...")
                
                group_out_dir = self.context_dir / group_id / "attempt_1"
                ensure_dir(group_out_dir)
                
                # Set sys.argv for context CLI
                original_argv = sys.argv
                try:
                    sys.argv = [
                        "context",
                        "--bug-groups", str(groups_path),
                        "--bug-report", str(bug_report_path),
                        "--index", str(index_path),
                        "--group-id", group_id,
                        "--out-dir", str(group_out_dir),
                        "--root", str(self.project_root)
                    ]
                    
                    if self.settings and self.settings.logging.level == "DEBUG":
                        sys.argv.append("-v")
                    
                    result = context_cli_main()
                    
                    context_file = group_out_dir / "analysis_context.txt"
                    if context_file.exists():
                        logger.info(f"    Context written to: {context_file}")
                    else:
                        logger.warning(f"    Context file not found for {group_id}")
                except Exception as e:
                    logger.error(f"    Failed to build context for {group_id}: {e}", exc_info=True)
                    return False
                finally:
                    sys.argv = original_argv
            
            return True
        except Exception as e:
            logger.error(f"Failed to run context builder: {e}", exc_info=True)
            return False
    
    def _run_patch_generation(self, groups_path: Path) -> bool:
        """Run patch generation for all groups.
        
        Args:
            groups_path: Path to bug groups JSON
            
        Returns:
            True on success, False on failure
        """
        try:
            groups_data = read_json(groups_path)
            groups = groups_data.get('groups', [])
            
            logger.info(f"Generating patches for {len(groups)} group(s)")
            
            # Check if context exists for all groups
            for group in groups:
                group_id = group.get('group_id', 'unknown')
                context_file = self.context_dir / group_id / "attempt_1" / "analysis_context.txt"
                if not context_file.exists():
                    logger.warning(f"Context not found for {group_id}, skipping patch generation")
                    logger.info("Run without --skip-context to generate context first")
                    return False
            
            # For now, just log that patches would be generated
            # Full patch generation requires additional components
            logger.info(f"Patch generation requires additional components not implemented in this orchestrator")
            logger.info(f"Context files are ready at: {self.context_dir}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to run patch generation: {e}", exc_info=True)
            return False
    
    def _write_stop_marker(self, completed_stages: List[str], stop_after: str) -> int:
        """Write pipeline_stop.json marker and exit.
        
        Args:
            completed_stages: List of completed stage names
            stop_after: Stage name where we stopped
            
        Returns:
            0 (success exit code)
        """
        stop_marker = {
            "stage": stop_after,
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "stages_completed": completed_stages
        }
        
        marker_path = self.output_dir / "pipeline_stop.json"
        write_json(marker_path, stop_marker)
        
        logger.info("=" * 80)
        logger.info(f"PIPELINE STOPPED AFTER: {stop_after}")
        logger.info("=" * 80)
        logger.info(f"Completed stages: {', '.join(completed_stages)}")
        logger.info(f"Stop marker: {marker_path}")
        logger.info("")
        
        return 0


def main() -> int:
    """Main entry point."""
    load_local_env()
    
    parser = argparse.ArgumentParser(
        description="Standalone orchestrator for 4o4PR pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline on a project
  python orchestrator.py --root /path/to/project
  
  # Run with specific import root
  python orchestrator.py --root /path/to/project --import-root src
  
  # Skip certain steps
  python orchestrator.py --root /path/to/project --skip-patches
  
  # Use custom output directory
  python orchestrator.py --root /path/to/project --out-dir /tmp/analysis
        """
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
        default=[],
        help="Import root directory (default: 'src')"
    )
    parser.add_argument(
        "--test-dir",
        type=str,
        action="append",
        dest="test_dirs",
        default=[],
        help="Test directory name (default: 'tests', 'test')"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        action="append",
        dest="exclude_patterns",
        default=[],
        help="Pattern to exclude (default: **/__pycache__, **/*.pyc)"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: ./runs/<run_id>)"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run ID (default: auto-generated from UTC time)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to settings.yaml"
    )
    parser.add_argument(
        "--skip-context",
        action="store_true",
        help="Skip context building step"
    )
    parser.add_argument(
        "--skip-patches",
        action="store_true",
        help="Skip patch generation step"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation step"
    )
    parser.add_argument(
        "--skip-explanation",
        action="store_true",
        help="Skip explanation generation"
    )
    parser.add_argument(
        "--skip-pr",
        action="store_true",
        help="Skip PR preparation"
    )
    parser.add_argument(
        "--stop-after",
        type=str,
        default=None,
        metavar="STAGE",
        help="Stop after completing STAGE (indexer, detector, grouper, context, patches)"
    )
    parser.add_argument(
        "--verbose", "-v",
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
    
    # Set defaults for import roots and test dirs
    import_roots = args.import_roots if args.import_roots else ["src"]
    test_dirs = args.test_dirs if args.test_dirs else ["tests", "test"]
    exclude_patterns = args.exclude_patterns if args.exclude_patterns else ["**/__pycache__", "**/*.pyc", ".git/**"]
    
    # Determine output directory
    if args.out_dir:
        out_dir = args.out_dir
    else:
        now_utc = datetime.now(timezone.utc)
        run_id = args.run_id or make_run_id(now_utc)
        out_dir = BACKEND_DIR / "runs" / run_id
    
    # Create orchestrator
    orchestrator = StandaloneOrchestrator(
        project_root=args.root,
        import_roots=import_roots,
        test_dirs=test_dirs,
        exclude_patterns=exclude_patterns,
        output_dir=out_dir,
        run_id=args.run_id,
        settings=settings
    )
    
    # Run all steps
    return orchestrator.run_all(
        skip_context=args.skip_context,
        skip_patches=args.skip_patches,
        skip_validation=args.skip_validation,
        skip_explanation=args.skip_explanation,
        skip_pr=args.skip_pr,
        stop_after=args.stop_after
    )


if __name__ == "__main__":
    sys.exit(main())
