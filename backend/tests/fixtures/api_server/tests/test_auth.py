"""Tests for authentication module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auth import _hash_password, validate_password, generate_token, InvalidTokenException
from config import SECRET_KEY


def test_hash_password_deterministic():
    """Test that password hashing is deterministic."""
    password = "mypassword"
    hash1 = _hash_password(password)
    hash2 = _hash_password(password)
    assert hash1 == hash2


def test_validate_password_correct():
    """Test password validation with correct password."""
    password = "mypassword"
    hashed = _hash_password(password)
    assert validate_password(password, hashed) == True


def test_validate_password_incorrect():
    """Test password validation with incorrect password."""
    password = "mypassword"
    hashed = _hash_password(password)
    assert validate_password("wrongpassword", hashed) == False


def test_generate_token():
    """Test token generation."""
    token = generate_token("user123")
    assert "user123" in token


def test_token_is_unique():
    """Test that tokens include some identifier."""
    token1 = generate_token("user1")
    token2 = generate_token("user2")
    assert token1 != token2
