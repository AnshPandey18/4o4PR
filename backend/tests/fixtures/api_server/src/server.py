"""API Server implementation."""

from config import SERVER_HOST, SERVER_PORT, DEBUG
from services import UserService, SessionManager
from auth import authenticate, generate_token


class APIServer:
    """Main API server class."""
    
    def __init__(self):
        """Initialize server and services."""
        self.host = SERVER_HOST
        self.port = SERVER_PORT
        self.running = False
        
        # Initialize services
        self.user_service = UserService()
        self.session_manager = SessionManager(self.user_service)
    
    def _initialize_database(self):
        """Initialize database connection."""
        self.db_connected = True
    
    def _initialize_routes(self):
        """Initialize API routes."""
        self.routes = {
            '/auth/login': self._handle_login,
            '/auth/logout': self._handle_logout,
            '/users': self._handle_users,
        }
    
    def _handle_login(self, username: str, password: str):
        """Handle login request.
        
        Calls session_manager.start_session.
        """
        # Calls session_manager.start_session
        token = self.session_manager.start_session(username, password)
        return {'token': token}
    
    @authenticate
    def _handle_logout(self, token: str):
        """Handle logout request."""
        return {'message': 'logged out'}
    
    @authenticate
    def _handle_users(self, token: str):
        """Handle users request."""
        return {'users': list(self.user_service.users.keys())}
    
    def start(self):
        """Start the server.
        
        Calls initialization chain: _initialize_database, _initialize_routes.
        """
        if self.running:
            return
        
        # Initialize in order
        self._initialize_database()
        self._initialize_routes()
        
        self.running = True
        
        if DEBUG:
            print(f"Server running on {self.host}:{self.port}")
    
    def stop(self):
        """Stop the server."""
        self.running = False
