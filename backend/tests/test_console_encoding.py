"""Regression tests for console encoding on legacy Windows code pages.

Progress markers such as "✓" cannot be encoded by cp1252. Printing them used
to raise UnicodeEncodeError inside the clone stage, which turned a successful
clone into a persisted failure.
"""

import contextlib
import io
import subprocess
import sys
from pathlib import Path

import pytest

from app.tools.console import configure_console, safe_print
from app.tools.github_client import GitHubClient


@contextlib.contextmanager
def narrow_stdout(encoding: str = "ascii"):
    """Temporarily replace stdout with a stream that rejects non-ASCII characters."""

    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding=encoding, errors="strict")
    original = sys.stdout
    sys.stdout = stream
    try:
        yield buffer
    finally:
        sys.stdout = original


class TestConsoleEncoding:
    def test_configure_console_allows_non_ascii_output(self):
        with narrow_stdout() as buffer:
            configure_console()
            print("✓ clone completed")
            sys.stdout.flush()
            assert b"clone completed" in buffer.getvalue()

    def test_configure_console_tolerates_a_stream_without_reconfigure(self):
        class Frozen:
            encoding = "ascii"

            def write(self, _text):
                return 0

            def flush(self):
                pass

        original = sys.stdout
        sys.stdout = Frozen()
        try:
            configure_console()
        finally:
            sys.stdout = original

    def test_safe_print_never_raises_on_a_narrow_encoder(self):
        with narrow_stdout() as buffer:
            safe_print("✗ boom")
            sys.stdout.flush()
            assert b"boom" in buffer.getvalue()


class TestCloneUnderNarrowConsole:
    """The clone stage must succeed even when the console cannot encode glyphs."""

    @pytest.fixture()
    def stubbed_clone(self, monkeypatch, tmp_path):
        import app.tools.github_client as github_client

        def _run(command, cwd=None, env=None, capture_output=None, text=None,
                 encoding=None, errors=None, timeout=None):
            destination = github_client.Path(command[-1])
            (destination / ".git").mkdir(parents=True, exist_ok=True)
            (destination / "README.md").write_text("hello", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(github_client.subprocess, "run", _run)
        monkeypatch.setattr(
            github_client.GitHubClient,
            "_verify_checkout",
            lambda self, clone_path, branch: ("b" * 40, branch or "main"),
        )
        monkeypatch.setattr(
            github_client.GitHubClient, "_get_directory_size_mb", lambda self, path: 0.5
        )
        monkeypatch.setattr(
            github_client, "get_redis_client",
            lambda: type("NoRedis", (), {
                "is_connected": lambda self: False,
                "get_clone_metadata": lambda self, u, r: None,
            })(),
        )
        monkeypatch.setenv("CLONE_BASE_PATH", str(tmp_path / "repos"))

    def test_clone_succeeds_when_stdout_cannot_encode_glyphs(self, stubbed_clone):
        with narrow_stdout() as buffer:
            configure_console()
            client = GitHubClient()

            metadata = client.clone_repository(
                "https://github.com/example/widgets", user_id=1, repo_id=1, branch="main"
            )

            sys.stdout.flush()
            assert b"Clone completed" in buffer.getvalue()

        assert metadata["clone_status"] == "cloned"
        assert metadata["commit_sha"] == "b" * 40
