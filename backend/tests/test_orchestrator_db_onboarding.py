"""Tests for the database-backed orchestrator (repository onboarding + execution).

The persistence behaviour is exercised against an isolated database using the
real ORM models. Only the external GitHub operations are mocked.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import orchestrator
from orchestrator import OrchestratorDB, _elapsed_seconds, execute_onboarding_task
from app.models.pipeline_run import PipelineRun
from app.models.repository import Repository
from app.tools.github_client import GitHubClient, WorkspaceBusyError

REPO_URL = "https://github.com/example/widgets"
PAT = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


# ============================================================================
# Helpers
# ============================================================================

def clone_metadata(clone_path: Path) -> dict:
    """Deterministic clone metadata as produced by the GitHub client."""
    return {
        "user_id": 1,
        "repo_id": 1,
        "clone_path": str(clone_path),
        "clone_status": "cloned",
        "cloned_at": "2026-10-24T10:00:00",
        "clone_size_mb": 1.25,
        "clone_duration_seconds": 0.5,
        "branch": "main",
        "commit_sha": "a" * 40,
        "redis_cache_key": "clone:1:1",
    }


@pytest.fixture()
def orchestrator(db_session):
    """An orchestrator bound to the isolated database."""
    return OrchestratorDB(user_id=1, db=db_session)


@pytest.fixture()
def clone_dir(tmp_path):
    """A directory that stands in for a cloned repository."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture()
def fake_clone(monkeypatch, clone_dir):
    """Replace the real git clone with a deterministic stub."""
    calls = []

    def _clone(self, repo_url, user_id, repo_id, branch=None, use_cache=True):
        calls.append({
            "repo_url": repo_url,
            "user_id": user_id,
            "repo_id": repo_id,
            "branch": branch,
            "use_cache": use_cache,
            "pat": self.pat,
        })
        return clone_metadata(clone_dir)

    monkeypatch.setattr(GitHubClient, "clone_repository", _clone)
    return calls


@pytest.fixture()
def fake_pipeline(monkeypatch, tmp_path):
    """Replace the pipeline subprocess with a stub that writes real artifacts."""
    calls = []

    def _run(command, cwd=None, env=None, capture_output=None, text=None,
             encoding=None, errors=None, timeout=None):
        calls.append({"command": command, "cwd": cwd, "env": env, "timeout": timeout})

        output_dir = Path(env["ORCHESTRATOR_OUTPUT_DIR"])
        (output_dir / "detector").mkdir(parents=True, exist_ok=True)
        (output_dir / "detector" / "bug_report.json").write_text(
            json.dumps({"summary": {"bugs_detected": 3}}), encoding="utf-8"
        )
        patch_dir = output_dir / "patches" / "bug_001"
        patch_dir.mkdir(parents=True, exist_ok=True)
        (patch_dir / "patch_candidate.json").write_text("{}", encoding="utf-8")

        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout="pipeline finished", stderr=""
        )

    monkeypatch.setattr(orchestrator.subprocess, "run", _run)
    return calls


# ============================================================================
# Configuration validation
# ============================================================================

class TestRepositoryValidation:
    """The orchestrator must refuse unusable configurations."""

    def test_accepts_public_github_url(self):
        is_valid, error = GitHubClient.validate_repo_url(REPO_URL)
        assert is_valid is True
        assert error is None

    def test_rejects_unsupported_host(self):
        is_valid, error = GitHubClient.validate_repo_url("https://gitlab.com/a/b")
        assert is_valid is False
        assert "github.com" in error

    def test_rejects_lookalike_host(self):
        is_valid, error = GitHubClient.validate_repo_url("https://github.com.evil.test/a/b")
        assert is_valid is False

    def test_rejects_path_traversal_identifier(self):
        is_valid, error = GitHubClient.validate_repo_url("https://github.com/../etc/passwd")
        assert is_valid is False

    def test_rejects_empty_url(self):
        is_valid, error = GitHubClient.validate_repo_url("   ")
        assert is_valid is False

    def test_rejects_empty_branch(self, orchestrator):
        result = orchestrator.register_repository(repo_url=REPO_URL, branch="  ")
        assert result["status"] == "FAILED"
        assert result["stage"] == "VALIDATING"
        assert "Branch" in result["error"]

    def test_private_repository_requires_token(self, orchestrator):
        result = orchestrator.register_repository(
            repo_url=REPO_URL, branch="main", visibility="private"
        )
        assert result["status"] == "FAILED"
        assert "token" in result["error"].lower()

    def test_rejects_malformed_token(self, orchestrator):
        result = orchestrator.register_repository(
            repo_url=REPO_URL, branch="main", visibility="private", pat="not-a-token"
        )
        assert result["status"] == "FAILED"
        assert "PAT" in result["error"]

    def test_requires_user_id(self, db_session):
        orchestrator = OrchestratorDB(user_id=None, db=db_session)
        result = orchestrator.register_repository(repo_url=REPO_URL)
        assert result["status"] == "FAILED"
        assert "User ID" in result["error"]


