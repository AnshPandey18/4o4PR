"""Test to ensure query construction never reads answer keys.

Per protocol R8: Pipeline and retrieval code must never read tests/answer_keys/
or any file named expected_bugs.json or *answer*.
"""

import sys
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from retrieval.bm25_query import build_query


def test_query_construction_no_answer_key_access():
    """Ensure build_query never opens answer key files."""
    
    # Create mock bug data (only data available from actual test run)
    mock_bug = {
        'bug_id': 'test_bug',
        'test_name': 'tests/test_example.py::test_function',
        'test_file': 'tests/test_example.py',
        'error_type': 'AssertionError',
        'error_message': 'assert False',
        'failing_function_code': 'def test_function():\n    assert False',
        'code': 'def test_function():\n    assert False',
        'frames': [
            {
                'file': 'src/example.py',
                'line': 10,
                'function': 'broken_function',
                'external': False
            }
        ]
    }
    
    bug_group = {
        'bug_ids': ['test_bug']
    }
    
    bugs = {
        'test_bug': mock_bug
    }
    
    # Track file opens
    opened_files = []
    original_open = open
    
    def tracking_open(file, *args, **kwargs):
        opened_files.append(str(file))
        return original_open(file, *args, **kwargs)
    
    # Patch open to track file access
    with patch('builtins.open', side_effect=tracking_open):
        try:
            # Build query (may fail without graph, that's ok)
            query_terms, sources = build_query(bug_group, bugs, graph=None)
        except Exception:
            # Errors are ok, we just care about file access
            pass
    
    # Check that no answer key files were opened
    forbidden_patterns = [
        'answer_keys',
        'expected_bugs',
        'answer.json',
        'answers.json'
    ]
    
    for opened_file in opened_files:
        opened_lower = opened_file.lower()
        for pattern in forbidden_patterns:
            assert pattern not in opened_lower, (
                f"Query construction opened forbidden file: {opened_file}\n"
                f"Matched pattern: {pattern}\n"
                f"This violates protocol rule R8: no answer-key access in pipeline code"
            )


def test_eval_script_does_not_use_description():
    """Ensure eval script doesn't use bug['description'] from answer key."""
    
    # Read the eval script
    eval_script_path = BACKEND_DIR / 'scripts' / 'eval_bm25_phase5.py'
    
    if not eval_script_path.exists():
        pytest.skip("Eval script not found")
    
    content = eval_script_path.read_text(encoding='utf-8')
    
    # Check for contamination pattern
    # Look for bug.get('description') or bug['description'] used for error_message
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check if line assigns to error_message
        if "'error_message'" in line or '"error_message"' in line:
            # Should NOT contain bug description access
            if "bug.get('description'" in line or 'bug["description"]' in line or "bug['description']" in line:
                # Allow if it's a comment explaining the fix
                if '#' in line and 'FIXED' in line.upper():
                    continue
                
                pytest.fail(
                    f"Line {i} in eval_bm25_phase5.py uses answer-key description:\n"
                    f"{line.strip()}\n\n"
                    f"This leaks ground-truth data into queries (answer-key contamination).\n"
                    f"Use empty string or actual test error message instead."
                )


def test_query_builder_imports_no_answer_keys():
    """Ensure query builder module doesn't import from answer_keys directory."""
    
    query_module_path = BACKEND_DIR / 'retrieval' / 'bm25_query.py'
    
    if not query_module_path.exists():
        pytest.skip("Query module not found")
    
    content = query_module_path.read_text(encoding='utf-8')
    
    # Check imports
    forbidden_imports = [
        'from tests.answer_keys',
        'import tests.answer_keys',
        'from answer_keys',
        'import answer_keys'
    ]
    
    for forbidden in forbidden_imports:
        assert forbidden not in content, (
            f"Query builder imports from answer_keys: {forbidden}\n"
            f"This violates protocol rule R8"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
