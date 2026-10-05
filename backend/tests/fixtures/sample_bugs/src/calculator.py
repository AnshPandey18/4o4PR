"""Calculator module with intentional bugs.

This module contains basic arithmetic operations, some of which have bugs
for testing the bug detection pipeline.
"""


def add(a, b):
    """Add two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b


def subtract(a, b):
    """Subtract b from a.

    Args:
        a: First number
        b: Second number

    Returns:
        Difference of a and b
    """
    return a - b


def divide(a, b):
    """Divide a by b.

    Args:
        a: Numerator
        b: Denominator

    Returns:
        Quotient of a divided by b

    Raises:
        ZeroDivisionError: If b is zero
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def modulo(a, b):
    """Calculate a modulo b.

    Args:
        a: Dividend
        b: Divisor

    Returns:
        Remainder of a divided by b

    Raises:
        ZeroDivisionError: If b is zero
    """
    if b == 0:
        raise ZeroDivisionError("Cannot modulo by zero")
    return a % b
