"""Configuration and constants for API server."""

# Security
SECRET_KEY = "dev-key-not-for-production"
TOKEN_EXPIRY = 3600  # seconds
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 900  # 15 minutes

# Database
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "api_db"
DB_USER = "postgres"
DB_PASSWORD = "password"

# Validation
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32
VALID_EMAIL_DOMAINS = ["example.com", "test.com"]

# Server
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
DEBUG = True

# Constants
ADMIN_ROLE = "admin"
USER_ROLE = "user"
GUEST_ROLE = "guest"
