"""Tests for BM25 query builder."""

import pytest

from retrieval.bm25_query import (
    build_query, query_from_text, _extract_test_name_terms,
    _extract_message_terms, _extract_identifiers
)


def test_build_query_from_bug_group():
    """Test query building from a realistic bug group."""
    # Simulate api_server test_create_user_validates_password
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'tests/test_services.py::test_create_user_validates_password',
            'error_type': 'AssertionError',
            'error_message': 'assert False',
            'code': 'def test_create_user_validates_password():\n    user = create_user("test", "ab")\n    assert user is None',
            'frames': [
                {
                    'file': 'tests/test_services.py',
                    'line': 65,
                    'function': 'test_create_user_validates_password',
                    'code_line': 'assert user is None',
                    'external': False
                },
                {
                    'file': 'src/services.py',
                    'line': 20,
                    'function': 'create_user',
                    'code_line': 'if _validate_user(username, password):',
                    'external': False
                }
            ]
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Verify query_terms contains expected terms
    assert 'create' in query_terms
    assert 'user' in query_terms
    assert 'validate' in query_terms  # validates -> validate (stemmed)
    assert 'password' in query_terms
    
    # Verify "test"/"tests" removed
    assert 'test' not in sources['test_names']
    assert 'tests' not in sources['test_names']
    
    # Verify test name terms
    assert 'create' in sources['test_names']
    assert 'user' in sources['test_names']
    assert 'validate' in sources['test_names']
    assert 'password' in sources['test_names']
    
    # Verify error info
    assert 'assert' in sources['error_info'] or 'assertionerror' in sources['error_info']
    
    # Verify traceback terms (from source frame, not test frame)
    assert 'validate' in sources['traceback'] or '_validate_user' in sources['traceback']


def test_test_name_term_extraction():
    """Test extraction from test names."""
    # Simple test name
    terms = _extract_test_name_terms("test_create_user_validates_password")
    assert 'create' in terms
    assert 'user' in terms
    assert 'validate' in terms  # validates -> validate
    assert 'password' in terms
    assert 'test' not in terms
    
    # With path prefix
    terms2 = _extract_test_name_terms("tests/test_module.py::test_func_name")
    assert 'func' in terms2
    assert 'name' in terms2
    assert 'test' not in terms2


def test_string_literals_not_in_query():
    """Test that string literals are not tokenized from test body."""
    code = '''
def test_example():
    result = calculate("hello world")
    assert result == "expected"
'''
    
    terms = _extract_identifiers(code)
    
    # Should have identifier terms
    assert 'example' in terms or 'test' in terms
    assert 'result' in terms
    assert 'calculate' in terms
    
    # Should NOT have string literal content
    assert 'hello' not in terms
    assert 'world' not in terms
    assert 'expected' not in terms


def test_empty_error_message():
    """Test handling of bug group with empty error messages."""
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'test_example',
            'error_type': '',
            'error_message': '',
            'code': '',
            'frames': []
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Should still have test name terms
    assert len(query_terms) > 0
    assert 'example' in query_terms


def test_test_and_tests_removed_in_query_builder():
    """Test that 'test' and 'tests' are removed by query builder, not tokenizer."""
    # First verify tokenizer DOES NOT remove them
    from retrieval.tokenizer import tokenize
    tokenizer_result = tokenize("test tests testing")
    assert 'test' in tokenizer_result
    assert 'tests' not in tokenizer_result  # "tests" becomes "test" after stemming
    
    # Now verify query builder removes them
    terms = _extract_test_name_terms("test_example_tests")
    assert 'example' in terms
    assert 'test' not in terms
    assert 'tests' not in terms


def test_literal_filtering_in_message():
    """Test that True/False/None literals are filtered from messages."""
    message = "assert True == False and value is not None"
    
    terms = _extract_message_terms(message)
    
    # OLD: assert 'assert' in terms
    # NEW: 'assert' is a Python keyword (STOPWORD) and should be filtered
    assert 'assert' not in terms, "'assert' is a Python keyword stopword and should be filtered"
    # 'value' is not a stopword and should remain (but will be stemmed to 'valu')
    assert 'valu' in terms, "Expected stemmed form 'valu' (from 'value')"
    
    # Should NOT have literal stopwords
    assert 'true' not in terms
    assert 'false' not in terms
    assert 'none' not in terms


def test_traceback_excludes_test_files():
    """Test that traceback only includes source file frames."""
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'test_example',
            'error_type': 'Error',
            'error_message': 'error',
            'code': '',
            'frames': [
                {
                    'file': 'tests/test_module.py',
                    'function': 'test_function',
                    'code_line': 'assert result',
                    'external': False
                },
                {
                    'file': 'src/module.py',
                    'function': 'calculate',
                    'code_line': 'return a + b',
                    'external': False
                }
            ]
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Should have source frame terms
    assert 'calculate' in sources['traceback']
    # The code_line tokens should be present
    assert len(sources['traceback']) > 0
    
    # Should NOT have test frame terms as primary source
    # (they might appear in test_name, but not traceback)
    # Test that traceback doesn't contain test-specific identifiers
    test_frame_terms = ['test_function']
    for term in test_frame_terms:
        assert term not in sources['traceback']


def test_external_frames_excluded():
    """Test that external frames are excluded."""
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'test_example',
            'error_type': 'Error',
            'error_message': 'error',
            'code': '',
            'frames': [
                {
                    'file': '/usr/lib/python/external.py',
                    'function': 'external_func',
                    'code_line': 'do_something()',
                    'external': True
                },
                {
                    'file': 'src/module.py',
                    'function': 'my_func',
                    'code_line': 'result = calculate()',
                    'external': False
                }
            ]
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Should have internal frame
    assert 'my' in sources['traceback'] or 'func' in sources['traceback'] or 'calculate' in sources['traceback']
    
    # Should NOT have external frame
    assert 'external' not in sources['traceback'] or 'external_func' not in sources['traceback']


def test_query_from_text():
    """Test simple text query builder for retrieve_more."""
    text = "find calculate_sum function"
    
    query_terms = query_from_text(text)
    
    assert 'find' in query_terms
    assert 'calculate' in query_terms
    assert 'sum' in query_terms
    assert 'function' in query_terms or 'func' in query_terms


def test_deduplication_within_sources():
    """Test that terms are deduplicated within each source."""
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1', 'bug2']
    }
    
    # Two bugs with same test name
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'test_example',
            'error_type': 'Error',
            'error_message': '',
            'code': '',
            'frames': []
        },
        'bug2': {
            'bug_id': 'bug2',
            'test_name': 'test_example',
            'error_type': 'Error',
            'error_message': '',
            'code': '',
            'frames': []
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Each source should have deduplicated terms
    # But query_terms can have duplicates across sources
    assert len(sources['test_names']) == len(set(sources['test_names']))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