# ============================================================================
# Database persistence
# ============================================================================

class TestRepositoryPersistence:
    """Both the repository and the pipeline run must be persisted."""

    def test_register_repository_persists_both_records(self, orchestrator, db_session):
        result = orchestrator.register_repository(repo_url=REPO_URL, branch="main")

        assert result["status"] == "COMPLETED"
        assert result["repository_id"]
        assert result["run_id"].startswith("run_")

        repo = db_session.query(Repository).filter(
            Repository.id == result["repository_id"]
        ).one()
        assert repo.name == "example/widgets"
        assert repo.url == REPO_URL
        assert repo.owner_id == 1
        assert repo.branch == "main"

        run = db_session.query(PipelineRun).filter(
            PipelineRun.run_id == result["run_id"]
        ).one()
        assert run.repository_id == repo.id
        assert run.user_id == 1
        assert run.status == "queued"
        assert run.output_dir.endswith(result["run_id"])

    def test_pipeline_run_is_linked_to_the_repository(self, orchestrator, db_session):
        result = orchestrator.register_repository(repo_url=REPO_URL)
        run = db_session.query(PipelineRun).one()
        assert run.repository.pipeline_runs == [run]

    def test_existing_repository_is_reused(self, orchestrator, db_session):
        first = orchestrator.register_repository(repo_url=REPO_URL)
        second = orchestrator.register_repository(repo_url=REPO_URL)

        assert second["repository_id"] == first["repository_id"]
        assert db_session.query(Repository).count() == 1
        # The first run is still active, so it is reused instead of duplicated.
        assert second["run_id"] == first["run_id"]
        assert db_session.query(PipelineRun).count() == 1

    def test_active_run_is_reused_to_block_duplicate_submissions(self, orchestrator):
        first = orchestrator.register_repository(repo_url=REPO_URL)
        second = orchestrator.register_repository(repo_url=REPO_URL)

        assert second["run_id"] == first["run_id"]

    def test_finished_run_allows_a_new_run(self, orchestrator, db_session):
        first = orchestrator.register_repository(repo_url=REPO_URL)
        run = db_session.query(PipelineRun).filter(
            PipelineRun.run_id == first["run_id"]
        ).one()
        run.status = "completed"
        db_session.commit()

        second = orchestrator.register_repository(repo_url=REPO_URL)
        assert second["run_id"] != first["run_id"]
        assert db_session.query(PipelineRun).count() == 2

    def test_private_token_is_stored_encrypted(self, orchestrator, db_session, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _fernet_key())
        result = orchestrator.register_repository(
            repo_url=REPO_URL, branch="main", visibility="private", pat=PAT
        )

        repo = db_session.query(Repository).one()
        assert repo.encrypted_pat
        assert PAT not in repo.encrypted_pat
        assert repo.is_private is True
        assert result["status"] == "COMPLETED"

    def test_public_repository_does_not_store_a_token(self, orchestrator, db_session):
        orchestrator.register_repository(repo_url=REPO_URL)
        repo = db_session.query(Repository).one()
        assert repo.encrypted_pat is None


