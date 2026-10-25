"""Tests for email validator module."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from email_validator import validate_email, extract_domain, extract_username, _is_valid_domain
from constants import VALID_DOMAINS, MAX_EMAIL_LENGTH


def test_validate_email_valid():
    """Test validation of valid emails."""
    assert validate_email("user@gmail.com") == True
    assert validate_email("test@yahoo.com") == True
    assert validate_email("admin@example.com") == True


def test_validate_email_invalid_domain():
    """Test rejection of emails with invalid domains."""
    # This should FAIL because _is_valid_domain always returns True
    assert validate_email("user@invalid.com") == False
    assert validate_email("test@nowhere.org") == False
    assert validate_email("admin@badomain.net") == False


def test_validate_email_invalid_format():
    """Test rejection of invalid email formats."""
    assert validate_email("") == False
    assert validate_email("notanemail") == False
    assert validate_email("@domain.com") == False
    assert validate_email("user@") == False


def test_validate_email_too_long():
    """Test rejection of emails exceeding MAX_EMAIL_LENGTH."""
    long_email = "a" * (MAX_EMAIL_LENGTH - 9) + "@gmail.com"
    assert validate_email(long_email) == False


def test_extract_domain():
    """Test domain extraction from emails."""
    assert extract_domain("user@gmail.com") == "gmail.com"
    assert extract_domain("test@example.org") == "example.org"
    assert extract_domain("notanemail") == ""


def test_extract_username():
    """Test username extraction from emails."""
    assert extract_username("user@gmail.com") == "user"
    assert extract_username("admin@example.org") == "admin"
    assert extract_username("notanemail") == ""


def test_is_valid_domain():
    """Test domain validation."""
    # This should FAIL because _is_valid_domain always returns True
    assert _is_valid_domain("gmail.com") == True
    assert _is_valid_domain("invalid.com") == False
    assert _is_valid_domain("random.org") == False
