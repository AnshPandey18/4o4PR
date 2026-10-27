"""Combined orchestrator for 4o4PR pipeline with database integration.

This orchestrator combines:
1. Complete standalone pipeline from standalone_orchestrator.py
2. Database operations and git repository cloning from orchestrator_db.py

Supports two modes:
A. Standalone mode: Run pipeline on local repository
   python orchestrator.py --root /path/to/project

B. Database mode: Run pipeline with database integration
   python orchestrator.py --run-id run_20261009_123456
   python orchestrator.py --repository-onboarding --user-id 1 --repo-url https://github.com/owner/repo

Usage examples:
    # Standalone mode - run full pipeline
    python orchestrator.py --root /path/to/project
    
    # Standalone mode - with specific import root
    python orchestrator.py --root /path/to/project --import-root src
    
    # Standalone mode - skip certain steps
    python orchestrator.py --root /path/to/project --skip-patches
    
    # Database mode - run pipeline for existing run
    python orchestrator.py --run-id run_20261009_123456
    
    # Database mode - onboard repository
    python orchestrator.py --repository-onboarding \\
        --user-id 1 \\
        --repo-url https://github.com/facebook/react \\
        --branch main
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure path
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

from config import load_settings, setup_logging
from common.io import read_json, read_text, write_json, write_text, ensure_dir
from indexer.index import RepoIndexer, make_run_id
from detector.cli import main as detector_cli_main
from grouper.cli import main as grouper_cli_main
from context.cli import main as context_cli_main

# Database imports (only used in database mode)
try:
    from app.database import SessionLocal
    from app.models.pipeline_run import PipelineRun
    from app.models.repository import Repository
    from app.tools.console import configure_console
    from app.tools.github_client import GitHubClient, WorkspaceBusyError
    DB_AVAILABLE = True
    configure_console()
except ImportError:
    DB_AVAILABLE = False


logger = logging.getLogger(__name__)


# Stage registry: ordered list of (name, method_name, uses_llm)
STAGE_REGISTRY = [
    ("indexer", "_run_indexer", False),
    ("detector", "_run_detector", False),
    ("grouper", "_run_grouper", False),
    ("context", "_run_context_builder", False),
    ("patches", "_run_patch_generation", True),  # Would use LLM if fully implemented
]

# Statuses that mean a pipeline run is still in flight
ACTIVE_STATUSES = ("pending", "queued", "running")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")

# Hard limit for a single pipeline execution
PIPELINE_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_TIMEOUT_SECONDS", "1800"))

# Patterns that must never reach the database, the logs or an API response
_CREDENTIAL_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)(authorization\s*:\s*\S+\s+\S+)"),
    re.compile(r"(?i)(https?://)[^/\s:@]+:[^/\s:@]+@"),
)


class PipelineExecutionError(RuntimeError):
    """Raised when the pipeline cannot be executed for the current run."""


def _utcnow() -> datetime:
    """Aware UTC timestamp, matching the timezone-aware DB columns."""
    return datetime.now(timezone.utc)


def _elapsed_seconds(started_at: Optional[datetime], completed_at: datetime) -> int:
    """Seconds between two timestamps, tolerating legacy naive values."""
    if started_at is None:
        return 0
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    return int((completed_at - started_at).total_seconds())


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
    """Orchestrates all pipeline steps independently (from standalone_orchestrator.py)."""
    
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


class OrchestratorDB:
    """Database-integrated orchestrator (from orchestrator_db.py)."""

    def __init__(
        self,
        run_id: Optional[str] = None,
        user_id: Optional[int] = None,
        db=None,
    ):
        """
        Initialize orchestrator.

        Args:
            run_id: Pipeline run identifier (for pipeline execution)
            user_id: User ID (for repository onboarding)
            db: Optional existing database session. When omitted the
                orchestrator owns (and closes) its own session.
        """
        if not DB_AVAILABLE:
            raise RuntimeError("Database mode requires database dependencies. Install app dependencies.")
        
        self.run_id = run_id
        self.user_id = user_id
        self._owns_session = db is None
        self.db = db if db is not None else SessionLocal()
        self.run: Optional[PipelineRun] = None
        self.repo: Optional[Repository] = None

    # ========================================================================
    # Repository Onboarding
    # ========================================================================

    def onboard_repository(
        self,
        repo_url: str,
        branch: str = "main",
        pat: Optional[str] = None,
        visibility: str = "public",
        run_id: Optional[str] = None,
        repository_id: Optional[int] = None,
        execute_pipeline: bool = True,
    ) -> Dict[str, Any]:
        """
        Clone and register a GitHub repository, then run the pipeline for it.

        This is the entry point for the repository onboarding workflow.

        Args:
            repo_url: GitHub repository URL
            branch: Branch to clone
            pat: Personal access token (required for private repos)
            visibility: "public" or "private"
            run_id: Pre-generated pipeline run identifier (optional)
            repository_id: Identifier of an already registered repository
            execute_pipeline: Whether to execute the pipeline after cloning

        Returns:
            Dictionary with operation result
        """
        if not self.user_id:
            return {
                "status": "FAILED",
                "stage": "VALIDATING",
                "error": "User ID required for repository onboarding",
            }

        try:
            print("=" * 60)
            print("  4o4PR Repository Onboarding")
            print("=" * 60)
            print(f"  URL: {repo_url}")
            print(f"  Branch: {branch}")
            print(f"  Visibility: {visibility}")
            print("=" * 60)
            print()

            # Step 1: Validate inputs
            print("🔍 Step 1: Validating repository configuration...")
            validation_result = self._validate_repo_config(repo_url, branch, pat, visibility)
            if not validation_result["valid"]:
                return {
                    "status": "FAILED",
                    "stage": "VALIDATING",
                    "error": validation_result["error"],
                }
            print("   ✓ Validation passed")
            print()

            # Step 2: Resolve (or create) the repository record
            print("🔍 Step 2: Checking for existing repository...")
            repo, already_registered = self._resolve_repository(
                repo_url, branch, visibility, pat, repository_id
            )
            if already_registered:
                print(f"   ⚠ Repository already registered: ID {repo.id}")
            else:
                print("   ✓ No existing repository found")
            print()

            # Step 3: Clone (or reuse an existing clone)
            print("🔄 Step 3: Cloning repository...")
            try:
                clone_metadata = self._clone_repository(repo, repo_url, branch, pat)
            except WorkspaceBusyError as busy_error:
                return {
                    "status": "FAILED",
                    "stage": "CLONING",
                    "repository_id": repo.id,
                    "error": self._sanitize_error(str(busy_error)),
                }
            except Exception as clone_error:
                self._mark_clone_failed(repo)
                raise clone_error
            print()

            # Step 4: Persist the pipeline run record
            print("💾 Step 4: Persisting pipeline run...")
            run = self._create_pipeline_run(repo, run_id)
            print(f"   ✓ Pipeline run: {run.run_id}")
            print()

            print("=" * 60)
            print("  Repository Onboarding Complete!")
            print("=" * 60)
            print()

            result: Dict[str, Any] = {
                "status": "COMPLETED",
                "stage": "PERSISTING",
                "repository_id": repo.id,
                "run_id": run.run_id,
                "clone_path": repo.clone_path,
                "clone_size_mb": float(repo.clone_size_mb or 0.0),
                "clone_status": repo.clone_status,
                "commit_sha": repo.commit_sha,
                "message": (
                    "Repository already registered"
                    if already_registered
                    else "Repository cloned and registered successfully"
                ),
            }

            # Step 5: Execute the existing pipeline for this run
            if execute_pipeline:
                self.run = run
                self.repo = repo
                exit_code = self.run_pipeline()
                result["pipeline_status"] = self.run.status if self.run else "failed"
                result["pipeline_exit_code"] = exit_code
                if exit_code != 0:
                    result["status"] = "FAILED"
                    result["stage"] = "EXECUTING"
                    result["error"] = (
                        self.run.error_message if self.run else "Pipeline execution failed"
                    )

            return result

        except Exception as e:
            error_msg = self._sanitize_error(str(e))
            print(f"\n❌ Repository onboarding failed: {error_msg}")
            return {
                "status": "FAILED",
                "stage": "CLONING",
                "error": error_msg,
            }
        finally:
            if self._owns_session:
                self.db.close()

    # ========================================================================
    # Split onboarding (used by the API background worker)
    # ========================================================================

    def register_repository(
        self,
        repo_url: str,
        branch: str = "main",
        visibility: str = "public",
        pat: Optional[str] = None,
        run_id: Optional[str] = None,
        repository_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create (or reuse) the repository record and its pipeline run record.

        This performs only short database work so that the API can return the
        repository and run identifiers immediately, while the clone and the
        pipeline execution happen in the background.

        Returns:
            Dictionary with the repository and pipeline run identifiers
        """
        if not self.user_id:
            return {
                "status": "FAILED",
                "stage": "VALIDATING",
                "error": "User ID required for repository onboarding",
            }

        validation_result = self._validate_repo_config(repo_url, branch, pat, visibility)
        if not validation_result["valid"]:
            return {
                "status": "FAILED",
                "stage": "VALIDATING",
                "error": validation_result["error"],
            }

        repo, already_registered = self._resolve_repository(
            repo_url, branch, visibility, pat, repository_id
        )
        run = self._create_pipeline_run(repo, run_id)

        return {
            "status": "COMPLETED",
            "stage": "PERSISTING",
            "repository_id": repo.id,
            "run_id": run.run_id,
            "clone_status": repo.clone_status,
            "message": (
                "Repository already registered"
                if already_registered
                else "Repository registered"
            ),
        }

    def execute_onboarding(
        self,
        repository_id: int,
        run_id: str,
        repo_url: str,
        branch: str = "main",
        pat: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Clone the registered repository and execute its pipeline run.

        This is the background half of the onboarding workflow: it uses the
        records that were already persisted by ``register_repository``.

        Returns:
            Dictionary with the operation result
        """
        try:
            repo = self.db.query(Repository).filter(
                Repository.id == repository_id
            ).first()
            if not repo:
                return {
                    "status": "FAILED",
                    "stage": "PERSISTING",
                    "error": "Repository record not found",
                }

            run = self.db.query(PipelineRun).filter(
                PipelineRun.run_id == run_id
            ).first()
            if not run:
                return {
                    "status": "FAILED",
                    "stage": "PERSISTING",
                    "error": "Pipeline run record not found",
                }

            self.repo = repo
            self.run = run

            try:
                self._clone_repository(repo, repo_url, branch, pat)
            except WorkspaceBusyError as busy_error:
                run.status = "failed"
                run.error_message = self._sanitize_error(str(busy_error))
                run.completed_at = _utcnow()
                self.db.commit()
                return {
                    "status": "FAILED",
                    "stage": "CLONING",
                    "repository_id": repo.id,
                    "run_id": run.run_id,
                    "error": run.error_message,
                }
            except Exception as clone_error:
                self._mark_clone_failed(repo)
                run.status = "failed"
                run.error_message = self._sanitize_error(str(clone_error))
                run.completed_at = _utcnow()
                self.db.commit()
                return {
                    "status": "FAILED",
                    "stage": "CLONING",
                    "repository_id": repo.id,
                    "run_id": run.run_id,
                    "error": run.error_message,
                }

            # The clone may have produced the workspace after the run record
            # was created, so keep the run pointing at the real directory.
            if repo.clone_path:
                run.orchestrator_root = repo.clone_path
                self.db.commit()

            exit_code = self.run_pipeline()

            return {
                "status": "COMPLETED" if exit_code == 0 else "FAILED",
                "stage": "EXECUTING",
                "repository_id": repo.id,
                "run_id": run.run_id,
                "pipeline_status": run.status,
                "pipeline_exit_code": exit_code,
                "clone_path": repo.clone_path,
                "commit_sha": repo.commit_sha,
                "error": None if exit_code == 0 else run.error_message,
            }
        finally:
            if self._owns_session:
                self.db.close()

    def _clone_repository(
        self,
        repo: Repository,
        repo_url: str,
        branch: str,
        pat: Optional[str],
    ) -> Dict[str, Any]:
        """
        Clone the repository (or reuse an existing clone) and persist the
        clone metadata on the repository record.
        """
        if self._can_reuse_clone(repo, branch):
            print(f"   ✓ Reusing existing clone: {repo.clone_path}")
            return {
                "clone_path": repo.clone_path,
                "clone_size_mb": float(repo.clone_size_mb or 0.0),
                "clone_duration_seconds": 0.0,
                "redis_cache_key": repo.redis_cache_key,
                "commit_sha": repo.commit_sha,
            }

        github_client = GitHubClient(personal_access_token=pat)
        clone_metadata = github_client.clone_repository(
            repo_url=repo_url,
            user_id=self.user_id,
            repo_id=repo.id,
            branch=branch,
            use_cache=False,  # Force fresh clone for onboarding
        )

        # Update repository with clone info
        repo.clone_path = clone_metadata["clone_path"]
        repo.clone_status = "cloned"
        repo.cloned_at = _utcnow()
        repo.clone_size_mb = clone_metadata["clone_size_mb"]
        repo.redis_cache_key = clone_metadata["redis_cache_key"]
        repo.commit_sha = clone_metadata.get("commit_sha")
        repo.branch = branch
        self.db.commit()
        self.db.refresh(repo)

        print(f"   ✓ Clone completed: {clone_metadata['clone_path']}")
        print(f"   ✓ Size: {float(clone_metadata['clone_size_mb']):.2f} MB")
        print(f"   ✓ Duration: {clone_metadata['clone_duration_seconds']:.1f}s")
        if repo.commit_sha:
            print(f"   ✓ Commit: {repo.commit_sha[:12]}")

        return clone_metadata

    # ========================================================================
    # Pipeline Execution
    # ========================================================================

    def execute_run(self, run_id: str) -> int:
        """
        Load a pipeline run from the database and execute it.

        This is the entry point used by the API background worker so that the
        persisted records are the single source of truth for execution.

        Args:
            run_id: Pipeline run identifier

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        self.run_id = run_id
        try:
            if not self.load_run_config():
                return 1
            return self.run_pipeline()
        finally:
            if self._owns_session:
                self.db.close()

    def load_run_config(self) -> bool:
        """
        Load pipeline run configuration from database.

        Returns:
            True if successful, False if run not found
        """
        # Load pipeline run
        self.run = self.db.query(PipelineRun).filter(
            PipelineRun.run_id == self.run_id
        ).first()

        if not self.run:
            print(f"❌ Pipeline run not found: {self.run_id}")
            return False

        # Load repository
        self.repo = self.db.query(Repository).filter(
            Repository.id == self.run.repository_id
        ).first()

        if not self.repo:
            print(f"❌ Repository not found: ID {self.run.repository_id}")
            return False

        print("✓ Loaded run configuration:")
        print(f"  Run ID: {self.run.run_id}")
        print(f"  Repository: {self.repo.name}")
        print(f"  Clone path: {self.run.orchestrator_root}")
        print(f"  Import roots: {self.run.import_roots}")
        print(f"  Output dir: {self.run.output_dir}")
        print(f"  Verbose: {self.run.verbose}")
        print(f"  Current status: {self.run.status}")

        return True

    def update_status(self, status: str, error_message: Optional[str] = None):
        """
        Update pipeline run status in database.

        Args:
            status: New status (pending, queued, running, completed, failed, cancelled)
            error_message: Optional error message for failed runs
        """
        if not self.run:
            return

        self.run.status = status

        # Set timestamps
        if status == "running" and not self.run.started_at:
            self.run.started_at = _utcnow()
            print(f"⏱️  Pipeline started at {self.run.started_at}")

        if status in TERMINAL_STATUSES:
            completed_at = _utcnow()
            self.run.completed_at = completed_at
            if self.run.started_at:
                duration = _elapsed_seconds(self.run.started_at, completed_at)
                self.run.duration_seconds = duration
                print(f"⏱️  Pipeline finished in {duration:.1f}s")

        if error_message:
            self.run.error_message = self._sanitize_error(error_message)

        self.db.commit()
        print(f"📝 Status updated: {status}")

    def update_results(
        self,
        bugs_detected: Optional[int] = None,
        bugs_fixed: Optional[int] = None,
        patches_generated: Optional[int] = None,
    ):
        """
        Update pipeline run results in database.

        Args:
            bugs_detected: Number of bugs detected
            bugs_fixed: Number of bugs successfully fixed
            patches_generated: Number of patches generated
        """
        if not self.run:
            return

        if bugs_detected is not None:
            self.run.bugs_detected = bugs_detected
            print(f"🐛 Bugs detected: {bugs_detected}")

        if bugs_fixed is not None:
            self.run.bugs_fixed = bugs_fixed
            print(f"✅ Bugs fixed: {bugs_fixed}")

        if patches_generated is not None:
            self.run.patches_generated = patches_generated
            print(f"📄 Patches generated: {patches_generated}")

        self.db.commit()

    def run_pipeline(self) -> int:
        """
        Execute the full pipeline for the loaded run and persist its outcome.

        Uses the standalone orchestrator for the actual pipeline execution.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        if not self.run or not self.repo:
            print("❌ Pipeline run configuration is not loaded")
            return 1

        try:
            print("=" * 60)
            print("  4o4PR Pipeline Orchestrator (Database Mode)")
            print("=" * 60)
            print()

            # Update status to running
            self.update_status("running")

            # Validate clone path exists
            if not self.run.orchestrator_root or not os.path.exists(self.run.orchestrator_root):
                raise PipelineExecutionError(
                    "Clone path does not exist. The repository must be cloned before the pipeline runs."
                )

            output_dir = self._resolve_output_dir(self.run)
            os.makedirs(output_dir, exist_ok=True)

            print(f"📂 Working directory: {self.run.orchestrator_root}")
            print(f"📊 Output directory: {output_dir}")
            print()

            # Parse import roots
            import_roots_str = self.run.import_roots or "src"
            import_roots = [r.strip() for r in import_roots_str.split(",") if r.strip()]

            # Load settings
            try:
                settings = load_settings(
                    config_path=Path(self.run.config_file) if self.run.config_file else None,
                    project_root=Path(self.run.orchestrator_root)
                )
            except Exception as e:
                print(f"Warning: Could not load settings: {e}")
                settings = None

            # Create standalone orchestrator and run pipeline
            standalone = StandaloneOrchestrator(
                project_root=Path(self.run.orchestrator_root),
                import_roots=import_roots,
                test_dirs=["tests", "test"],
                exclude_patterns=["**/__pycache__", "**/*.pyc", ".git/**"],
                output_dir=Path(output_dir),
                run_id=self.run.run_id,
                settings=settings
            )

            exit_code = standalone.run_all()

            # Collect results from pipeline output
            results = self._collect_results(output_dir)
            self.update_results(**results)

            if exit_code == 0:
                print()
                print("=" * 60)
                print("  Pipeline Complete!")
                print("=" * 60)
                print(f"✓ Bugs detected: {self.run.bugs_detected}")
                print(f"✓ Patches generated: {self.run.patches_generated}")
                print(f"✓ Bugs fixed: {self.run.bugs_fixed}")
                print()
                self.update_status("completed")
                return 0

            raise PipelineExecutionError("The pipeline reported a failure.")

        except KeyboardInterrupt:
            print("\n\n⚠️  Pipeline interrupted by user")
            self.update_status("cancelled", "Interrupted by user (Ctrl+C)")
            return 1

        except Exception as e:
            print(f"\n\n❌ Pipeline failed: {e}")
            import traceback
            self.run.error_traceback = self._sanitize_error(traceback.format_exc())
            self.update_status("failed", str(e))
            return 1

    # ========================================================================
    # Internals
    # ========================================================================

    def _validate_repo_config(
        self,
        repo_url: str,
        branch: str,
        pat: Optional[str],
        visibility: str,
    ) -> Dict[str, Any]:
        """Validate repository configuration."""
        # Validate URL
        is_valid_url, url_error = GitHubClient.validate_repo_url(repo_url)
        if not is_valid_url:
            return {"valid": False, "error": f"Invalid repository URL: {url_error}"}

        # Validate branch
        if not branch or not branch.strip():
            return {"valid": False, "error": "Branch name cannot be empty"}

        # Validate PAT for private repos
        if visibility == "private":
            if not pat:
                return {"valid": False, "error": "Personal access token required for private repositories"}
            is_valid_pat, pat_error = GitHubClient.validate_pat(pat)
            if not is_valid_pat:
                return {"valid": False, "error": f"Invalid PAT: {pat_error}"}

        return {"valid": True}

    def _find_existing_repository(self, repo_url: str) -> Optional[Repository]:
        """Check if repository already exists for this user."""
        # Parse repository identifier
        repo_identifier = GitHubClient._parse_repo_identifier(repo_url)

        # Query database
        existing = self.db.query(Repository).filter(
            Repository.owner_id == self.user_id,
            Repository.name == repo_identifier
        ).first()

        return existing

    def _resolve_repository(
        self,
        repo_url: str,
        branch: str,
        visibility: str,
        pat: Optional[str],
        repository_id: Optional[int] = None,
    ) -> Tuple[Repository, bool]:
        """
        Return the repository record for this request.

        The record is reused when it already exists so that a repository is
        never registered twice for the same user.

        Returns:
            Tuple of (repository, already_registered)
        """
        if repository_id:
            existing = self.db.query(Repository).filter(
                Repository.id == repository_id
            ).first()
            if existing:
                self._refresh_repository_metadata(existing, branch, visibility, pat)
                return existing, True

        existing = self._find_existing_repository(repo_url)
        if existing:
            self._refresh_repository_metadata(existing, branch, visibility, pat)
            return existing, True

        github_client = GitHubClient(personal_access_token=pat)
        return self._create_repository_record(repo_url, branch, visibility, pat, github_client), False

    def _refresh_repository_metadata(
        self,
        repo: Repository,
        branch: str,
        visibility: str,
        pat: Optional[str],
    ) -> None:
        """Refresh the mutable metadata of an existing repository record."""
        repo.branch = branch
        repo.is_private = (visibility == "private")

        if pat:
            # Never store a plaintext token: only the encrypted form is kept.
            github_client = GitHubClient(personal_access_token=pat)
            repo.encrypted_pat = github_client.encrypt_pat(pat)

        self.db.commit()

    def _can_reuse_clone(self, repo: Repository, branch: str) -> bool:
        """Whether an existing clone can be reused for this request."""
        return bool(
            repo.clone_status == "cloned"
            and repo.clone_path
            and os.path.isdir(repo.clone_path)
            and repo.branch == branch
        )

    def _mark_clone_failed(self, repo: Repository) -> None:
        """Record a failed clone attempt on the repository row."""
        try:
            repo.clone_status = "failed"
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _mark_run_failed(self, run_id: str, message: str) -> None:
        """Record a terminal failure on a pipeline run row."""
        try:
            run = self.db.query(PipelineRun).filter(
                PipelineRun.run_id == run_id
            ).first()
            if not run:
                return
            run.status = "failed"
            run.error_message = self._sanitize_error(message)
            completed_at = _utcnow()
            run.completed_at = completed_at
            if run.started_at:
                run.duration_seconds = _elapsed_seconds(run.started_at, completed_at)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _create_repository_record(
        self,
        repo_url: str,
        branch: str,
        visibility: str,
        pat: Optional[str],
        github_client: GitHubClient,
    ) -> Repository:
        """Create repository database record."""
        repo_identifier = GitHubClient._parse_repo_identifier(repo_url)

        # Try to fetch GitHub metadata (if PAT provided)
        repo_info = None
        if pat:
            try:
                repo_info = github_client.get_repo_info(repo_url)
            except Exception as e:
                print(f"   ⚠ Could not fetch GitHub metadata: {self._sanitize_error(str(e))}")

        # Create repository record
        new_repo = Repository(
            name=repo_identifier,
            url=repo_url,
            branch=branch,
            owner_id=self.user_id,
            clone_status="cloning",
            is_private=(visibility == "private")
        )

        # Add GitHub metadata if available
        if repo_info:
            new_repo.github_id = repo_info.get("github_id")
            new_repo.full_name = repo_info.get("full_name")
            new_repo.owner_login = repo_info.get("owner_login")
            new_repo.repo_name = repo_info.get("repo_name")
            new_repo.default_branch = repo_info.get("default_branch")
            new_repo.is_private = repo_info.get("is_private")
            new_repo.stars_count = repo_info.get("stars_count")
            new_repo.language = repo_info.get("language")
            new_repo.description = repo_info.get("description")

        # Encrypt and store PAT if provided
        if pat:
            new_repo.encrypted_pat = github_client.encrypt_pat(pat)

        self.db.add(new_repo)
        self.db.commit()
        self.db.refresh(new_repo)

        return new_repo

    def _create_pipeline_run(self, repo: Repository, run_id: Optional[str] = None) -> PipelineRun:
        """
        Create the pipeline run record for a repository.

        An already active run for the same repository is reused so that a
        duplicate submission cannot start a conflicting operation.
        """
        active_run = self.db.query(PipelineRun).filter(
            PipelineRun.repository_id == repo.id,
            PipelineRun.status.in_(ACTIVE_STATUSES),
        ).first()

        if active_run:
            print(f"   ⚠ Active pipeline run already exists: {active_run.run_id}")
            return active_run

        if not run_id:
            run_id = self.generate_run_id()

        output_dir = str(BACKEND_DIR / "runs" / run_id)

        new_run = PipelineRun(
            run_id=run_id,
            repository_id=repo.id,
            user_id=repo.owner_id,
            orchestrator_root=repo.clone_path or "",
            import_roots="src",  # Default import root; can be customized per run
            output_dir=output_dir,
            verbose=True,
            status="queued",
        )

        self.db.add(new_run)
        self.db.commit()
        self.db.refresh(new_run)

        return new_run

    @staticmethod
    def generate_run_id() -> str:
        """Generate a unique pipeline run identifier."""
        stamp = _utcnow().strftime("%Y%m%d_%H%M%S")
        return f"run_{stamp}_{uuid.uuid4().hex[:6]}"

    @staticmethod
    def _resolve_output_dir(run: PipelineRun) -> str:
        """Resolve the absolute output directory for a run."""
        output_dir = run.output_dir or str(BACKEND_DIR / "runs" / run.run_id)
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            output_path = BACKEND_DIR / output_path
        return str(output_path.resolve())

    def _collect_results(self, output_dir: str) -> Dict[str, int]:
        """
        Read the real results produced by the pipeline from its artifacts.
        """
        results = {
            "bugs_detected": 0,
            "bugs_fixed": 0,
            "patches_generated": 0,
        }

        output_path = Path(output_dir)

        bug_report = self._read_json(output_path / "detector" / "bug_report.json")
        if isinstance(bug_report, dict):
            summary = bug_report.get("summary") or {}
            try:
                results["bugs_detected"] = int(summary.get("bugs_detected", 0) or 0)
            except (TypeError, ValueError):
                results["bugs_detected"] = 0

        patches_dir = output_path / "patches"
        if patches_dir.is_dir():
            results["patches_generated"] = len(
                list(patches_dir.glob("*/patch_candidate.json"))
            )

        # The existing pipeline only produces patch candidates; it never
        # applies them, so no bug can honestly be reported as fixed.
        return results

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        """Read a JSON file, returning None when it is missing or invalid."""
        try:
            if not path.is_file():
                return None
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _sanitize_error(message: Any) -> str:
        """Strip credential-like material from an error message."""
        text = str(message)
        for pattern in _CREDENTIAL_PATTERNS:
            text = pattern.sub("[redacted]", text)
        return text


def execute_onboarding_task(
    user_id: int,
    repository_id: int,
    run_id: str,
    repo_url: str,
    branch: str = "main",
    pat: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Background task that clones a repository and executes its pipeline run.

    This is the worker used by the API so that the clone and the pipeline
    execution never block the request/event loop. Every failure is recorded on
    the pipeline run row so the frontend always observes the real state.

    Returns:
        Dictionary with the operation result
    """
    if not DB_AVAILABLE:
        return {
            "status": "FAILED",
            "stage": "VALIDATING",
            "error": "Database mode requires database dependencies",
        }
    
    orchestrator = OrchestratorDB(user_id=user_id)
    try:
        result = orchestrator.execute_onboarding(
            repository_id=repository_id,
            run_id=run_id,
            repo_url=repo_url,
            branch=branch,
            pat=pat,
        )
        return result
    except Exception as e:
        message = OrchestratorDB._sanitize_error(str(e))
        print(f"❌ Onboarding task failed: {message}")
        orchestrator._mark_run_failed(run_id, message)
        return {
            "status": "FAILED",
            "stage": "EXECUTING",
            "repository_id": repository_id,
            "run_id": run_id,
            "error": message,
        }


def main() -> int:
    """Main entry point."""
    load_local_env()
    
    parser = argparse.ArgumentParser(
        description="Combined orchestrator for 4o4PR pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standalone mode - run full pipeline on local repository
  python orchestrator.py --root /path/to/project
  
  # Standalone mode - with specific import root
  python orchestrator.py --root /path/to/project --import-root src
  
  # Standalone mode - skip certain steps
  python orchestrator.py --root /path/to/project --skip-patches
  
  # Database mode - run pipeline for existing run
  python orchestrator.py --run-id run_20261009_123456
  
  # Database mode - onboard (clone and register) a public repository
  python orchestrator.py --repository-onboarding \\
    --user-id 1 \\
    --repo-url https://github.com/facebook/react \\
    --branch main
  
  # Database mode - onboard a private repository
  python orchestrator.py --repository-onboarding \\
    --user-id 1 \\
    --repo-url https://github.com/myorg/private-repo \\
    --branch develop \\
    --pat ghp_xxxxxxxxxxxx \\
    --visibility private
        """
    )
    
    # Mode selection (database mode vs standalone mode)
    parser.add_argument(
        "--repository-onboarding",
        action="store_true",
        help="[DB mode] Run repository onboarding (clone and register)"
    )
    
    parser.add_argument(
        "--run-id",
        type=str,
        help="[DB mode] Pipeline run identifier (for full pipeline execution)"
    )
    
    # Standalone mode arguments
    parser.add_argument(
        "--root",
        type=Path,
        help="[Standalone mode] Project root directory to analyze"
    )
    parser.add_argument(
        "--import-root",
        type=str,
        action="append",
        dest="import_roots",
        default=[],
        help="[Standalone mode] Import root directory (default: 'src')"
    )
    parser.add_argument(
        "--test-dir",
        type=str,
        action="append",
        dest="test_dirs",
        default=[],
        help="[Standalone mode] Test directory name (default: 'tests', 'test')"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        action="append",
        dest="exclude_patterns",
        default=[],
        help="[Standalone mode] Pattern to exclude (default: **/__pycache__, **/*.pyc)"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="[Standalone mode] Output directory (default: ./runs/<run_id>)"
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
        help="[Standalone mode] Skip context building step"
    )
    parser.add_argument(
        "--skip-patches",
        action="store_true",
        help="[Standalone mode] Skip patch generation step"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="[Standalone mode] Skip validation step"
    )
    parser.add_argument(
        "--skip-explanation",
        action="store_true",
        help="[Standalone mode] Skip explanation generation"
    )
    parser.add_argument(
        "--skip-pr",
        action="store_true",
        help="[Standalone mode] Skip PR preparation"
    )
    parser.add_argument(
        "--stop-after",
        type=str,
        default=None,
        metavar="STAGE",
        help="[Standalone mode] Stop after completing STAGE (indexer, detector, grouper, context, patches)"
    )
    
    # Database mode arguments
    parser.add_argument(
        "--user-id",
        type=int,
        help="[DB mode] User ID (required for repository onboarding)"
    )
    parser.add_argument(
        "--repo-url",
        type=str,
        help="[DB mode] Repository URL (for onboarding)"
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="[DB mode] Branch name (default: main)"
    )
    parser.add_argument(
        "--pat",
        type=str,
        help="[DB mode] Personal access token (for private repositories)"
    )
    parser.add_argument(
        "--visibility",
        type=str,
        choices=["public", "private"],
        default="public",
        help="[DB mode] Repository visibility (default: public)"
    )
    
    # Common arguments
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Determine mode: Database mode or Standalone mode
    is_db_mode = args.repository_onboarding or args.run_id
    is_standalone_mode = args.root is not None
    
    if is_db_mode and is_standalone_mode:
        print("❌ Error: Cannot use both database mode and standalone mode simultaneously")
        parser.print_help()
        return 1
    
    if not is_db_mode and not is_standalone_mode:
        parser.print_help()
        print("\n❌ Error: Must specify either --root (standalone) or --run-id/--repository-onboarding (database)")
        return 1
    
    # ========================================================================
    # DATABASE MODE
    # ========================================================================
    if is_db_mode:
        if not DB_AVAILABLE:
            print("❌ Error: Database mode requires database dependencies")
            print("Install dependencies: pip install -r requirements.txt")
            return 1
        
        # Repository onboarding mode
        if args.repository_onboarding:
            if not args.user_id:
                print("❌ Error: --user-id required for repository onboarding")
                return 1

            if not args.repo_url:
                print("❌ Error: --repo-url required for repository onboarding")
                return 1

            orchestrator = OrchestratorDB(user_id=args.user_id)

            result = orchestrator.onboard_repository(
                repo_url=args.repo_url,
                branch=args.branch,
                pat=args.pat,
                visibility=args.visibility
            )

            if result["status"] == "COMPLETED":
                print(f"✓ Repository ID: {result['repository_id']}")
                print(f"✓ Pipeline run: {result.get('run_id')}")
                return 0
            else:
                print(f"✗ Error: {result.get('error', 'Unknown error')}")
                return 1

        # Pipeline execution mode
        elif args.run_id:
            orchestrator = OrchestratorDB(run_id=args.run_id)

            # Load configuration from database
            if not orchestrator.load_run_config():
                return 1

            print()

            # Run pipeline
            return orchestrator.run_pipeline()
    
    # ========================================================================
    # STANDALONE MODE
    # ========================================================================
    else:
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
            run_id_arg = getattr(args, 'run_id', None) or make_run_id(now_utc)
            out_dir = BACKEND_DIR / "runs" / run_id_arg
        
        # Create orchestrator
        orchestrator = StandaloneOrchestrator(
            project_root=args.root,
            import_roots=import_roots,
            test_dirs=test_dirs,
            exclude_patterns=exclude_patterns,
            output_dir=out_dir,
            run_id=None,  # Will be auto-generated
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
