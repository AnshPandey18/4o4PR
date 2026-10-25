"""Tests for business logic services."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services import UserService, SessionManager
from config import MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH, VALID_EMAIL_DOMAINS
from auth import InvalidTokenException


def test_create_user_valid():
    """Test creating a valid user."""
    service = UserService()
    result = service.create_user("testuser", "Password123", "test@example.com")
    assert result == True
    assert "testuser" in service.users


def test_create_user_validates_email():
    """Test that user creation validates email."""
    service = UserService()
    result = service.create_user("testuser", "Password123", "test@invalid.com")
    assert result == False


def test_create_user_validates_password():
    """Test password validation on creation."""
    service = UserService()
    result = service.create_user("testuser", "short", "test@example.com")
    assert result == False


def test_authenticate_valid():
    """Test authentication with valid credentials."""
    service = UserService()
    service.create_user("testuser", "Password123", "test@example.com")
    
    token = service.authenticate("testuser", "Password123")
    assert token is not None
    assert "testuser" in token


def test_authenticate_invalid_user():
    """Test authentication with invalid username."""
    service = UserService()
    with assert_raises(InvalidTokenException):
        service.authenticate("nonexistent", "Password123")


def test_authenticate_invalid_password():
    """Test authentication with invalid password."""
    service = UserService()
    service.create_user("testuser", "Password123", "test@example.com")
    
    with assert_raises(InvalidTokenException):
        service.authenticate("testuser", "WrongPassword")


def test_update_user_password():
    """Test updating user password."""
    service = UserService()
    service.create_user("testuser", "OldPassword", "test@example.com")
    
    result = service.update_user("testuser", "NewPassword123")
    assert result == True


def test_session_manager():
    """Test session manager integration.
    
    Calls user_service.authenticate through session manager.
    """
    user_service = UserService()
    session_manager = SessionManager(user_service)
    
    user_service.create_user("testuser", "Password123", "test@example.com")
    
    token = session_manager.start_session("testuser", "Password123")
    assert token is not None


# Helper for testing exceptions
def assert_raises(exception_type):
    """Simple context manager for exception testing."""
    class RaisesContext:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Expected {exception_type} but no exception was raised")
            return issubclass(exc_type, exception_type)
    return RaisesContext()
