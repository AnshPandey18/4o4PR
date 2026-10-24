"""Comprehensive tests for indexer features (Schema 1.2).

Tests cover:
1. attr_types extraction from self.x = Cls() and annotated parameters
2. Call resolution through self.x.m() and var.x.m() chains
3. super().m() and inherited self.m() resolution
4. Builtin exceptions and methods recognition
5. parameter_call and decorated_by edges
6. Signature parsing with defaults, *args, **kwargs, keyword-only, return annotations
7. Metrics: char_count == len(segment) and approx_tokens == max(1, char_count // 4)
8. Schema 1.2 fields: children, bases, bases_unresolved, attr_types
9. validate_index.py on every fixture
"""

import json
import pytest
import tempfile
from pathlib import Path

from indexer.index import RepoIndexer
from indexer.validate_index import validate_index


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure."""
    return tmp_path


def write_files(root: Path, files: dict):
    """Write multiple files to project root."""
    for path_str, content in files.items():
        file_path = root / path_str
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)


def index_project(root: Path, import_roots=["src"]):
    """Index a project and return the index data."""
    indexer = RepoIndexer(
        project_root=root,
        import_roots=import_roots,
        test_dirs=["tests"],
        exclude_patterns=[],
        schema_version="1.2"
    )
    return indexer.index().to_dict()


class TestAttrTypes:
    """Test attr_types extraction."""
    
    def test_attr_types_from_assignment(self, temp_project):
        """Test attr_types from self.x = ClassName() pattern."""
        write_files(temp_project, {
            "src/models.py": """
class UserService:
    pass

class SessionManager:
    pass

class APIServer:
    def __init__(self):
        self.user_service = UserService()
        self.session_manager = SessionManager()
""",
        })
        
        index = index_project(temp_project)
        api_server = index['symbols']['src/models.py::APIServer']
        
        assert api_server['attr_types'] == {
            'user_service': 'src/models.py::UserService',
            'session_manager': 'src/models.py::SessionManager'
        }
    
    def test_attr_types_from_annotated_param(self, temp_project):
        """Test attr_types from annotated parameters."""
        write_files(temp_project, {
            "src/models.py": """
class Database:
    pass

class APIServer:
    def __init__(self, db: Database):
        self.database = db
""",
        })
        
        index = index_project(temp_project)
        api_server = index['symbols']['src/models.py::APIServer']
        
        assert 'database' in api_server['attr_types']
        assert api_server['attr_types']['database'] == 'src/models.py::Database'


class TestCallResolution:
    """Test call resolution through attr chains."""
    
    def test_self_attr_method_resolution(self, temp_project):
        """Test self.x.m() resolution via attr_types."""
        write_files(temp_project, {
            "src/app.py": """
class Service:
    def process(self):
        pass

class App:
    def __init__(self):
        self.service = Service()
    
    def run(self):
        self.service.process()
""",
        })
        
        index = index_project(temp_project)
        run_method = index['symbols']['src/app.py::App.run']
        
        # Should resolve self.service.process() to Service.process
        callees = index['call_graph']['callees'].get('src/app.py::App.run', [])
        assert 'src/app.py::Service.process' in callees
        assert run_method['unresolved_calls'] == 0
    
    def test_var_attr_method_resolution(self, temp_project):
        """Test var.x.m() resolution via type_map + attr_types."""
        write_files(temp_project, {
            "src/app.py": """
class UserService:
    def create_user(self, name):
        pass

class APIServer:
    def __init__(self):
        self.user_service = UserService()

def test_flow():
    server = APIServer()
    server.user_service.create_user("admin")
""",
        })
        
        index = index_project(temp_project)
        test_func = index['symbols']['src/app.py::test_flow']
        
        # Should resolve server.user_service.create_user() via type_map + attr_types
        callees = index['call_graph']['callees'].get('src/app.py::test_flow', [])
        assert 'src/app.py::UserService.create_user' in callees
        assert test_func['unresolved_calls'] == 0


class TestInheritance:
    """Test super() and inherited method resolution."""
    
    def test_super_method_resolution(self, temp_project):
        """Test super().m() resolution."""
        write_files(temp_project, {
            "src/models.py": """
class BaseService:
    def initialize(self):
        pass

