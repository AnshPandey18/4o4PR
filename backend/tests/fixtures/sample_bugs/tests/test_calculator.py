"""Tests for calculator module.

These tests exercise the calculator functions and expose the intentional bugs.
"""

import sys
from pathlib import Path

# Add src directory to path so we can import calculator
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from calculator import add, subtract, multiply, divide, power, modulo


def test_add():
    """Test addition - this should PASS."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_subtract():
    """Test subtraction - this should FAIL."""
    assert subtract(5, 3) == 2
    assert subtract(10, 4) == 6
    assert subtract(0, 5) == -5


def test_multiply():
    """Test multiplication - this should PASS."""
    assert multiply(3, 4) == 12
    assert multiply(-2, 5) == -10
    assert multiply(0, 100) == 0


def test_divide():
    """Test division - this should FAIL."""
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3
    assert divide(7, 2) == 3.5


def test_divide_by_zero():
    """Test division by zero - this should PASS."""
    try:
        divide(5, 0)
        assert False, "Expected ZeroDivisionError"
    except ZeroDivisionError:
        pass  # Expected


def test_power():
    """Test exponentiation - this should PASS."""
    assert power(2, 3) == 8
    assert power(5, 2) == 25
    assert power(10, 0) == 1


def test_modulo():
    """Test modulo operation - this should FAIL."""
    assert modulo(10, 3) == 1
    assert modulo(15, 4) == 3
    assert modulo(7, 5) == 2
