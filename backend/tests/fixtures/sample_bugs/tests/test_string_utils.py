"""Tests for string utilities module.

These tests exercise the string utility functions and expose the intentional bugs.
"""

import sys
from pathlib import Path

# Add src directory to path so we can import string_utils
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from string_utils import reverse_string, capitalize_words, count_vowels, is_palindrome


def test_reverse_string():
    """Test string reversal - this should FAIL."""
    assert reverse_string("hello") == "olleh"
    assert reverse_string("world") == "dlrow"
    assert reverse_string("") == ""


def test_capitalize_words():
    """Test word capitalization - this should PASS."""
    assert capitalize_words("hello world") == "Hello World"
    assert capitalize_words("python programming") == "Python Programming"
    assert capitalize_words("") == ""


def test_count_vowels():
    """Test vowel counting - this should FAIL."""
    assert count_vowels("hello") == 2  # e, o
    assert count_vowels("AEIOU") == 5
    assert count_vowels("xyz") == 0
    assert count_vowels("beautiful") == 5  # e, a, u, i, u


def test_is_palindrome():
    """Test palindrome detection - this should FAIL."""
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("A man a plan a canal Panama") == True
    assert is_palindrome("not a palindrome") == False
