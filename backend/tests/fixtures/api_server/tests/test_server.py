"""Tests for API server."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import APIServer
from services import UserService
from config import SERVER_PORT, ADMIN_ROLE


def test_server_initialization():
    """Test server initializes correctly."""
    server = APIServer()
    assert server.running == False
    assert server.port == SERVER_PORT


def test_server_start():
    """Test server start sequence.
    
    Calls _initialize_database and _initialize_routes.
    """
    server = APIServer()
    server.start()
    
    assert server.running == True
    assert server.db_connected == True
    assert '/auth/login' in server.routes


def test_server_stop():
    """Test server stop."""
    server = APIServer()
    server.start()
    assert server.running == True
    
    server.stop()
    assert server.running == False


def test_server_login_flow():
    """Test complete login flow."""
    server = APIServer()
    server.start()
    
    # Create user
    server.user_service.create_user("admin", "AdminPass123", "admin@example.com")
    
    # Login
    response = server._handle_login("admin", "AdminPass123")
    assert 'token' in response
    assert response['token'] is not None
