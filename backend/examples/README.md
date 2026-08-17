# Bug Detector Examples

This folder contains sample Python code with intentional bugs for testing the Bug Detector.

## Structure

Each example folder should follow this structure:

```
example_name/
├── src/                  # Source code (with intentional bugs)
│   ├── __init__.py
│   └── module.py
└── tests/               # Test files (that will fail)
    ├── __init__.py
    └── test_module.py
```

## Available Examples

### `sample_bugs/`
Contains basic Python functions with intentional bugs:
- **calculator.py**: Math operations with bugs (subtract, divide, modulo)
- **string_utils.py**: String operations with bugs (reverse, count_vowels, is_palindrome)

Expected failures: 6 bugs across 6 test failures

## Running Bug Detection

### Scan All Examples
```bash
cd backend
python run_bug_detector.py
```

### Scan Specific Example
```bash
cd backend
python run_bug_detector.py sample_bugs
```

### List Available Examples
```bash
cd backend
python run_bug_detector.py --list
```

## Creating Your Own Examples

1. Create a new folder in `backend/examples/`
2. Add your buggy Python code in `src/`
3. Add failing tests in `tests/`
4. Run the bug detector to generate reports

Example:
```bash
mkdir backend/examples/my_bugs
mkdir backend/examples/my_bugs/src
mkdir backend/examples/my_bugs/tests

# Add your code and tests
# Then run:
python run_bug_detector.py my_bugs
```

## Output

Reports are saved to `backend/evaluation/results/`:
- **JSON reports**: Machine-readable format
- **Markdown reports**: Human-readable format
- **Terminal output**: Immediate feedback

## Tips

- Each example should be a complete, runnable Python project
- Tests should be discoverable by pytest
- Bugs should be intentional and clear
- Add comments marking where the bugs are
