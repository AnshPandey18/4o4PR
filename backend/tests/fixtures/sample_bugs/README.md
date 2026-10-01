# Sample Bugs Project

This is a test fixture containing intentionally buggy Python code for testing the 4o4PR bug detection and analysis pipeline.

## Structure

```
sample_bugs/
├── src/
│   ├── calculator.py      # 6 functions (3 buggy: subtract, divide, modulo)
│   └── string_utils.py    # 4 functions (3 buggy: reverse_string, count_vowels, is_palindrome)
├── tests/
│   ├── test_calculator.py # 7 tests (3 failing)
│   └── test_string_utils.py # 4 tests (3 failing)
└── pytest.ini
```

## Expected Test Results

- **Total Tests:** 10
- **Passing:** 4
- **Failing:** 6

## Intentional Bugs

### calculator.py

1. **subtract(a, b)** - Returns `a + b` instead of `a - b`
2. **divide(a, b)** - Returns `b / a` instead of `a / b`
3. **modulo(a, b)** - Returns `a % (b - 1)` instead of `a % b`

### string_utils.py

1. **reverse_string(s)** - Returns string unchanged instead of reversed
2. **count_vowels(s)** - Counts 'e' and 'E' twice
3. **is_palindrome(s)** - Doesn't ignore spaces and comparison is reversed

## Running Tests

From this directory:

```bash
pytest
```

Or from the backend directory:

```bash
pytest tests/fixtures/sample_bugs/
```

## Expected Grouping

When processed by the bug grouper, the 6 bugs should be grouped into 2 groups:

- **G1**: calculator.py (subtract, divide, modulo) - 3 bugs
- **G2**: string_utils.py (reverse_string, count_vowels, is_palindrome) - 3 bugs
