"""Porter2 stemmer consistency tests.

These tests verify that Porter2 stemmer produces consistent stems for related word forms.
They document actual Porter2 behavior rather than asserting specific stem values.

Created: 2026-10-24
Reason: Replace old stem-specific tests with consistency tests (S2 Item 3)
"""

import pytest
from retrieval.tokenizer import _stem, tokenize


class TestPorter2Consistency:
    """Test Porter2 stemmer consistency across word forms."""
    
    def test_validate_family_consistency(self):
        """validate, validates, validated, validating all produce same stem."""
        stems = [_stem('validate'), _stem('validates'), _stem('validated'), _stem('validating')]
        # All should produce the same stem
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        # Document actual Porter2 output
        assert stems[0] == 'valid'
    
    def test_calculate_family_consistency(self):
        """calculate, calculates, calculated, calculating all produce same stem."""
        stems = [_stem('calculate'), _stem('calculates'), _stem('calculated'), _stem('calculating')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        assert stems[0] == 'calcul'
    
    def test_create_family_consistency(self):
        """create, creates, created, creating all produce same stem."""
        stems = [_stem('create'), _stem('creates'), _stem('created'), _stem('creating')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        assert stems[0] == 'creat'
    
    def test_example_family_consistency(self):
        """example, examples all produce same stem."""
        stems = [_stem('example'), _stem('examples')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        assert stems[0] == 'exampl'
    
    def test_decorator_family_consistency(self):
        """decorator, decorated, decorating all produce same stem."""
        stems = [_stem('decorator'), _stem('decorated'), _stem('decorating')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        assert stems[0] == 'decor'
    
    def test_palindrome_family_consistency(self):
        """palindrome, palindromes all produce same stem."""
        stems = [_stem('palindrome'), _stem('palindromes')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        assert stems[0] == 'palindrom'
    
    def test_response_family_consistency(self):
        """response, responses all produce same stem."""
        stems = [_stem('response'), _stem('responses')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        assert stems[0] == 'respons'
    
    def test_value_family_consistency(self):
        """value, values all produce same stem."""
        stems = [_stem('value'), _stem('values')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        assert stems[0] == 'valu'
    
    def test_entry_family_consistency(self):
        """entry, entries all produce same stem."""
        stems = [_stem('entry'), _stem('entries')]
        assert len(set(stems)) == 1, f"Inconsistent stems: {stems}"
        # Porter2: both produce 'entri' (not 'entry' as old test expected)
        assert stems[0] == 'entri'


class TestPorter2TokenizeConsistency:
    """Test tokenize() function consistency with Porter2."""
    
    def test_validate_user_tokenization(self):
        """_validate_user tokenizes consistently."""
        result = tokenize("_validate_user")
        # Should contain stemmed form of 'validate'
        assert 'valid' in result
        assert 'user' in result
    
    def test_http_response_tokenization(self):
        """HTTPResponse tokenizes consistently."""
        result = tokenize("HTTPResponse")
        # Should contain stemmed forms
        assert 'http' in result
        assert 'respons' in result  # Porter2 stems 'response' to 'respons'
    
    def test_create_user_validates_password_tokenization(self):
        """test_create_user_validates_password tokenizes consistently."""
        result = tokenize("test_create_user_validates_password")
        # Should contain stemmed forms
        assert 'test' in result or 'test_create_user_validates_password' in result
        assert 'creat' in result
        assert 'user' in result
        assert 'valid' in result  # validates -> valid
        assert 'password' in result
    
    def test_calculate_sum_tokenization(self):
        """calculate_sum tokenizes consistently."""
        result = tokenize("calculate_sum")
        # Should contain stemmed form of calculate
        assert 'calcul' in result
        assert 'sum' in result


class TestPorter2DocumentedBehavior:
    """Document specific Porter2 behaviors for reference."""
    
    def test_lengths_to_length(self):
        """lengths stems to length (Porter2 removes trailing s)."""
        assert _stem('lengths') == 'length'
    
    def test_process_unchanged(self):
        """process remains process (Porter2 no suffix to remove)."""
        assert _stem('process') == 'process'
    
    def test_class_unchanged(self):
        """class remains class (Porter2 no suffix to remove)."""
        assert _stem('class') == 'class'
    
    def test_ed_removal(self):
        """Porter2 -ed suffix removal."""
        assert _stem('validated') == 'valid'
        assert _stem('calculated') == 'calcul'
    
    def test_ing_removal(self):
        """Porter2 -ing suffix removal."""
        assert _stem('validating') == 'valid'
        assert _stem('calculating') == 'calcul'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
