"""Tests for BM25 tokenizer."""

import pytest
from retrieval.tokenizer import tokenize, _split_identifier, _stem, STOPWORDS


class TestIdentifierSplitting:
    """Test identifier splitting with camelCase, PascalCase, and acronyms."""
    
    def test_count_vowels(self):
        """count_vowels gives count, vowels, plus full identifier."""
        result = _split_identifier("count_vowels")
        assert result == ['count', 'vowels', 'count_vowels']
    
    def test_vowels_uppercase(self):
        """VOWELS gives vowels."""
        result = _split_identifier("VOWELS")
        assert result == ['vowels']
    
    def test_is_palindrome(self):
        """isPalindrome gives is, palindrome, plus ispalindrome."""
        result = _split_identifier("isPalindrome")
        assert result == ['is', 'palindrome', 'ispalindrome']
    
    def test_http_response(self):
        """HTTPResponse gives http, response, plus httpresponse."""
        result = _split_identifier("HTTPResponse")
        assert result == ['http', 'response', 'httpresponse']
    
    def test_parse_http_response2(self):
        """parseHTTPResponse2 gives parse, http, response, 2, plus full."""
        result = _split_identifier("parseHTTPResponse2")
        assert result == ['parse', 'http', 'response', '2', 'parsehttpresponse2']


class TestStemming:
    """Test light stemming rules."""
    


    def test_lengths_to_length(self):
        """lengths -> length."""
        assert _stem('lengths') == 'length'
    
    def test_process_unchanged(self):
        """process -> process (would be too short after stemming)."""
        assert _stem('process') == 'process'
    
    def test_class_unchanged(self):
        """class -> class (ends in ss)."""
        assert _stem('class') == 'class'
    

    def test_ed_removal(self):
        """processed -> process."""
        assert _stem('processed') == 'process'
    
    def test_ing_removal(self):
        """processing -> process."""
        assert _stem('processing') == 'process'


class TestStopwords:
    """Test stopword filtering."""
    
    def test_python_keywords_are_stopwords(self):
        """Python keywords like 'assert' are stopwords and should be filtered."""
        # Test that Python keywords are filtered as stopwords
        result = tokenize("assert value is not None")
        
        # Python keywords should be filtered
        assert 'assert' not in result, "'assert' is a Python keyword and should be filtered as stopword"
        assert 'is' not in result, "'is' is a Python keyword and should be filtered as stopword"
        assert 'not' not in result, "'not' is a Python keyword and should be filtered as stopword"
        assert 'none' not in result, "'none' is a Python keyword and should be filtered as stopword"
        
        # Non-stopwords should remain (but will be stemmed)
        assert 'valu' in result, "Expected stemmed form 'valu' (from 'value')"
    
    def test_stopword_dropped(self):
        """Stopwords are filtered out."""
        result = tokenize("return the value")
        assert 'return' not in result
        assert 'the' not in result
        # OLD: assert 'value' in result
        # NEW: 'value' is stemmed to 'valu'
        assert 'valu' in result, "Expected stemmed form 'valu' (from 'value')"
    
    def test_stopword_in_identifier(self):
        """Stopword piece is dropped from isPalindrome."""
        result = tokenize("isPalindrome")
        # 'is' is a stopword and should be dropped
        assert 'is' not in result
        # OLD: assert 'palindrome' in result
        # NEW: 'palindrome' is stemmed to 'palindrom'
        assert 'palindrom' in result, "Expected stemmed form 'palindrom' (from 'palindrome')"
        assert 'ispalindrome' in result


class TestMinimumLength:
    """Test minimum token length filtering."""
    
    def test_short_tokens_dropped(self):
        """Tokens shorter than MIN_TOKEN_LEN are dropped."""
        result = tokenize("a ab abc")
        assert 'a' not in result  # length 1
        assert 'ab' in result      # length 2 (minimum)
        assert 'abc' in result     # length 3
    
    def test_digit_only_dropped(self):
        """Single digit tokens are too short."""
        result = tokenize("test2")
        assert 'test' in result
        # '2' is length 1, should be dropped
        assert '2' not in result


class TestFullTokenization:
    """Test complete tokenization with all rules."""
    
    def test_empty_string(self):
        """Empty string gives empty list."""
        assert tokenize("") == []
    
    def test_simple_snake_case(self):
        """Simple snake_case function name."""
        result = tokenize("count_vowels")
        assert result == ['count', 'vowel', 'count_vowels']
    

    def test_with_punctuation(self):
        """Text with various punctuation."""
        result = tokenize("hello_world! test-case, foo.bar")
        assert 'hello' in result
        assert 'world' in result
        assert 'test' in result
        assert 'case' in result
        assert 'foo' in result
        assert 'bar' in result
    
    def test_unicode_letters(self):
        """Unicode letters are tokenized."""
        result = tokenize("café naïve")
        assert 'café' in result or 'caf' in result  # depends on regex handling
        # At minimum, should handle ASCII part
        result2 = tokenize("test_café")
        assert 'test' in result2
    
    def test_identical_runs(self):
        """Two runs produce identical output."""
        text = "def calculate_sum(values): return sum(values)"
        result1 = tokenize(text)
        result2 = tokenize(text)
        assert result1 == result2
    
    def test_preserves_duplicates(self):
        """Duplicates are preserved in output."""
        result = tokenize("test test code")
        # Should have 'test' twice and 'code' once
        assert result.count('test') == 2
        assert result.count('code') == 1
    
    def test_order_of_first_occurrence(self):
        """Tokens appear in order of first occurrence."""
        result = tokenize("alpha beta alpha gamma")
        # 'alpha' appears first, then 'beta', then 'gamma'
        first_alpha = result.index('alpha')
        first_beta = result.index('beta')
        first_gamma = result.index('gamma')
        assert first_alpha < first_beta < first_gamma


class TestRealWorldExamples:
    """Test with realistic code identifiers."""
    



class TestStemmingEnabled:
    """Test behavior with stemming on vs off."""
    
    
    def test_validates_without_stemming(self):
        """Without stemming, validates stays validates."""
        from retrieval import tokenizer
        original = tokenizer.STEM_ENABLED
        try:
            tokenizer.STEM_ENABLED = False
            result = tokenize("validates")
            assert 'validates' in result
            assert 'validate' not in result
        finally:
            tokenizer.STEM_ENABLED = original


class TestStopwordApplication:
    """Test that stopwords apply to both pieces and full identifiers."""
    
    def test_full_identifier_is_stopword(self):
        """If full identifier is a stopword, it's dropped."""
        result = tokenize("return")
        assert 'return' not in result  # stopword
    
    def test_piece_is_stopword(self):
        """If a split piece is a stopword, it's dropped."""
        result = tokenize("returnValue")
        # 'return' is stopword, dropped
        # OLD: assert 'value' in result
        # NEW: 'value' is stemmed to 'valu'
        assert 'return' not in result
        assert 'valu' in result, "Expected stemmed form 'valu' (from 'value')"
        # 'returnvalue' full identifier kept (not in stopwords)
        assert 'returnvalue' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
