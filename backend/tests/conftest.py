"""Shared pytest fixtures for the 4o4PR backend test suite.

The tests run against an isolated in-memory SQLite database that uses the
real ORM models, so the persistence behaviour is exercised for real. Only the
external GitHub operations are mocked.
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.repository import Repository  # noqa: E402
from app.models.pipeline_run import PipelineRun  # noqa: E402
from app.tools.github_client import GitHubClient  # noqa: E402


@pytest.fixture(autouse=True)
def github_offline(monkeypatch):
    """Never talk to github.com from a test."""
    monkeypatch.setattr(GitHubClient, "_connect", lambda self: None)


@pytest.fixture()
def test_engine():
    """An isolated database that uses the production schema."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def session_factory(test_engine):
    """Session factory bound to the isolated database."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture()
def db_session(session_factory):
    """A session on the isolated database."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sample_user(db_session):
    """An active user that owns the repositories under test."""
    user = User(
        email="tester@example.com",
        hashed_password="not-a-real-hash",
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
