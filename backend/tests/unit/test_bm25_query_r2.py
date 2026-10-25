"""R2 tests for query builder spec compliance using bm25_eval_full.txt data."""

import pytest

from retrieval.bm25_query import build_query, _strip_pytest_boilerplate


def test_no_pytest_boilerplate_in_error_info():
    """Test that pytest boilerplate is stripped from error messages."""
    # From data_processor group in bm25_eval_full.txt
    error_message = """AssertionError: assert [10, 50] == [10, 50, 150, 200]
  At index 2 diff: None != 150
  Full diff:
    - [10, 50, 150, 200]
    ?       ------
    +  [10, 50]
  Full output truncated (6 lines hidden), use `-vv` to show"""
    
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'tests/test_processor.py::test_filter_removes_invalid',
            'error_type': 'AssertionError',
            'error_message': error_message,
            'code': 'def test_filter_removes_invalid(): pass',
            'frames': []
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Should NOT contain pytest boilerplate
    error_terms = sources['error_info']
    assert 'should' not in error_terms, "should not contain 'should'"
    assert 'diff' not in error_terms, "should not contain 'diff'"
    assert 'truncat' not in error_terms, "should not contain 'truncat'"
    assert 'vv' not in error_terms, "should not contain 'vv'"
    assert 'hidden' not in error_terms, "should not contain 'hidden'"
    assert 'use' not in error_terms, "should not contain 'use'"


def test_no_digit_only_tokens():
    """Test that digit-only tokens are filtered out."""
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'tests/test_processor.py::test_filter_removes_invalid',
            'error_type': 'AssertionError',
            'error_message': 'assert [10, 50] == [10, 50, 150, 200]',
            'code': 'result = processor.filter([10, 50, 150, 200])',
            'frames': []
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Should NOT contain digit-only tokens
    assert '10' not in query_terms, "should not contain '10'"
    assert '50' not in query_terms, "should not contain '50'"
    assert '150' not in query_terms, "should not contain '150'"
    assert '200' not in query_terms, "should not contain '200'"
    
    # Check all sources
    for source_name, terms in sources.items():
        for term in terms:
            assert not term.isdigit(), f"source {source_name} contains digit-only token '{term}'"


def test_test_body_no_docstring_terms():
    """Test that docstrings and comments are excluded from test body terms."""
    # From string_processor fixture (has "This should fail" in docstring)
    code = '''def test_is_valid_domain():
    """This should fail because _is_valid_domain always returns True."""
    assert not _is_valid_domain("invalid.com")
'''
    
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': 'tests/test_validator.py::test_is_valid_domain',
            'error_type': 'AssertionError',
            'error_message': 'assert False',
            'failing_function_code': code,
            'code': code,
            'frames': []
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Should NOT contain docstring words
    body_terms = sources['test_body']
    assert 'should' not in body_terms, "should not contain 'should' from docstring"
    assert 'fail' not in body_terms, "should not contain 'fail' from docstring"
    assert 'because' not in body_terms, "should not contain 'because' from docstring"
    assert 'alway' not in body_terms, "should not contain 'alway' from docstring"
    
    # SHOULD contain actual code identifiers
    assert 'valid' in body_terms or 'domain' in body_terms, "should contain code identifiers"


def test_test_name_terms_unchanged():
    """Test that test name tokenization preserves identifier parts."""
    # From api_server fixture
    test_name = 'tests/test_services.py::test_create_user_validates_password'
    
    bug_group = {
        'group_id': 'G1',
        'bug_ids': ['bug1']
    }
    
    bugs = {
        'bug1': {
            'bug_id': 'bug1',
            'test_name': test_name,
            'error_type': 'AssertionError',
            'error_message': 'assert False',
            'code': 'pass',
            'frames': []
        }
    }
    
    query_terms, sources = build_query(bug_group, bugs)
    
    # Test name terms should be tokenized consistently (Porter2 stems some)
    name_terms = sources['test_names']
    # Porter2: create->creat, validates->valid
    assert 'creat' in name_terms or 'create' in name_terms, "should have create/creat"
    assert 'user' in name_terms
    assert 'valid' in name_terms or 'validate' in name_terms, "should have valid/validate"
    assert 'password' in name_terms
    
    # test/tests should be removed
    assert 'test' not in name_terms
    assert 'tests' not in name_terms


def test_boilerplate_stripper_removes_e_markers():
    """Test that 'E   ' continuation markers are removed."""
    message = """AssertionError
E   assert False
E   where False = is_valid_domain('invalid.com')
"""
    
    cleaned = _strip_pytest_boilerplate(message)
    
    # Should not start with E
    lines = cleaned.split('\n')
    for line in lines:
        if line.strip():
            assert not line.strip().startswith('E '), f"Line still has E marker: {line}"


def test_boilerplate_stripper_removes_truncation_hints():
    """Test that truncation hints are removed."""
    message = "AssertionError: Full output truncated (6 lines hidden), use `-vv` to show"
    
    cleaned = _strip_pytest_boilerplate(message)
    
    # Should not contain these phrases
    assert 'truncat' not in cleaned.lower()
    assert 'hidden' not in cleaned.lower()
    assert '-vv' not in cleaned
    assert 'use' not in cleaned.lower()
