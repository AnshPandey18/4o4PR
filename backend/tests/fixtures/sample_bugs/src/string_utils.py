"""String utilities module with intentional bugs.

This module contains string manipulation functions, some of which have bugs
for testing the bug detection pipeline.
"""


def reverse_string(s):
    """Reverse a string.
    
    BUG: Returns the string unchanged instead of reversed
    
    Args:
        s: String to reverse
        
    Returns:
        Reversed string
    """
    return s  # BUG: Should be s[::-1]


def capitalize_words(s):
    """Capitalize the first letter of each word.
    
    Args:
        s: String to capitalize
        
    Returns:
        String with each word capitalized
    """
    return s.title()


def count_vowels(s):
    """Count the number of vowels in a string.
    
    BUG: Counts 'e' twice (both lowercase and uppercase)
    
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
        # BUG: Extra count for 'e' and 'E'
        if char in 'eE':
            count += 1
    return count


def is_palindrome(s):
    """Check if a string is a palindrome (ignoring case and spaces).
    
    BUG: Doesn't ignore spaces, and comparison logic is reversed
    
    Args:
        s: String to check
        
    Returns:
        True if string is a palindrome, False otherwise
    """
    # BUG: Should remove spaces: s = s.replace(' ', '')
    s_lower = s.lower()
    # BUG: Comparison is reversed (should be ==)
    return s_lower != s_lower[::-1]
