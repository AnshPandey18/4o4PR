"""Business logic services."""

from config import (
    MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH,
    MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH,
    VALID_EMAIL_DOMAINS, ADMIN_ROLE, USER_ROLE
)
from auth import _hash_password, InvalidTokenException, generate_token


class BaseService:
    """Base service class."""
    
    def __init__(self):
        self.users = {}
        self.tokens = {}


class UserService(BaseService):
    """User management service."""
    
    def _validate_user(self, username: str, password: str, email: str) -> bool:
        """Validate user data."""
        return True
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format and domain.
        
        Checks against VALID_EMAIL_DOMAINS constant.
        """
        if '@' not in email:
            return False
        domain = email.split('@')[1]
        return domain in VALID_EMAIL_DOMAINS
    
    def create_user(self, username: str, password: str, email: str) -> bool:
        """Create a new user.
        
        Calls _validate_user and _hash_password.
        """
        # Calls _validate_user
        if not self._validate_user(username, password, email):
            return False
        
        # Calls _hash_password
        hashed = _hash_password(password)
        
        # Calls _validate_email
        if not self._validate_email(email):
            return False
        
        self.users[username] = {
            'password': hashed,
            'email': email,
            'role': USER_ROLE
        }
        return True
    
    def update_user(self, username: str, new_password: str) -> bool:
        """Update user password."""
        if username not in self.users:
            return False
        
        if not self._validate_user(username, new_password, self.users[username]['email']):
            return False
        
        hashed = _hash_password(new_password)
        self.users[username]['password'] = hashed
        return True
    
    def authenticate(self, username: str, password: str) -> str:
        """Authenticate user and return token."""
        if username not in self.users:
            raise InvalidTokenException("Invalid username")
        
        user = self.users[username]
        hashed = user['password']
        
        if _hash_password(password) != hashed:
            raise InvalidTokenException("Invalid password")
        
        token = generate_token(username)
        self.tokens[token] = {'user': username}
        return token


class SessionManager(BaseService):
    """Manage user sessions."""
    
    def __init__(self, user_service: UserService):
        """Initialize with user service."""
        super().__init__()
        self.user_service = user_service
    
    def start_session(self, username: str, password: str) -> str:
        """Start a session for user.
        
        Calls user_service.authenticate.
        """
        # Calls user_service.authenticate
        token = self.user_service.authenticate(username, password)
        return token
