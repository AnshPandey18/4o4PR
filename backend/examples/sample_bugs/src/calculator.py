"""Simple calculator with intentional bugs for testing."""


def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a.
    
    BUG: Returns addition instead of subtraction.
    """
    return a + b  # Should be: return a - b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def divide(a, b):
    """Divide a by b.
    
    BUG: Returns multiplication instead of division.
    """
    return a * b  # Should be: return a / b


def power(a, b):
    """Raise a to the power of b."""
    return a ** b


def modulo(a, b):
    """Get remainder of a divided by b.
    
    BUG: Returns subtraction instead of modulo.
    """
    return a - b  # Should be: return a % b
