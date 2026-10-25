"""R3 verification tests for Porter2 stemmer + NLTK stopwords."""

import pytest

from retrieval.tokenizer import tokenize, _stem


def test_this_removed_by_stopwords():
    """Test that 'this' is properly removed by NLTK stopwords."""
    result = tokenize('this')
    assert result == [], f"'this' should be removed by stopwords, got {result}"


def test_always_stemmed_correctly():
    """Test that 'always' is stemmed to 'alway' by Porter2."""
    # Porter2 stems 'always' to 'alway'
    result = tokenize('always')
    assert 'alway' in result, f"'always' should stem to 'alway', got {result}"
    
    # Direct stem test
    stemmed = _stem('always')
    assert stemmed == 'alway', f"_stem('always') should be 'alway', got '{stemmed}'"


def test_removes_equals_remove():
    """Test that 'removes' and 'remove' stem to the same form."""
    removes_tokens = tokenize('removes')
    remove_tokens = tokenize('remove')
    
    assert len(removes_tokens) == 1, f"'removes' should produce one token, got {removes_tokens}"
    assert len(remove_tokens) == 1, f"'remove' should produce one token, got {remove_tokens}"
    assert removes_tokens[0] == remove_tokens[0], \
        f"'removes' and 'remove' should stem to same form: {removes_tokens[0]} != {remove_tokens[0]}"
    
    # Both should stem to 'remov'
    assert removes_tokens[0] == 'remov', f"Expected 'remov', got '{removes_tokens[0]}'"


def test_values_equals_value():
    """Test that 'values' and 'value' stem to the same form."""
    values_tokens = tokenize('values')
    value_tokens = tokenize('value')
    
    assert len(values_tokens) == 1, f"'values' should produce one token, got {values_tokens}"
    assert len(value_tokens) == 1, f"'value' should produce one token, got {value_tokens}"
    assert values_tokens[0] == value_tokens[0], \
        f"'values' and 'value' should stem to same form: {values_tokens[0]} != {value_tokens[0]}"
    
    # Both should stem to 'valu'
    assert values_tokens[0] == 'valu', f"Expected 'valu', got '{values_tokens[0]}'"


def test_class_removed_by_python_keywords():
    """Test that 'class' is removed by Python keyword stopwords."""
    result = tokenize('class')
    assert result == [], f"'class' should be removed as Python keyword, got {result}"


def test_process_unchanged():
    """Test that 'process' stems to itself (no suffix to remove)."""
    result = tokenize('process')
    assert 'process' in result, f"'process' should stem to itself, got {result}"
    
    # Direct stem test
    stemmed = _stem('process')
    assert stemmed == 'process', f"_stem('process') should be 'process', got '{stemmed}'"


def test_validates_to_valid():
    """Test that 'validates' stems to 'valid' (Porter2 behavior)."""
    result = tokenize('validates')
    assert 'valid' in result, f"'validates' should stem to 'valid', got {result}"
    
    # Direct stem test
    stemmed = _stem('validates')
    assert stemmed == 'valid', f"_stem('validates') should be 'valid', got '{stemmed}'"


def test_validate_to_valid():
    """Test that 'validate' stems to 'valid' (Porter2 behavior)."""
    result = tokenize('validate')
    assert 'valid' in result, f"'validate' should stem to 'valid', got {result}"
    
    # Direct stem test
    stemmed = _stem('validate')
    assert stemmed == 'valid', f"_stem('validate') should be 'valid', got '{stemmed}'"


def test_length_variations():
    """Test that length variations stem to same form."""
    # lengths -> length (Porter2)
    lengths_tokens = tokenize('lengths')
    length_tokens = tokenize('length')
    
    assert lengths_tokens[0] == length_tokens[0], \
        f"'lengths' and 'length' should stem to same form"
    assert lengths_tokens[0] == 'length', f"Expected 'length', got '{lengths_tokens[0]}'"


def test_python_keywords_removed():
    """Test that Python keywords are removed as stopwords."""
    keywords_to_test = ['return', 'import', 'for', 'in', 'if', 'else', 'def', 'class']
    
    for keyword in keywords_to_test:
        result = tokenize(keyword)
        assert result == [], f"Python keyword '{keyword}' should be removed, got {result}"


def test_nltk_stopwords_removed():
    """Test that common NLTK stopwords are removed."""
    stopwords_to_test = ['the', 'is', 'at', 'which', 'on', 'a', 'an', 'this', 'that']
    
    for stopword in stopwords_to_test:
        result = tokenize(stopword)
        assert result == [], f"NLTK stopword '{stopword}' should be removed, got {result}"