def _fernet_key() -> str:
    """A throwaway Fernet key for the tests."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


# ============================================================================
# Cloning
# ============================================================================

class TestCloning:
    """The clone must be isolated, verified and persisted."""

    def test_clone_metadata_is_persisted(self, orchestrator, db_session, fake_clone):
        result = orchestrator.register_repository(repo_url=REPO_URL)
        orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        repo = db_session.query(Repository).one()
        assert repo.clone_status == "cloned"
        assert repo.clone_path
        assert repo.commit_sha == "a" * 40
        assert float(repo.clone_size_mb) == 1.25
        assert repo.cloned_at is not None

    def test_clone_receives_the_requested_branch(self, orchestrator, fake_clone):
        result = orchestrator.register_repository(repo_url=REPO_URL, branch="develop")
        orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="develop",
        )
        assert fake_clone[0]["branch"] == "develop"

    def test_existing_clone_is_reused(self, orchestrator, db_session, clone_dir, monkeypatch):
        result = orchestrator.register_repository(repo_url=REPO_URL)
        repo = db_session.query(Repository).one()
        repo.clone_status = "cloned"
        repo.clone_path = str(clone_dir)
        repo.branch = "main"
        db_session.commit()

        def _fail(*args, **kwargs):
            raise AssertionError("the repository should not be cloned again")

        monkeypatch.setattr(GitHubClient, "clone_repository", _fail)
        orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )
        assert repo.clone_status == "cloned"

    def test_clone_failure_marks_repository_and_run_failed(self, orchestrator, db_session, monkeypatch):
        def _fail(self, *args, **kwargs):
            raise ValueError("GitHub authentication failed. Check the access token.")

        monkeypatch.setattr(GitHubClient, "clone_repository", _fail)

        result = orchestrator.register_repository(repo_url=REPO_URL)
        outcome = orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        assert outcome["status"] == "FAILED"
        assert outcome["stage"] == "CLONING"
        assert "authentication failed" in outcome["error"].lower()

        repo = db_session.query(Repository).one()
        run = db_session.query(PipelineRun).one()
        assert repo.clone_status == "failed"
        assert run.status == "failed"
        assert run.completed_at is not None
        assert run.error_message

    def test_workspace_collision_marks_the_run_failed(self, orchestrator, db_session, monkeypatch):
        def _busy(self, *args, **kwargs):
            raise WorkspaceBusyError(
                "Clone workspace is busy; another operation is in progress"
            )

        monkeypatch.setattr(GitHubClient, "clone_repository", _busy)

        result = orchestrator.register_repository(repo_url=REPO_URL)
        outcome = orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        assert outcome["status"] == "FAILED"
        run = db_session.query(PipelineRun).one()
        assert run.status == "failed"
        assert "busy" in run.error_message.lower()


# ============================================================================
# Pipeline execution
# ============================================================================

class TestPipelineExecution:
    """The real pipeline must be executed and its real outcome persisted."""

    def _registered_run(self, orchestrator, db_session, tmp_path):
        result = orchestrator.register_repository(repo_url=REPO_URL)
        run = db_session.query(PipelineRun).one()
        run.output_dir = str(tmp_path / "output")
        db_session.commit()
        return result, run

    def test_pipeline_reuses_the_existing_entrypoint(self, orchestrator, db_session, tmp_path, fake_clone, fake_pipeline):
        result, run = self._registered_run(orchestrator, db_session, tmp_path)
        orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        assert len(fake_pipeline) == 1
        call = fake_pipeline[0]
        assert call["command"] == [sys.executable, str(BACKEND_DIR / "orchestrator.py")]
        assert call["env"]["ORCHESTRATOR_ROOT"]
        assert call["env"]["ORCHESTRATOR_RUN_ID"] == result["run_id"]
        assert call["env"]["ORCHESTRATOR_IMPORT_ROOTS"]
        assert call["timeout"] == orchestrator.PIPELINE_TIMEOUT_SECONDS

    def test_pipeline_persists_the_real_results(self, orchestrator, db_session, tmp_path, fake_clone, fake_pipeline):
        result, run = self._registered_run(orchestrator, db_session, tmp_path)
        orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        db_session.refresh(run)
        assert run.status == "completed"
        assert run.bugs_detected == 3
        assert run.patches_generated == 1
        # The existing pipeline only produces patch candidates, it never
        # applies them, so nothing may be reported as fixed.
        assert run.bugs_fixed == 0
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.duration_seconds is not None
        assert run.error_message is None

    def test_pipeline_failure_marks_the_run_failed(self, orchestrator, db_session, tmp_path, fake_clone, monkeypatch):
        result, run = self._registered_run(orchestrator, db_session, tmp_path)

        def _fail(command, **kwargs):
            return subprocess.CompletedProcess(
                args=command, returncode=1,
                stdout="", stderr="ERROR: the detector crashed\n",
            )

        monkeypatch.setattr(orchestrator.subprocess, "run", _fail)

        orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        db_session.refresh(run)
        assert run.status == "failed"
        assert run.completed_at is not None
        assert "detector crashed" in run.error_message

    def test_pipeline_timeout_marks_the_run_failed(self, orchestrator, db_session, tmp_path, fake_clone, monkeypatch):
        result, run = self._registered_run(orchestrator, db_session, tmp_path)

        def _timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout", 1))

        monkeypatch.setattr(orchestrator.subprocess, "run", _timeout)

        orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        db_session.refresh(run)
        assert run.status == "failed"
        assert "timed out" in run.error_message.lower()

    def test_missing_clone_path_marks_the_run_failed(self, orchestrator, db_session, tmp_path, monkeypatch):
        result, run = self._registered_run(orchestrator, db_session, tmp_path)
        run.orchestrator_root = str(tmp_path / "does-not-exist")
        db_session.commit()

        def _fail(*args, **kwargs):
            raise AssertionError("the pipeline must not start without a clone")

        monkeypatch.setattr(GitHubClient, "clone_repository", _fail)
        monkeypatch.setattr(orchestrator.subprocess, "run", _fail)

        outcome = orchestrator.execute_onboarding(
            repository_id=result["repository_id"],
            run_id=result["run_id"],
            repo_url=REPO_URL,
            branch="main",
        )

        assert outcome["status"] == "FAILED"
        db_session.refresh(run)
        assert run.status == "failed"

    def test_execute_run_uses_the_persisted_configuration(self, orchestrator, db_session, tmp_path, fake_pipeline):
        result = orchestrator.register_repository(repo_url=REPO_URL)
        run = db_session.query(PipelineRun).one()
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        run.orchestrator_root = str(workspace)
        run.output_dir = str(tmp_path / "output")
        db_session.commit()

        exit_code = orchestrator.execute_run(result["run_id"])

        assert exit_code == 0
        assert fake_pipeline[0]["env"]["ORCHESTRATOR_ROOT"] == str(workspace)
        db_session.refresh(run)
        assert run.status == "completed"


# ============================================================================
# Credential safety
# ============================================================================

class TestCredentialSafety:
    """No credential may leak into the database, the logs or a message."""

    def test_sanitize_error_redacts_github_tokens(self):
        message = "clone failed for ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        sanitized = OrchestratorDB._sanitize_error(message)
        assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in sanitized
        assert "[redacted]" in sanitized

    def test_sanitize_error_redacts_fine_grained_tokens(self):
        token = "github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz"
        sanitized = OrchestratorDB._sanitize_error(f"token {token} rejected")
        assert token not in sanitized

    def test_sanitize_error_redacts_credentials_in_a_url(self):
        sanitized = OrchestratorDB._sanitize_error(
            "fatal: https://user:secret@github.com/example/widgets failed"
        )
        assert "secret" not in sanitized

    def test_clone_url_never_carries_credentials(self):
        client = GitHubClient(personal_access_token=PAT)
        clone_url = client._build_clone_url(REPO_URL)
        assert PAT not in clone_url
        assert "@" not in clone_url
        assert clone_url == "https://github.com/example/widgets.git"

    def test_git_environment_carries_the_token_in_a_header(self):
        client = GitHubClient(personal_access_token=PAT)
        env = client._build_git_env()

        assert env["GIT_TERMINAL_PROMPT"] == "0"
        assert env["GIT_CONFIG_COUNT"] == "1"
        assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
        assert "Authorization: Basic " in env["GIT_CONFIG_VALUE_0"]
        # The raw token must not be part of the environment value.
        assert PAT not in env["GIT_CONFIG_VALUE_0"]

    def test_public_clone_environment_has_no_authorization_header(self):
        env = GitHubClient()._build_git_env()
        assert "GIT_CONFIG_COUNT" not in env
        assert env["GIT_TERMINAL_PROMPT"] == "0"

    def test_stored_token_can_be_decrypted_but_is_never_plaintext(self, db_session, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _fernet_key())
        orchestrator = OrchestratorDB(user_id=1, db=db_session)
        orchestrator.register_repository(
            repo_url=REPO_URL, visibility="private", pat=PAT
        )

        repo = db_session.query(Repository).one()
        assert PAT not in repo.encrypted_pat
        assert GitHubClient().decrypt_pat(repo.encrypted_pat) == PAT


# ============================================================================
# Background worker
# ============================================================================

class TestBackgroundWorker:
    """The background task must always leave a truthful run record behind."""

    def test_worker_marks_the_run_failed_on_an_unexpected_error(self, db_session, monkeypatch):
        monkeypatch.setattr(orchestrator, "SessionLocal", lambda: db_session)

        def _boom(self, **kwargs):
            raise RuntimeError("boom ghp_abcdefghijklmnopqrstuvwxyz0123456789")

        monkeypatch.setattr(OrchestratorDB, "execute_onboarding", _boom)

        result = execute_onboarding_task(
            user_id=1, repository_id=1, run_id="run_missing", repo_url=REPO_URL
        )

        assert result["status"] == "FAILED"
        assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in result["error"]


# ============================================================================
# Command line interface
# ============================================================================

class TestCLIInterface:
    """The orchestrator keeps its command line entry point."""

    def test_cli_onboarding_success(self, monkeypatch, capsys):
        orchestrator = MockOrchestrator(
            {"status": "COMPLETED", "repository_id": 7, "run_id": "run_123"}
        )
        monkeypatch.setattr(orchestrator, "OrchestratorDB", lambda **kw: orchestrator_obj)
        monkeypatch.setattr(
            sys, "argv",
            ["orchestrator.py", "--repository-onboarding", "--user-id", "1",
             "--repo-url", REPO_URL, "--branch", "main"],
        )

        exit_code = orchestrator.main()

        assert exit_code == 0
        assert orchestrator.calls[0]["repo_url"] == REPO_URL
        assert orchestrator.calls[0]["branch"] == "main"

    def test_cli_onboarding_failure(self, monkeypatch):
        orchestrator = MockOrchestrator(
            {"status": "FAILED", "error": "Clone timeout"}
        )
        monkeypatch.setattr(orchestrator, "OrchestratorDB", lambda **kw: orchestrator_obj)
        monkeypatch.setattr(
            sys, "argv",
            ["orchestrator.py", "--repository-onboarding", "--user-id", "1",
             "--repo-url", REPO_URL],
        )

        exit_code = orchestrator.main()

        assert exit_code == 1

    def test_cli_requires_a_user_id(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv",
            ["orchestrator.py", "--repository-onboarding", "--repo-url", REPO_URL],
        )

        exit_code = orchestrator.main()

        assert exit_code == 1


class TestRunTimestamps:
    """Terminal status transitions must survive timezone-aware DB values.

    PostgreSQL stores these columns as TIMESTAMP WITH TIME ZONE, so a reloaded
    ``started_at`` is aware while ``datetime.utcnow()`` is naive. Subtracting
    the two used to raise and leave runs stuck in ``running``.
    """

    def test_elapsed_seconds_accepts_mixed_timezone_awareness(self):
        now = datetime.now(timezone.utc)

        assert _elapsed_seconds(now - timedelta(seconds=10), now) == 10
        assert _elapsed_seconds(
            (now - timedelta(seconds=10)).replace(tzinfo=None), now
        ) == 10
        assert _elapsed_seconds(None, now) == 0

    def test_terminal_status_records_duration_for_an_aware_started_at(
        self, orchestrator, db_session
    ):
        result = orchestrator.register_repository(repo_url=REPO_URL)
        orchestrator.run = db_session.query(PipelineRun).filter(
            PipelineRun.run_id == result["run_id"]
        ).one()
        orchestrator.run.status = "running"
        orchestrator.run.started_at = datetime.now(timezone.utc) - timedelta(seconds=42)

        orchestrator.update_status("failed", "boom")

        run = db_session.query(PipelineRun).filter(
            PipelineRun.run_id == result["run_id"]
        ).one()
        assert run.status == "failed"
        assert run.completed_at is not None
        assert run.duration_seconds >= 42


class MockOrchestrator:
    """Minimal stand-in for the orchestrator used by the CLI tests."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def onboard_repository(self, **kwargs):
        self.calls.append(kwargs)
        return self.result
