"""Tests for string utilities."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from string_utils import reverse_string, capitalize_words, count_vowels, is_palindrome


def test_reverse_string():
    """Test string reversal - should FAIL."""
    assert reverse_string("hello") == "olleh"
    assert reverse_string("world") == "dlrow"
    assert reverse_string("") == ""


def test_capitalize_words():
    """Test word capitalization - should pass."""
    assert capitalize_words("hello world") == "Hello World"
    assert capitalize_words("python programming") == "Python Programming"


def test_count_vowels():
    """Test vowel counting - should FAIL."""
    assert count_vowels("hello") == 2  # e, o
    assert count_vowels("world") == 1  # o
    assert count_vowels("aeiou") == 5
    assert count_vowels("xyz") == 0


def test_is_palindrome():
    """Test palindrome detection - should FAIL."""
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("madam") == True
    assert is_palindrome("test") == False
