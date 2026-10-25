"""Integration tests for the repository onboarding API.

The frontend talks to the backend through these endpoints, so the tests
verify the contract end to end: request validation, the persisted repository
and pipeline run records, the identifiers handed to the background worker and
the absence of credentials in every response.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_db
from app.main import app
from app.models.pipeline_run import PipelineRun
from app.models.repository import Repository
from app.utils.security import get_current_active_user

REPO_URL = "https://github.com/example/widgets"
PAT = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


class RecordingWorker:
    """Captures the arguments the API hands to the background worker."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "COMPLETED"}


@pytest.fixture()
def worker(monkeypatch):
    """Replace the background worker so that no real clone is attempted."""
    recorder = RecordingWorker()
    monkeypatch.setattr("app.api.repositories.execute_onboarding_task", recorder)
    return recorder


@pytest.fixture()
def client(session_factory, sample_user, worker):
    """A test client bound to the isolated database and an authenticated user."""

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_active_user] = override_current_user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_active_user, None)


@pytest.fixture()
def anonymous_client(session_factory):
    """A test client without a valid authentication."""
    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestOnboardEndpoint:
    """POST /api/repositories/onboard is the single onboarding entry point."""

    def test_public_repository_is_accepted(self, client, db_session):
        response = client.post("/api/repositories/onboard", json={
            "url": REPO_URL,
            "branch": "main",
            "visibility": "public",
        })

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["repository_id"]
        assert body["run_id"].startswith("run_")
        assert body["repository"]["name"] == "example/widgets"

        repo = db_session.query(Repository).one()
        run = db_session.query(PipelineRun).one()
        assert repo.id == body["repository_id"]
        assert run.run_id == body["run_id"]
        assert run.repository_id == repo.id
        assert run.status == "queued"

    def test_private_repository_with_token_is_accepted(self, client, db_session, monkeypatch):
        from cryptography.fernet import Fernet
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

        response = client.post("/api/repositories/onboard", json={
            "url": REPO_URL,
            "branch": "main",
            "visibility": "private",
            "personal_access_token": PAT,
        })

        assert response.status_code == 202
        repo = db_session.query(Repository).one()
        assert repo.is_private is True
        assert repo.encrypted_pat
        assert PAT not in repo.encrypted_pat

    def test_response_never_contains_the_token(self, client):
        response = client.post("/api/repositories/onboard", json={
            "url": REPO_URL,
            "branch": "main",
            "visibility": "private",
            "personal_access_token": PAT,
        })

        assert PAT not in response.text
        assert "encrypted_pat" not in response.text

    def test_background_worker_receives_the_correct_identifiers(self, client, worker):
        response = client.post("/api/repositories/onboard", json={
            "url": REPO_URL,
            "branch": "develop",
            "visibility": "public",
        })

        body = response.json()
        assert len(worker.calls) == 1
        args = worker.calls[0][0]
        assert args[1] == body["repository_id"]
        assert args[2] == body["run_id"]
        assert args[3] == REPO_URL
        assert args[4] == "develop"

    def test_invalid_url_is_rejected(self, client):
        response = client.post("/api/repositories/onboard", json={
            "url": "https://gitlab.com/example/widgets",
            "branch": "main",
        })

        assert response.status_code == 400
        assert "github.com" in response.json()["detail"]

    def test_private_repository_without_token_is_rejected(self, client):
        response = client.post("/api/repositories/onboard", json={
            "url": REPO_URL,
            "branch": "main",
            "visibility": "private",
        })

        assert response.status_code == 400
        assert "token" in response.json()["detail"].lower()

    def test_malformed_token_is_rejected(self, client):
        response = client.post("/api/repositories/onboard", json={
            "url": REPO_URL,
            "branch": "main",
            "visibility": "private",
            "personal_access_token": "short",
        })

        assert response.status_code == 400
        assert "token" in response.json()["detail"].lower()

    def test_duplicate_submission_is_rejected(self, client):
        first = client.post("/api/repositories/onboard", json={
            "url": REPO_URL, "branch": "main", "visibility": "public",
        })
        assert first.status_code == 202

        second = client.post("/api/repositories/onboard", json={
            "url": REPO_URL, "branch": "main", "visibility": "public",
        })

        assert second.status_code == 409
        assert first.json()["run_id"] in second.json()["detail"]

    def test_unauthenticated_request_is_rejected(self, anonymous_client):
        response = anonymous_client.post("/api/repositories/onboard", json={
            "url": REPO_URL, "branch": "main", "visibility": "public",
        })

        assert response.status_code == 401


class TestPipelineRunStatus:
    """The frontend reads the real execution state from these endpoints."""

    def test_run_state_is_readable(self, client):
        onboarded = client.post("/api/repositories/onboard", json={
            "url": REPO_URL, "branch": "main", "visibility": "public",
        }).json()
        run_id = onboarded["run_id"]

        response = client.get(f"/api/pipeline-runs/{run_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == run_id
        assert body["status"] == "queued"
        assert body["repository_id"] == onboarded["repository_id"]

    def test_unknown_run_returns_404(self, client):
        response = client.get("/api/pipeline-runs/run_does_not_exist")
        assert response.status_code == 404

    def test_trigger_rejects_a_second_active_run(self, client, db_session):
        onboarded = client.post("/api/repositories/onboard", json={
            "url": REPO_URL, "branch": "main", "visibility": "public",
        }).json()

        response = client.post("/api/pipeline-runs/trigger", json={
            "repository_id": onboarded["repository_id"],
        })

        assert response.status_code == 409
        assert onboarded["run_id"] in response.json()["detail"]

    def test_trigger_starts_the_background_worker(self, client, db_session, monkeypatch):
        from app.api import pipeline_runs as pipeline_runs_api
        recorder = RecordingWorker()
        monkeypatch.setattr(pipeline_runs_api, "execute_onboarding_task", recorder)

        onboarded = client.post("/api/repositories/onboard", json={
            "url": REPO_URL, "branch": "main", "visibility": "public",
        }).json()

        # The first run has to reach a terminal state before a new one is allowed.
        previous = db_session.query(PipelineRun).one()
        previous.status = "completed"
        db_session.commit()

        response = client.post("/api/pipeline-runs/trigger", json={
            "repository_id": onboarded["repository_id"],
        })

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"
        assert body["run_id"] != onboarded["run_id"]
        assert recorder.calls
