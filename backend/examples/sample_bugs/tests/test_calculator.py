"""Tests for calculator module."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from calculator import add, subtract, multiply, divide, power, modulo


def test_add():
    """Test addition - should pass."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_subtract():
    """Test subtraction - should FAIL."""
    assert subtract(5, 3) == 2
    assert subtract(10, 4) == 6
    assert subtract(0, 5) == -5


def test_multiply():
    """Test multiplication - should pass."""
    assert multiply(3, 4) == 12
    assert multiply(0, 100) == 0
    assert multiply(-2, 3) == -6


def test_divide():
    """Test division - should FAIL."""
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3
    assert divide(100, 4) == 25


def test_power():
    """Test power - should pass."""
    assert power(2, 3) == 8
    assert power(5, 2) == 25
    assert power(10, 0) == 1


def test_modulo():
    """Test modulo - should FAIL."""
    assert modulo(10, 3) == 1
    assert modulo(17, 5) == 2
    assert modulo(20, 6) == 2
