import os

import pytest

from app.config import get_settings
from app.tools.claude_client import GeminiClient


def test_settings_loads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings = get_settings()
    assert settings["gemini_api_key"] == "test-key"


def test_gemini_client_requires_api_key():
    with pytest.raises(ValueError):
        GeminiClient(api_key="")


def test_gemini_client_builds_terminal_prompt():
    client = GeminiClient(api_key="test-key")
    prompt = client.build_prompt("List the steps to debug a failing test.")
    assert "List the steps to debug a failing test." in prompt
    assert "You are a helpful coding assistant" in prompt
