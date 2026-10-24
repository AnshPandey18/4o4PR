"""Authentication and authorization utilities."""

import hashlib
from config import SECRET_KEY, TOKEN_EXPIRY


class AuthException(Exception):
    """Base authentication exception."""
    pass


class InvalidTokenException(AuthException):
    """Token is invalid or expired."""
    pass


def _hash_password(password: str) -> str:
    """Hash a password using SHA256."""
    return hashlib.sha256((password + SECRET_KEY).encode()).hexdigest()


def validate_password(password: str, hashed: str) -> bool:
    """Validate a password against hash.
    
    Calls _hash_password to validate.
    """
    return _hash_password(password) == hashed


def generate_token(user_id: str) -> str:
    """Generate an authentication token."""
    return f"token_{user_id}_{SECRET_KEY}"


def authenticate(func):
    """Decorator to require authentication."""
    def wrapper(*args, **kwargs):
        token = kwargs.get('token')
        if token:
            return func(*args, **kwargs)
        raise InvalidTokenException("Missing token")
    return wrapper
