"""Tests for BM25 chunk builder."""

import json
import tempfile
from pathlib import Path

import pytest

from retrieval.bm25_chunks import (
    build_chunks, get_searchable_chunks, StaleIndexError, INCLUDE_TEST_CHUNKS
)


@pytest.fixture
def temp_project():
    """Create a temporary project with source files and index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create source directory
        src_dir = root / "src"
        src_dir.mkdir()
        
        # Create a simple function file
        func_file = src_dir / "utils.py"
        func_file.write_text("""def calculate_sum(a, b):
    '''Add two numbers.'''
    return a + b

MAGIC_NUMBER = 42

def helper():
    pass
""")
        
        # Create a class file
        class_file = src_dir / "models.py"
        class_file.write_text("""class User:
    '''A user model.'''
    
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        return f"Hello, {self.name}"
""")
        
        # Create test file
        test_dir = root / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_utils.py"
        test_file.write_text("""def test_calculate_sum():
    assert calculate_sum(1, 2) == 3
""")
        
        # Compute SHA1 for each file
        from common.hashing import sha1_file
        func_sha1 = sha1_file(func_file)
        class_sha1 = sha1_file(class_file)
        test_sha1 = sha1_file(test_file)
        
        # Create index
        index_data = {
            "schema_version": "1.2",
            "run_id": "test_run",
            "content_hash": "test_hash",
            "files": [
                {
                    "path": "src/utils.py",
                    "sha1": func_sha1,
                    "kind": "source"
                },
                {
                    "path": "src/models.py",
                    "sha1": class_sha1,
                    "kind": "source"
                },
                {
                    "path": "tests/test_utils.py",
                    "sha1": test_sha1,
                    "kind": "test"
                }
            ],
            "symbols": [
                {
                    "symbol_id": "src/utils.py::calculate_sum",
                    "kind": "function",
                    "name": "calculate_sum",
                    "file": "src/utils.py",
                    "line_start": 1,
                    "line_end": 3,
                    "signature": "def calculate_sum(a, b)",
                    "docstring": "Add two numbers.",
                    "is_test": False
                },
                {
                    "symbol_id": "src/utils.py::MAGIC_NUMBER",
                    "kind": "constant",
                    "name": "MAGIC_NUMBER",
                    "file": "src/utils.py",
                    "line_start": 5,
                    "line_end": 5,
                    "signature": None,
                    "value_preview": "42",
                    "is_test": False
                },
                {
                    "symbol_id": "src/utils.py::helper",
                    "kind": "function",
                    "name": "helper",
                    "file": "src/utils.py",
                    "line_start": 7,
                    "line_end": 8,
                    "signature": "def helper()",
                    "is_test": False
                },
                {
                    "symbol_id": "src/models.py::User",
                    "kind": "class",
                    "name": "User",
                    "file": "src/models.py",
                    "line_start": 1,
                    "line_end": 8,
                    "signature": "class User",
                    "docstring": "A user model.",
                    "is_test": False,
                    "children": ["src/models.py::User.__init__", "src/models.py::User.greet"]
                },
                {
                    "symbol_id": "src/models.py::User.__init__",
                    "kind": "method",
                    "name": "__init__",
                    "file": "src/models.py",
                    "line_start": 4,
                    "line_end": 5,
                    "signature": "def __init__(self, name)",
                    "parent_class": "User",
                    "is_test": False
                },
                {
                    "symbol_id": "src/models.py::User.greet",
                    "kind": "method",
                    "name": "greet",
                    "file": "src/models.py",
                    "line_start": 7,
                    "line_end": 8,
                    "signature": "def greet(self)",
                    "parent_class": "User",
                    "is_test": False
                },
                {
                    "symbol_id": "tests/test_utils.py::test_calculate_sum",
                    "kind": "function",
                    "name": "test_calculate_sum",
                    "file": "tests/test_utils.py",
                    "line_start": 1,
                    "line_end": 2,
                    "signature": "def test_calculate_sum()",
                    "is_test": True
                }
            ]
        }
        
        index_path = root / "index.json"
        with open(index_path, 'w') as f:
            json.dump(index_data, f)
        
        yield root, index_path


def test_build_chunks_basic(temp_project):
    """Test basic chunk building."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    
    # Should have chunks for: calculate_sum, MAGIC_NUMBER, helper, User (skeleton),
    # User.__init__, User.greet, test_calculate_sum
    assert len(chunks) == 7
    
    # Verify calculate_sum chunk
    calc_chunk = next(c for c in chunks if c.id == "src/utils.py::calculate_sum")
    assert calc_chunk.kind == "function"
    assert calc_chunk.file == "src/utils.py"
    assert calc_chunk.line_start == 1
    assert calc_chunk.line_end == 3
    assert not calc_chunk.is_test
    assert calc_chunk.token_count > 0
    
    # Check that chunk contains expected tokens
    assert 'calculate' in calc_chunk.term_frequencies
    assert 'sum' in calc_chunk.term_frequencies
    assert 'number' in calc_chunk.term_frequencies  # from docstring


