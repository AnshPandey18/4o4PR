# Bug Detection Report

## Run Information

- **Run ID:** r_20261005_205310
- **Timestamp:** 2026-10-05T15:23:20.291116Z
- **Project Root:** .
- **Python Version:** 3.14.7
- **Pytest Version:** 9.1.1
- **Content Hash:** 008ac7698522711b...

## Summary

- **Total Tests Run:** 11

- **Total Failures:** 6

- **Total Errors:** 0

- **Tests Passed:** 5

- **Tests Skipped:** 0

- **Bugs Detected:** 6

- **Pytest Exit Code:** 1

- **Duration:** 0.07s

- **Consistency Check:** ✓ PASS

## Detected Bugs

### Bug #1: tests/test_calculator.py::test_subtract

- **Bug ID:** `b_056a5081c629`
- **Failure Kind:** assertion
- **Error Type:** Error

**Error Message:**
```
assert 8 == 2
 +  where 8 = subtract(5, 3)
```

**Location:**
- File: `tests/test_calculator.py`
- Line: 25

**Assertion Details:**
- Statement: `assert subtract(5, 3) == 2`
- Line: 25
- Assertion 1 of 3
- 2 assertion(s) not evaluated after this failure
- Operator: `==`
- Actual: `8`
- Expected: `2`

**Called Symbols:**
- `subtract` → `src/calculator.py::subtract` (src/calculator.py:21)

**Inferred Source Module:** `src/calculator.py`

**Traceback:**
```
  tests/test_calculator.py:25 in 
    assert subtract(5, 3) == 2E   assert 8 == 2E    +  where 8 = subtract(5, 3)
```

**Test Code:**
```python
def test_subtract():
    """Test subtraction - this should FAIL."""
    assert subtract(5, 3) == 2
    assert subtract(10, 4) == 6
    assert subtract(0, 5) == -5
```

**Source Snapshot (subtract):**
```python
def subtract(a, b):
    """Subtract b from a.
    
    BUG: Returns a + b instead of a - b
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Difference of a and b
    """
    return a + b  # BUG: Should be a - b
```

**Rerun Command:** `pytest "tests/test_calculator.py::test_subtract"`

---

### Bug #2: tests/test_calculator.py::test_divide

- **Bug ID:** `b_54e477c51122`
- **Failure Kind:** assertion
- **Error Type:** Error

**Error Message:**
```
assert 0.2 == 5
 +  where 0.2 = divide(10, 2)
```

**Location:**
- File: `tests/test_calculator.py`
- Line: 39

**Assertion Details:**
- Statement: `assert divide(10, 2) == 5`
- Line: 39
- Assertion 1 of 3
- 2 assertion(s) not evaluated after this failure
- Operator: `==`
- Actual: `0.2`
- Expected: `5`

**Called Symbols:**
- `divide` → `src/calculator.py::divide` (src/calculator.py:49)

**Inferred Source Module:** `src/calculator.py`

**Traceback:**
```
  tests/test_calculator.py:39 in 
    assert divide(10, 2) == 5E   assert 0.2 == 5E    +  where 0.2 = divide(10, 2)
```

**Test Code:**
```python
def test_divide():
    """Test division - this should FAIL."""
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3
    assert divide(7, 2) == 3.5
```

**Source Snapshot (divide):**
```python
def divide(a, b):
    """Divide a by b.
    
    BUG: Returns b / a instead of a / b
    
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
    return b / a  # BUG: Should be a / b
```

**Rerun Command:** `pytest "tests/test_calculator.py::test_divide"`

---

### Bug #3: tests/test_calculator.py::test_modulo

- **Bug ID:** `b_bd675980c5ec`
- **Failure Kind:** assertion
- **Error Type:** Error

**Error Message:**
```
assert 0 == 1
 +  where 0 = modulo(10, 3)
```

**Location:**
- File: `tests/test_calculator.py`
- Line: 62

**Assertion Details:**
- Statement: `assert modulo(10, 3) == 1`
- Line: 62
- Assertion 1 of 3
- 2 assertion(s) not evaluated after this failure
- Operator: `==`
- Actual: `0`
- Expected: `1`

**Called Symbols:**
- `modulo` → `src/calculator.py::modulo` (src/calculator.py:82)

**Inferred Source Module:** `src/calculator.py`

**Traceback:**
```
  tests/test_calculator.py:62 in 
    assert modulo(10, 3) == 1E   assert 0 == 1E    +  where 0 = modulo(10, 3)
```

**Test Code:**
```python
def test_modulo():
    """Test modulo operation - this should FAIL."""
    assert modulo(10, 3) == 1
    assert modulo(15, 4) == 3
    assert modulo(7, 5) == 2
```

