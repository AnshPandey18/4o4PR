import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from analysis.root_cause_agent import OpenAICompatibleClient, RootCauseAnalysisError


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body


def test_complete_sends_bearer_token(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(
            json.dumps(
                {"choices": [{"message": {"content": '{"ok": true}'}}]}
            ).encode("utf-8")
        )

    monkeypatch.setattr("analysis.root_cause_agent.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        base_url="http://localhost:20128/v1",
        api_key="test-key",
        model="auto/coding",
        timeout=7,
    )

    assert client.complete("prompt") == '{"ok": true}'
    request, timeout = requests[0]
    assert request.get_header("Authorization") == "Bearer test-key"
    assert request.full_url == "http://localhost:20128/v1/chat/completions"
    assert timeout == 7


def test_complete_reports_http_error_body(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"error":"invalid api key"}'),
        )

    monkeypatch.setattr("analysis.root_cause_agent.urlopen", fake_urlopen)

    with pytest.raises(
        RootCauseAnalysisError,
        match=r"HTTP 401 Unauthorized: \{\"error\":\"invalid api key\"\}",
    ):
        OpenAICompatibleClient(api_key="test-key").complete("prompt")


def test_complete_reports_empty_non_json_response(monkeypatch):
    monkeypatch.setattr(
        "analysis.root_cause_agent.urlopen",
        lambda request, timeout: FakeResponse(b"", headers={"Content-Type": "text/plain"}),
    )

    with pytest.raises(
        RootCauseAnalysisError,
        match=r"HTTP 200, Content-Type text/plain: <empty response body>",
    ):
        OpenAICompatibleClient(api_key="test-key").complete("prompt")
