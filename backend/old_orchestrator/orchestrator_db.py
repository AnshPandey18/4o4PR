"""Database-integrated orchestrator for the 4o4PR analysis-to-patch pipeline.

This orchestrator reads configuration from the database instead of environment
variables. It owns the complete repository-onboarding workflow:

1. Validate the GitHub repository configuration
2. Clone the requested repository and branch (without persisting credentials)
3. Persist the repository metadata in the ``repositories`` table
4. Persist the corresponding pipeline run in the ``pipeline_runs`` table
5. Execute the existing pipeline through ``orchestrator.py`` / ``run_pipeline.py``
6. Persist the actual execution states, results and failures

Usage:
    python orchestrator_db.py --run-id run_20261009_123456
    python orchestrator_db.py --repository-onboarding --repo-url https://github.com/owner/repo --branch main [--pat TOKEN]
"""

from __future__ import annotations

import os
import re
import sys
import json
import argparse
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend to path for imports
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.pipeline_run import PipelineRun
from app.models.repository import Repository
from app.tools.console import configure_console
from app.tools.github_client import GitHubClient, WorkspaceBusyError


# Progress markers are not encodable on legacy Windows code pages; without this
# a successful clone can be reported as a failure.
configure_console()


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


class OrchestratorDB:
    """Database-integrated orchestrator."""

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

        The existing pipeline (``orchestrator.py`` -> ``run_pipeline.py``) is
        executed as a controlled subprocess so that it cannot block the API
        event loop and can be bounded by a timeout.

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

            exit_code, failure_message = self._execute_pipeline_process(output_dir)

            # Persist the real results produced by the pipeline, even when a
            # later stage failed.
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

            raise PipelineExecutionError(
                failure_message or "The pipeline reported a failure."
            )

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
            import_roots=os.getenv("ORCHESTRATOR_IMPORT_ROOTS", "src"),
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

    def _execute_pipeline_process(self, output_dir: str) -> Tuple[int, Optional[str]]:
        """
        Execute the existing pipeline as a controlled subprocess.

        The existing ``orchestrator.py`` entry point is reused so that the
        pipeline behaviour (detection, RCA and patch generation) is preserved.

        Returns:
            Tuple of (exit_code, sanitized_failure_message)
        """
        env = os.environ.copy()
        env["ORCHESTRATOR_ROOT"] = str(self.run.orchestrator_root)
        env["ORCHESTRATOR_IMPORT_ROOTS"] = self.run.import_roots or "src"
        env["ORCHESTRATOR_OUTPUT_DIR"] = output_dir
        env["ORCHESTRATOR_RUN_ID"] = self.run.run_id
        env["ORCHESTRATOR_VERBOSE"] = "1" if self.run.verbose else "0"
        if self.run.config_file:
            env["ORCHESTRATOR_CONFIG"] = str(self.run.config_file)

        command = [sys.executable, str(BACKEND_DIR / "orchestrator.py")]

        print(f"▶ Executing pipeline: {' '.join(command)}")
        print(f"  Root: {self.run.orchestrator_root}")
        print(f"  Output: {output_dir}")
        print()

        try:
            completed = subprocess.run(
                command,
                cwd=str(BACKEND_DIR),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return 1, (
                f"Pipeline execution timed out after {PIPELINE_TIMEOUT_SECONDS} seconds."
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        if stdout.strip():
            print(stdout[-4000:])
        if stderr.strip():
            print(stderr[-2000:])

        if completed.returncode == 0:
            return 0, None

        return completed.returncode, self._extract_failure_message(stdout, stderr)

    @staticmethod
    def _extract_failure_message(stdout: str, stderr: str) -> str:
        """Derive a short, sanitized failure message from the pipeline output."""
        lines = [
            line.strip()
            for line in (stderr or stdout).splitlines()
            if line.strip()
        ]

        for line in reversed(lines):
            lowered = line.lower()
            if "error:" in lowered or "failed" in lowered or "traceback" in lowered:
                return OrchestratorDB._sanitize_error(line[:500])

        if lines:
            return OrchestratorDB._sanitize_error(lines[-1][:500])

        return "The pipeline reported a failure."

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
    parser = argparse.ArgumentParser(
        description="4o4PR Pipeline Orchestrator (Database Mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline for a specific run_id
  python orchestrator_db.py --run-id run_20261009_123456
  
  # Onboard (clone and register) a public repository
  python orchestrator_db.py --repository-onboarding \\
    --user-id 1 \\
    --repo-url https://github.com/facebook/react \\
    --branch main
  
  # Onboard a private repository
  python orchestrator_db.py --repository-onboarding \\
    --user-id 1 \\
    --repo-url https://github.com/myorg/private-repo \\
    --branch develop \\
    --pat ghp_xxxxxxxxxxxx \\
    --visibility private
        """
    )

    # Mode selection
    parser.add_argument(
        "--repository-onboarding",
        action="store_true",
        help="Run repository onboarding (clone and register)"
    )

    # Pipeline execution mode
    parser.add_argument(
        "--run-id",
        type=str,
        help="Pipeline run identifier (for full pipeline execution)"
    )

    # Repository onboarding mode
    parser.add_argument(
        "--user-id",
        type=int,
        help="User ID (required for repository onboarding)"
    )

    parser.add_argument(
        "--repo-url",
        type=str,
        help="Repository URL (for onboarding)"
    )

    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="Branch name (default: main)"
    )

    parser.add_argument(
        "--pat",
        type=str,
        help="Personal access token (for private repositories)"
    )

    parser.add_argument(
        "--visibility",
        type=str,
        choices=["public", "private"],
        default="public",
        help="Repository visibility (default: public)"
    )

    args = parser.parse_args()

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

    else:
        parser.print_help()
        print("\n❌ Error: Must specify either --repository-onboarding or --run-id")
        return 1


if __name__ == "__main__":
    sys.exit(main())
