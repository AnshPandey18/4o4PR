"""Unit tests for the credential-safe clone execution in GitHubClient."""

import subprocess
from pathlib import Path

import pytest

import app.tools.github_client as github_client
from app.tools.github_client import GitHubClient


@pytest.fixture()
def no_redis(monkeypatch):
    monkeypatch.setattr(
        github_client, "get_redis_client",
        lambda: type("NoRedis", (), {
            "is_connected": lambda self: False,
            "get_clone_metadata": lambda self, u, r: None,
        })(),
    )


@pytest.fixture()
def clone_env(monkeypatch, tmp_path, no_redis):
    monkeypatch.setenv("CLONE_BASE_PATH", str(tmp_path / "repos"))
    monkeypatch.setattr(GitHubClient, "_verify_checkout",
                        lambda self, clone_path, branch: ("c" * 40, branch or "main"))
    monkeypatch.setattr(GitHubClient, "_get_directory_size_mb", lambda self, path: 1.0)
    return tmp_path


def _record_run(monkeypatch, returncode=0, stderr="", create_clone=True):
    calls = []

    def _run(command, cwd=None, env=None, capture_output=None, text=None,
             encoding=None, errors=None, timeout=None):
        calls.append({"command": command, "env": env, "timeout": timeout})
        if create_clone:
            destination = Path(command[-1])
            (destination / ".git").mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(command, returncode, stdout="", stderr=stderr)

    monkeypatch.setattr(github_client.subprocess, "run", _run)
    return calls


class TestCloneCommand:
    def test_clone_uses_a_bounded_shallow_clone(self, clone_env, monkeypatch):
        calls = _record_run(monkeypatch)

        GitHubClient().clone_repository(
            "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
        )

        command = calls[0]["command"]
        assert command[:3] == ["git", "clone", "--depth"]
        assert "--single-branch" in command
        assert command[command.index("--branch") + 1] == "main"
        assert "--" in command
        assert calls[0]["timeout"] == GitHubClient().clone_timeout

    def test_clone_command_carries_no_credentials(self, clone_env, monkeypatch):
        calls = _record_run(monkeypatch)
        client = GitHubClient(personal_access_token="ghp_secretvalue1234567890")

        client.clone_repository(
            "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
        )

        command = calls[0]["command"]
        assert not any("ghp_secretvalue1234567890" in part for part in command)
        assert all("ghp_secretvalue1234567890" not in part for part in command)
        assert "secretvalue" not in " ".join(command)

    def test_private_clone_authenticates_through_the_environment_only(self, clone_env, monkeypatch):
        calls = _record_run(monkeypatch)
        client = GitHubClient(personal_access_token="ghp_secretvalue1234567890")

        client.clone_repository(
            "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
        )

        env = calls[0]["env"]
        assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
        assert env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
        assert "ghp_secretvalue1234567890" not in " ".join(env.values())
        assert env["GIT_TERMINAL_PROMPT"] == "0"

    def test_public_clone_sets_no_authorization_header(self, clone_env, monkeypatch):
        calls = _record_run(monkeypatch)

        GitHubClient().clone_repository(
            "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
        )

        assert "GIT_CONFIG_VALUE_0" not in calls[0]["env"]


class TestCloneFailures:
    def test_clone_timeout_is_reported_and_cleans_up(self, clone_env, monkeypatch):
        def _run(command, cwd=None, env=None, capture_output=None, text=None,
                 encoding=None, errors=None, timeout=None):
            destination = Path(command[-1])
            destination.mkdir(parents=True, exist_ok=True)
            raise subprocess.TimeoutExpired(command, timeout)

        monkeypatch.setattr(github_client.subprocess, "run", _run)

        with pytest.raises(ValueError) as excinfo:
            GitHubClient().clone_repository(
                "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
            )

        assert "timed out" in str(excinfo.value).lower()
        assert not (clone_env / "repos" / "1" / "example_widgets").exists()

    def test_missing_branch_is_reported(self, clone_env, monkeypatch):
        _record_run(
            monkeypatch,
            returncode=128,
            stderr="fatal: Remote branch nope not found in upstream origin",
        )

        with pytest.raises(ValueError) as excinfo:
            GitHubClient().clone_repository(
                "https://github.com/example/widgets", user_id=1, repo_id=1, branch="nope"
            )

        assert "Branch not found" in str(excinfo.value)
        assert not (clone_env / "repos" / "1" / "example_widgets").exists()

    def test_access_denied_is_reported_without_credentials(self, clone_env, monkeypatch):
        _record_run(monkeypatch, returncode=128, stderr="fatal: Authentication failed")

        with pytest.raises(ValueError) as excinfo:
            GitHubClient(personal_access_token="ghp_secretvalue1234567890").clone_repository(
                "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
            )

        message = str(excinfo.value)
        assert "authentication failed" in message.lower()
        assert "ghp_secretvalue1234567890" not in message

    def test_missing_git_executable_is_reported(self, clone_env, monkeypatch):
        def _run(command, cwd=None, env=None, capture_output=None, text=None,
                 encoding=None, errors=None, timeout=None):
            raise FileNotFoundError("git")

        monkeypatch.setattr(github_client.subprocess, "run", _run)

        with pytest.raises(ValueError) as excinfo:
            GitHubClient().clone_repository(
                "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
            )

        assert "git" in str(excinfo.value).lower()