class UserService(BaseService):
    def setup(self):
        super().initialize()
""",
        })
        
        index = index_project(temp_project)
        setup_method = index['symbols']['src/models.py::UserService.setup']
        
        # Should resolve super().initialize() to BaseService.initialize
        callees = index['call_graph']['callees'].get('src/models.py::UserService.setup', [])
        assert 'src/models.py::BaseService.initialize' in callees
        assert setup_method['unresolved_calls'] == 0
    
    def test_inherited_self_method(self, temp_project):
        """Test inherited self.m() resolution."""
        write_files(temp_project, {
            "src/models.py": """
class BaseService:
    def log(self, message):
        pass

class UserService(BaseService):
    def create_user(self, name):
        self.log(f"Creating user: {name}")
""",
        })
        
        index = index_project(temp_project)
        create_method = index['symbols']['src/models.py::UserService.create_user']
        
        # Should resolve self.log() to inherited BaseService.log
        callees = index['call_graph']['callees'].get('src/models.py::UserService.create_user', [])
        assert 'src/models.py::BaseService.log' in callees
        assert create_method['unresolved_calls'] == 0


class TestBuiltins:
    """Test builtin exceptions and methods recognition."""
    
    def test_builtin_exceptions(self, temp_project):
        """Test builtin exceptions are recognized."""
        write_files(temp_project, {
            "src/app.py": """
def process(data):
    if not data:
        raise ValueError("Data is empty")
    try:
        result = int(data)
    except TypeError:
        raise RuntimeError("Invalid data")
    return result
""",
        })
        
        index = index_project(temp_project)
        func = index['symbols']['src/app.py::process']
        
        # Builtin exceptions and functions should be in builtin_calls
        assert 'ValueError' in func['builtin_calls']
        assert 'int' in func['builtin_calls']
        assert 'RuntimeError' in func['builtin_calls']
    
    def test_builtin_methods(self, temp_project):
        """Test builtin methods are recognized."""
        write_files(temp_project, {
            "src/app.py": """
def process(items):
    items.append("new")
    text = "hello"
    return text.upper()
""",
        })
        
        index = index_project(temp_project)
        func = index['symbols']['src/app.py::process']
        
        # Builtin methods should not create unresolved calls
        # They should be recognized as builtins
        assert func['unresolved_calls'] == 0


class TestEdges:
    """Test parameter_call and decorated_by edges."""
    
    def test_parameter_call_edge(self, temp_project):
        """Test parameter_call reason for function-as-parameter."""
        write_files(temp_project, {
            "src/app.py": """
def authenticate(username, password, callback):
    if username == "admin":
        callback(username)

def on_success(user):
    pass

def login():
    authenticate("admin", "pass", on_success)
""",
        })
        
        index = index_project(temp_project)
        auth_func = index['symbols']['src/app.py::authenticate']
        
        # callback() should be marked as parameter_call
        unresolved = [u for u in auth_func['unresolved'] if u['name'] == 'callback']
        assert len(unresolved) == 1
        assert unresolved[0]['reason'] == 'parameter_call'
    
    def test_decorated_by_edge(self, temp_project):
        """Test decorated_by edges in call graph."""
        write_files(temp_project, {
            "src/app.py": """