**Source Snapshot (modulo):**
```python
def modulo(a, b):
    """Calculate a modulo b.
    
    BUG: Returns a % (b - 1) instead of a % b
    
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
    return a % (b - 1)  # BUG: Should be a % b
```

**Rerun Command:** `pytest "tests/test_calculator.py::test_modulo"`

---

### Bug #4: tests/test_string_utils.py::test_reverse_string

- **Bug ID:** `b_e6f0145b1e87`
- **Failure Kind:** assertion
- **Error Type:** AssertionError

**Error Message:**
```
assert 'hello' == 'olleh'
  
  - olleh
  + hello
```

**Location:**
- File: `tests/test_string_utils.py`
- Line: 18

**Assertion Details:**
- Statement: `assert reverse_string("hello") == "olleh"`
- Line: 18
- Assertion 1 of 3
- 2 assertion(s) not evaluated after this failure
- Operator: `==`
- Actual: `'hello'`
- Expected: `'olleh'`

**Called Symbols:**
- `reverse_string` → `src/string_utils.py::reverse_string` (src/string_utils.py:8)

**Inferred Source Module:** `src/string_utils.py`

**Traceback:**
```
  tests/test_string_utils.py:18 in 
    assert reverse_string("hello") == "olleh"E   AssertionError: assert 'hello' == 'olleh'E     E     - ollehE     + hello
```

**Test Code:**
```python
def test_reverse_string():
    """Test string reversal - this should FAIL."""
    assert reverse_string("hello") == "olleh"
    assert reverse_string("world") == "dlrow"
    assert reverse_string("") == ""
```

**Source Snapshot (reverse_string):**
```python
def reverse_string(s):
    """Reverse a string.
    
    BUG: Returns the string unchanged instead of reversed
    
    Args:
        s: String to reverse
        
    Returns:
        Reversed string
    """
    return s  # BUG: Should be s[::-1]
```

**Rerun Command:** `pytest "tests/test_string_utils.py::test_reverse_string"`

---

### Bug #5: tests/test_string_utils.py::test_count_vowels

- **Bug ID:** `b_3d27458021e3`
- **Failure Kind:** assertion
- **Error Type:** AssertionError

**Error Message:**
```
assert 3 == 2
 +  where 3 = count_vowels('hello')
```

**Location:**
- File: `tests/test_string_utils.py`
- Line: 32

**Assertion Details:**
- Statement: `assert count_vowels("hello") == 2  # e, o`
- Line: 32
- Assertion 1 of 4
- 3 assertion(s) not evaluated after this failure
- Operator: `==`
- Actual: `3`
- Expected: `2`

**Called Symbols:**
- `count_vowels` → `src/string_utils.py::count_vowels` (src/string_utils.py:34)

**Inferred Source Module:** `src/string_utils.py`

**Traceback:**
```
  tests/test_string_utils.py:32 in 
    assert count_vowels("hello") == 2  # e, o    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^E   AssertionError: assert 3 == 2E    +  where 3 = count_vowels('hello')
```

**Test Code:**
```python
def test_count_vowels():
    """Test vowel counting - this should FAIL."""
    assert count_vowels("hello") == 2  # e, o
    assert count_vowels("AEIOU") == 5
    assert count_vowels("xyz") == 0
    assert count_vowels("beautiful") == 5  # e, a, u, i, u
```

**Source Snapshot (count_vowels):**
```python
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
```

**Rerun Command:** `pytest "tests/test_string_utils.py::test_count_vowels"`

---

### Bug #6: tests/test_string_utils.py::test_is_palindrome

- **Bug ID:** `b_c283258e46bb`
- **Failure Kind:** assertion
- **Error Type:** AssertionError

**Error Message:**
```
assert False == True
 +  where False = is_palindrome('racecar')
```

**Location:**
- File: `tests/test_string_utils.py`
- Line: 40

**Assertion Details:**
- Statement: `assert is_palindrome("racecar") == True`
- Line: 40
- Assertion 1 of 4
- 3 assertion(s) not evaluated after this failure
- Operator: `==`
- Actual: `False`
- Expected: `True`

**Called Symbols:**
- `is_palindrome` → `src/string_utils.py::is_palindrome` (src/string_utils.py:56)

**Inferred Source Module:** `src/string_utils.py`

**Traceback:**
```
  tests/test_string_utils.py:40 in 
    assert is_palindrome("racecar") == TrueE   AssertionError: assert False == TrueE    +  where False = is_palindrome('racecar')
```

**Test Code:**
```python
def test_is_palindrome():
    """Test palindrome detection - this should FAIL."""
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("A man a plan a canal Panama") == True
    assert is_palindrome("not a palindrome") == False
```

**Source Snapshot (is_palindrome):**
```python
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
```

**Rerun Command:** `pytest "tests/test_string_utils.py::test_is_palindrome"`

---

---

**Note:** Validate patches by re-running the full test node IDs, not just the failing assertion