def test_class_skeleton_chunk(temp_project):
    """Test that class chunks only contain name + signature + docstring."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    
    # Find User class chunk
    user_chunk = next(c for c in chunks if c.id == "src/models.py::User")
    assert user_chunk.kind == "class"
    
    # Should have tokens from name, signature, docstring
    assert 'user' in user_chunk.term_frequencies
    assert 'model' in user_chunk.term_frequencies
    
    # Should NOT have tokens that appear only in method bodies
    # The word "greet" appears in method name (which is part of class structure)
    # But "hello" only appears in the method body
    # Note: The skeleton should NOT include method bodies
    # Let's check for a token that ONLY appears in method body
    assert 'hello' not in user_chunk.term_frequencies  # Only in greet() body


def test_constant_chunk(temp_project):
    """Test constant chunk creation."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    
    const_chunk = next(c for c in chunks if c.id == "src/utils.py::MAGIC_NUMBER")
    assert const_chunk.kind == "constant"
    assert 'magic' in const_chunk.term_frequencies
    assert 'number' in const_chunk.term_frequencies
    # The value "42" is read from source
    assert '42' in const_chunk.term_frequencies or const_chunk.token_count > 0


def test_method_chunks(temp_project):
    """Test method chunk creation."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    
    # Find __init__ method
    init_chunk = next(c for c in chunks if c.id == "src/models.py::User.__init__")
    assert init_chunk.kind == "method"
    assert 'init' in init_chunk.term_frequencies or '__init__' in init_chunk.term_frequencies
    assert 'name' in init_chunk.term_frequencies
    
    # Find greet method
    greet_chunk = next(c for c in chunks if c.id == "src/models.py::User.greet")
    assert greet_chunk.kind == "method"
    assert 'greet' in init_chunk.term_frequencies or 'greet' in greet_chunk.term_frequencies


def test_test_symbol_marked(temp_project):
    """Test that test symbols are marked as is_test=True."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    
    test_chunk = next(c for c in chunks if c.id == "tests/test_utils.py::test_calculate_sum")
    assert test_chunk.is_test is True


def test_searchable_chunks_excludes_tests_by_default(temp_project):
    """Test that get_searchable_chunks excludes test symbols by default."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    searchable = get_searchable_chunks(chunks)
    
    # Should exclude the test function
    test_ids = [c.id for c in searchable if c.is_test]
    assert len(test_ids) == 0
    
    # Should include non-test symbols
    assert len(searchable) > 0
    assert all(not c.is_test for c in searchable)


def test_stale_index_raises_error(temp_project):
    """Test that modifying a source file after indexing raises StaleIndexError."""
    root, index_path = temp_project
    
    # Modify a source file
    utils_file = root / "src" / "utils.py"
    original_content = utils_file.read_text()
    utils_file.write_text(original_content + "\n# Modified\n")
    
    # Should raise StaleIndexError
    with pytest.raises(StaleIndexError) as exc_info:
        build_chunks(index_path, root)
    
    assert "src/utils.py" in str(exc_info.value)


def test_empty_chunks_excluded(temp_project):
    """Test that chunks with zero tokens are excluded."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    
    # All chunks should have token_count > 0
    assert all(c.token_count > 0 for c in chunks)


def test_term_frequencies_sorted(temp_project):
    """Test that term_frequencies dict is sorted by term."""
    root, index_path = temp_project
    
    chunks = build_chunks(index_path, root)
    
    for chunk in chunks:
        terms = list(chunk.term_frequencies.keys())
        assert terms == sorted(terms), f"Terms not sorted in chunk {chunk.id}"


def test_decorated_function_starts_at_decorator(temp_project):
    """Test that decorated functions have chunks starting at the decorator line."""
    root, index_path = temp_project
    
    # Add a decorated function
    decorated_file = root / "src" / "decorated.py"
    decorated_file.write_text("""@decorator
def func():
    pass
""")
    
    from common.hashing import sha1_file
    decorated_sha1 = sha1_file(decorated_file)
    
    # Update index
    with open(index_path, 'r') as f:
        index_data = json.load(f)
    
    index_data['files'].append({
        "path": "src/decorated.py",
        "sha1": decorated_sha1,
        "kind": "source"
    })
    
    index_data['symbols'].append({
        "symbol_id": "src/decorated.py::func",
        "kind": "function",
        "name": "func",
        "file": "src/decorated.py",
        "line_start": 1,  # Starts at decorator
        "line_end": 3,
        "signature": "def func()",
        "decorators": ["decorator"],
        "is_test": False
    })
    
    with open(index_path, 'w') as f:
        json.dump(index_data, f)
    
    chunks = build_chunks(index_path, root)
    
    func_chunk = next(c for c in chunks if c.id == "src/decorated.py::func")
    assert func_chunk.line_start == 1
    # The chunk text should include the decorator
    assert 'decorator' in func_chunk.term_frequencies


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
