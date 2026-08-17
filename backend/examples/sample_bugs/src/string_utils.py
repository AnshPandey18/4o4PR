"""String utility functions with bugs."""


def reverse_string(s):
    """Reverse a string.
    
    BUG: Returns the original string instead of reversed.
    """
    return s  # Should be: return s[::-1]


def capitalize_words(s):
    """Capitalize first letter of each word."""
    return s.title()


def count_vowels(s):
    """Count vowels in a string.
    
    BUG: Counts all characters instead of just vowels.
    """
    return len(s)  # Should be: return sum(1 for c in s.lower() if c in 'aeiou')


def is_palindrome(s):
    """Check if a string is a palindrome.
    
    BUG: Always returns True.
    """
    return True  # Should be: return s == s[::-1]
