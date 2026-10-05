"""String utilities module with intentional bugs.

This module contains string manipulation functions, some of which have bugs
for testing the bug detection pipeline.
"""


def reverse_string(s):
    """Reverse a string.

    Args:
        s: String to reverse

    Returns:
        Reversed string
    """
    return s[::-1]


def count_vowels(s):
    """Count the number of vowels in a string.

    Args:
        s: String to analyze

    Returns:
        Number of vowels in the string
    """
    vowels = 'aeiouAEIOU'
    count = 0
    for char in s:
        if char in vowels:
            count += 1
    return count


def is_palindrome(s):
    """Check if a string is a palindrome (ignoring case and spaces).

    Args:
        s: String to check

    Returns:
        True if string is a palindrome, False otherwise
    """
    s = s.replace(' ', '')
    s_lower = s.lower()
    return s_lower == s_lower[::-1]