def requires_auth(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@requires_auth
def protected_endpoint():
    pass
""",
        })
        
        index = index_project(temp_project)
        endpoint = index['symbols']['src/app.py::protected_endpoint']
        
        # Should have decorator_targets populated
        assert 'src/app.py::requires_auth' in endpoint['decorator_targets']


class TestSignatures:
    """Test signature parsing with various forms."""
    
    def test_signature_with_defaults(self, temp_project):
        """Test signature with default values."""
        write_files(temp_project, {
            "src/app.py": """
def connect(host="localhost", port=8080, timeout=30):
    pass
""",
        })
        
        index = index_project(temp_project)
        func = index['symbols']['src/app.py::connect']
        
        assert 'localhost' in func['signature']
        assert '8080' in func['signature']
        assert '30' in func['signature']
    
    def test_signature_with_args_kwargs(self, temp_project):
        """Test signature with *args and **kwargs."""
        write_files(temp_project, {
            "src/app.py": """
def process(x, y, *args, **kwargs):
    pass
""",
        })
        
        index = index_project(temp_project)
        func = index['symbols']['src/app.py::process']
        
        assert '*args' in func['signature']
        assert '**kwargs' in func['signature']
    
    def test_signature_keyword_only(self, temp_project):
        """Test signature with keyword-only params."""
        write_files(temp_project, {
            "src/app.py": """
def create_user(name, *, admin=False, verified=False):
    pass
""",
        })
        
        index = index_project(temp_project)
        func = index['symbols']['src/app.py::create_user']
        
        # Keyword-only params should be in signature
        assert 'admin' in func['signature']
        assert 'verified' in func['signature']
    
    def test_signature_return_annotation(self, temp_project):
        """Test signature with return annotation."""
        write_files(temp_project, {
            "src/app.py": """
def get_count() -> int:
    return 42
""",
        })
        
        index = index_project(temp_project)
        func = index['symbols']['src/app.py::get_count']
        
        assert '-> int' in func['signature']


class TestMetrics:
    """Test line_count, char_count, and approx_tokens metrics."""
    
    def test_char_count_equals_len(self, temp_project):
        """Test char_count == len(source_segment)."""
        write_files(temp_project, {
            "src/app.py": """
def hello():
    return "world"
""",
        })
        
        index = index_project(temp_project)
        func = index['symbols']['src/app.py::hello']
        
        # Read the actual source to verify char_count
        source_lines = (temp_project / "src/app.py").read_text().splitlines()
        func_lines = source_lines[func['line_start']-1:func['line_end']]
        expected_char_count = len('\n'.join(func_lines))
        
        assert func['char_count'] == expected_char_count
    
    def test_approx_tokens_formula(self, temp_project):
        """Test approx_tokens == max(1, char_count // 4)."""
        write_files(temp_project, {
            "src/app.py": """
def tiny():
    pass

def medium_function():
    x = 1
    y = 2
    z = x + y
    return z

def large_function_with_many_operations():
    result = []
    for i in range(100):
        if i % 2 == 0:
            result.append(i * 2)
    return result
""",
        })
        
        index = index_project(temp_project)
        
        for sym_id, sym in index['symbols'].items():
            if sym['kind'] == 'function':
                expected_tokens = max(1, sym['char_count'] // 4)
                assert sym['approx_tokens'] == expected_tokens, \
                    f"{sym_id}: expected {expected_tokens}, got {sym['approx_tokens']}"


class TestSchema12Fields:
    """Test Schema 1.2 specific fields."""
    
    def test_children_field(self, temp_project):
        """Test children field for classes."""
        write_files(temp_project, {
            "src/models.py": """
class APIServer:
    def __init__(self):
        pass
    
    def start(self):
        pass
    
    def stop(self):
        pass
""",
        })
        
        index = index_project(temp_project)
        api_server = index['symbols']['src/models.py::APIServer']
        
        assert len(api_server['children']) == 3
        assert 'src/models.py::APIServer.__init__' in api_server['children']
        assert 'src/models.py::APIServer.start' in api_server['children']
        assert 'src/models.py::APIServer.stop' in api_server['children']
    
    def test_bases_field(self, temp_project):
        """Test bases and bases_unresolved fields."""
        write_files(temp_project, {
            "src/models.py": """
class BaseService:
    pass

class UserService(BaseService):
    pass

class SessionManager(BaseService, object):
    pass
""",
        })
        
        index = index_project(temp_project)
        user_service = index['symbols']['src/models.py::UserService']
        session_manager = index['symbols']['src/models.py::SessionManager']
        
        # UserService should resolve BaseService
        assert 'src/models.py::BaseService' in user_service['bases']
        assert len(user_service['bases_unresolved']) == 0
        
        # SessionManager should resolve BaseService, object stays unresolved
        assert 'src/models.py::BaseService' in session_manager['bases']
        assert 'object' in session_manager['bases_unresolved']
    
    def test_attr_types_field(self, temp_project):
        """Test attr_types field for classes."""
        write_files(temp_project, {
            "src/models.py": """
class Database:
    pass

class UserService:
    def __init__(self, db: Database):
        self.db = db

class APIServer:
    def __init__(self):
        self.user_service = UserService(None)
""",
        })
        
        index = index_project(temp_project)
        user_service = index['symbols']['src/models.py::UserService']
        api_server = index['symbols']['src/models.py::APIServer']
        
        assert user_service['attr_types']['db'] == 'src/models.py::Database'
        assert api_server['attr_types']['user_service'] == 'src/models.py::UserService'


class TestValidateIndex:
    """Test validate_index.py on fixtures."""
    
    def test_validate_on_generated_index(self, temp_project):
        """Test that generated indexes pass validation."""
        write_files(temp_project, {
            "src/app.py": """
class Service:
    def process(self):
        pass

def main():
    s = Service()
    s.process()
""",
        })
        
        # Generate index
        index = index_project(temp_project)
        index_file = temp_project / "index.json"
        with open(index_file, 'w') as f:
            json.dump(index, f)
        
        # Validate it
        is_valid, errors = validate_index(str(index_file))
        
        assert is_valid, f"Index validation failed: {errors}"
        assert len(errors) == 0


class TestRetrievalGoldenTest:
    """Test retrieval with decorated_by edge."""
    
    def test_decorated_by_retrieval(self, temp_project):
        """Test that decorated_by edges work in retrieval (golden test)."""
        write_files(temp_project, {
            "src/app.py": """
def requires_auth(func):
    pass

@requires_auth
def protected_route():
    pass

def _handle_users():
    protected_route()
""",
            "tests/test_app.py": """
from src.app import _handle_users

def test_users():
    _handle_users()
""",
        })
        
        index = index_project(temp_project)
        
        # Check decorator_targets edge
        protected = index['symbols']['src/app.py::protected_route']
        assert 'src/app.py::requires_auth' in protected['decorator_targets']
        
        # For retrieval: if we're analyzing test_users, we should reach requires_auth
        # via _handle_users -> protected_route -> (decorated_by) -> requires_auth
        # This is tested in test_retrieval_walk.py with proper scoring


class TestSchemaVersion:
    """Test that schema version is consistent across all entry points."""
    
    def test_orchestrator_emits_schema_12(self, temp_project):
        """Test that standalone_orchestrator emits schema 1.2."""
        import sys
        import subprocess
        
        write_files(temp_project, {
            "src/app.py": """
def hello():
    return "world"
""",
            "tests/test_app.py": """
from src.app import hello

def test_hello():
    assert hello() == "world"
""",
        })
        
        # Run orchestrator
        result = subprocess.run(
            [
                sys.executable, "standalone_orchestrator.py",
                "--root", str(temp_project),
                "--import-root", "src",
                "--out-dir", str(temp_project / "runs"),
                "--skip-context"
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True
        )
        
        # Check it succeeded
        assert result.returncode == 0, f"Orchestrator failed: {result.stderr}"
        
        # Load the generated index
        index_path = temp_project / "runs" / "index" / "index.json"
        assert index_path.exists(), "Index file not created"
        
        with open(index_path) as f:
            index = json.load(f)
        
        # Verify schema version is 1.2
        assert index['schema_version'] == "1.2", \
            f"Expected schema_version '1.2', got '{index['schema_version']}'"
    
    def test_indexer_cli_emits_schema_12(self, temp_project):
        """Test that indexer CLI emits schema 1.2."""
        import sys
        import subprocess
        
        write_files(temp_project, {
            "src/app.py": """
def hello():
    return "world"
""",
        })
        
        index_path = temp_project / "index.json"
        
        # Run indexer CLI
        result = subprocess.run(
            [
                sys.executable, "-m", "indexer.cli",
                "--root", str(temp_project),
                "--import-root", "src",
                "--out", str(index_path),
                "--no-cache"
            ],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True
        )
        
        # Check it succeeded
        assert result.returncode == 0, f"Indexer CLI failed: {result.stderr}"
        assert index_path.exists(), "Index file not created"
        
        # Load the generated index
        with open(index_path) as f:
            index = json.load(f)
        
        # Verify schema version is 1.2
        assert index['schema_version'] == "1.2", \
            f"Expected schema_version '1.2', got '{index['schema_version']}'"
    
    def test_schema_version_constant(self):
        """Test that SCHEMA_VERSION constant is 1.2."""
        from indexer.index import SCHEMA_VERSION
        assert SCHEMA_VERSION == "1.2"
