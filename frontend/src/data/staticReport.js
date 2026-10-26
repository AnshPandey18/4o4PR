/**
 * Static fallback report data — embedded directly from the latest on-disk run.
 * Used by Report.jsx when the backend is offline.
 * Source: backend/runs/r_20261004_220336/
 */

export const STATIC_RUN_ID = 'r_20261004_220336';

export const STATIC_BUG_REPORT = {
  run_id: 'r_20261004_220336',
  timestamp: '2026-10-04T16:33:53.692603Z',
  schema_version: '2.0',
  project: { python_version: '3.13.2', pytest_version: '9.1.1', root: '.' },
  summary: {
    bugs_detected: 6,
    tests_run: 11,
    passed: 5,
    failed: 6,
    errors: 0,
    skipped: 0,
    duration_seconds: 0.166,
    pytest_exit_code: 1,
    consistency_ok: true,
  },
  bugs: [
    {
      bug_id: 'b_056a5081c629',
      test_name: 'tests/test_calculator.py::test_subtract',
      error_type: 'Error',
      error_message: 'assert 8 == 2\n +  where 8 = subtract(5, 3)',
      failure_kind: 'assertion',
      inferred_source_module: 'src/calculator.py',
      location: { file_path: 'tests/test_calculator.py', line_number: 25 },
      first_failing_assertion: { statement: 'assert subtract(5, 3) == 2', expected: '2', actual: '8', operator: '==', line: 25, assert_total: 3, assertion_index: 1 },
      called_symbols: [{ file: 'src/calculator.py', name: 'subtract', line_start: 21, line_end: 33, resolution: 'resolved', symbol_id: 'src/calculator.py::subtract', source_snapshot: 'def subtract(a, b):\n    """Subtract b from a.\n\n    BUG: Returns a + b instead of a - b\n    """\n    return a + b  # BUG: Should be a - b' }],
      rerun_command: 'pytest "tests/test_calculator.py::test_subtract"',
      code: 'def test_subtract():\n    assert subtract(5, 3) == 2\n    assert subtract(10, 4) == 6\n    assert subtract(0, 5) == -5',
      flaky: false,
    },
    {
      bug_id: 'b_54e477c51122',
      test_name: 'tests/test_calculator.py::test_divide',
      error_type: 'Error',
      error_message: 'assert 0.2 == 5\n +  where 0.2 = divide(10, 2)',
      failure_kind: 'assertion',
      inferred_source_module: 'src/calculator.py',
      location: { file_path: 'tests/test_calculator.py', line_number: 39 },
      first_failing_assertion: { statement: 'assert divide(10, 2) == 5', expected: '5', actual: '0.2', operator: '==', line: 39, assert_total: 3, assertion_index: 1 },
      called_symbols: [{ file: 'src/calculator.py', name: 'divide', line_start: 49, line_end: 66, resolution: 'resolved', symbol_id: 'src/calculator.py::divide', source_snapshot: 'def divide(a, b):\n    """Divide a by b.\n\n    BUG: Returns b / a instead of a / b\n    """\n    if b == 0:\n        raise ZeroDivisionError("Cannot divide by zero")\n    return b / a  # BUG: Should be a / b' }],
      rerun_command: 'pytest "tests/test_calculator.py::test_divide"',
      code: 'def test_divide():\n    assert divide(10, 2) == 5\n    assert divide(9, 3) == 3\n    assert divide(7, 2) == 3.5',
      flaky: false,
    },
    {
      bug_id: 'b_bd675980c5ec',
      test_name: 'tests/test_calculator.py::test_modulo',
      error_type: 'Error',
      error_message: 'assert 0 == 1\n +  where 0 = modulo(10, 3)',
      failure_kind: 'assertion',
      inferred_source_module: 'src/calculator.py',
      location: { file_path: 'tests/test_calculator.py', line_number: 62 },
      first_failing_assertion: { statement: 'assert modulo(10, 3) == 1', expected: '1', actual: '0', operator: '==', line: 62, assert_total: 3, assertion_index: 1 },
      called_symbols: [{ file: 'src/calculator.py', name: 'modulo', line_start: 82, line_end: 99, resolution: 'resolved', symbol_id: 'src/calculator.py::modulo', source_snapshot: 'def modulo(a, b):\n    """Calculate a modulo b.\n\n    BUG: Returns a % (b - 1) instead of a % b\n    """\n    if b == 0:\n        raise ZeroDivisionError("Cannot modulo by zero")\n    return a % (b - 1)  # BUG: Should be a % b' }],
      rerun_command: 'pytest "tests/test_calculator.py::test_modulo"',
      code: 'def test_modulo():\n    assert modulo(10, 3) == 1\n    assert modulo(15, 4) == 3\n    assert modulo(7, 5) == 2',
      flaky: false,
    },
    {
      bug_id: 'b_e6f0145b1e87',
      test_name: 'tests/test_string_utils.py::test_reverse_string',
      error_type: 'AssertionError',
      error_message: "assert 'hello' == 'olleh'",
      failure_kind: 'assertion',
      inferred_source_module: 'src/string_utils.py',
      location: { file_path: 'tests/test_string_utils.py', line_number: 18 },
      first_failing_assertion: { statement: 'assert reverse_string("hello") == "olleh"', expected: "'olleh'", actual: "'hello'", operator: '==', line: 18, assert_total: 3, assertion_index: 1 },
      called_symbols: [{ file: 'src/string_utils.py', name: 'reverse_string', line_start: 8, line_end: 19, resolution: 'resolved', symbol_id: 'src/string_utils.py::reverse_string', source_snapshot: 'def reverse_string(s):\n    """Reverse a string.\n\n    BUG: Returns the string unchanged instead of reversed\n    """\n    return s  # BUG: Should be s[::-1]' }],
      rerun_command: 'pytest "tests/test_string_utils.py::test_reverse_string"',
      code: 'def test_reverse_string():\n    assert reverse_string("hello") == "olleh"\n    assert reverse_string("world") == "dlrow"\n    assert reverse_string("") == ""',
      flaky: false,
    },
    {
      bug_id: 'b_3d27458021e3',
      test_name: 'tests/test_string_utils.py::test_count_vowels',
      error_type: 'AssertionError',
      error_message: "assert 3 == 2\n +  where 3 = count_vowels('hello')",
      failure_kind: 'assertion',
      inferred_source_module: 'src/string_utils.py',
      location: { file_path: 'tests/test_string_utils.py', line_number: 32 },
      first_failing_assertion: { statement: 'assert count_vowels("hello") == 2  # e, o', expected: '2', actual: '3', operator: '==', line: 32, assert_total: 4, assertion_index: 1 },
      called_symbols: [{ file: 'src/string_utils.py', name: 'count_vowels', line_start: 34, line_end: 53, resolution: 'resolved', symbol_id: 'src/string_utils.py::count_vowels', source_snapshot: 'def count_vowels(s):\n    """Count the number of vowels in a string.\n\n    BUG: Counts \'e\' twice\n    """\n    vowels = \'aeiouAEIOU\'\n    count = 0\n    for char in s:\n        if char in vowels:\n            count += 1\n        if char in \'eE\':\n            count += 1\n    return count' }],
      rerun_command: 'pytest "tests/test_string_utils.py::test_count_vowels"',
      code: 'def test_count_vowels():\n    assert count_vowels("hello") == 2  # e, o\n    assert count_vowels("AEIOU") == 5\n    assert count_vowels("xyz") == 0',
      flaky: false,
    },
    {
      bug_id: 'b_c283258e46bb',
      test_name: 'tests/test_string_utils.py::test_is_palindrome',
      error_type: 'AssertionError',
      error_message: 'assert False == True\n +  where False = is_palindrome(\'racecar\')',
      failure_kind: 'assertion',
      inferred_source_module: 'src/string_utils.py',
      location: { file_path: 'tests/test_string_utils.py', line_number: 40 },
      first_failing_assertion: { statement: 'assert is_palindrome("racecar") == True', expected: 'True', actual: 'False', operator: '==', line: 40, assert_total: 4, assertion_index: 1 },
      called_symbols: [{ file: 'src/string_utils.py', name: 'is_palindrome', line_start: 56, line_end: 70, resolution: 'resolved', symbol_id: 'src/string_utils.py::is_palindrome', source_snapshot: "def is_palindrome(s):\n    \"\"\"Check if a string is a palindrome.\n\n    BUG: Comparison logic is reversed\n    \"\"\"\n    s_lower = s.lower()\n    return s_lower != s_lower[::-1]  # BUG: Should be ==" }],
      rerun_command: 'pytest "tests/test_string_utils.py::test_is_palindrome"',
      code: 'def test_is_palindrome():\n    assert is_palindrome("racecar") == True\n    assert is_palindrome("hello") == False\n    assert is_palindrome("A man a plan a canal Panama") == True',
      flaky: false,
    },
  ],
};

export const STATIC_BASELINE_RESULTS = {
  run_id: 'r_20261004_220336',
  schema_version: '1.0',
  results: {
    'tests/test_calculator.py::test_add': 'passed',
    'tests/test_calculator.py::test_divide': 'failed',
    'tests/test_calculator.py::test_divide_by_zero': 'passed',
    'tests/test_calculator.py::test_modulo': 'failed',
    'tests/test_calculator.py::test_multiply': 'passed',
    'tests/test_calculator.py::test_power': 'passed',
    'tests/test_calculator.py::test_subtract': 'failed',
    'tests/test_string_utils.py::test_capitalize_words': 'passed',
    'tests/test_string_utils.py::test_count_vowels': 'failed',
    'tests/test_string_utils.py::test_is_palindrome': 'failed',
    'tests/test_string_utils.py::test_reverse_string': 'failed',
  },
};

export const STATIC_MD_CONTENT = `# Bug Detection Report

## Run Information

- **Run ID:** r_20261004_220336
- **Timestamp:** 2026-10-04T16:33:53Z
- **Python Version:** 3.13.2
- **Pytest Version:** 9.1.1

## Summary

- **Total Tests Run:** 11
- **Total Failures:** 6
- **Tests Passed:** 5
- **Bugs Detected:** 6
- **Duration:** 0.17s
- **Consistency Check:** ✓ PASS

---

## Detected Bugs

### Bug #1: tests/test_calculator.py::test_subtract

- **Bug ID:** \`b_056a5081c629\`
- **Error Type:** AssertionError
- **Inferred Source:** \`src/calculator.py\`

**Error Message:**
\`\`\`
assert 8 == 2
 +  where 8 = subtract(5, 3)
\`\`\`

**Root Cause:** \`subtract()\` returns \`a + b\` instead of \`a - b\`

**Rerun:** \`pytest "tests/test_calculator.py::test_subtract"\`

---

### Bug #2: tests/test_calculator.py::test_divide

- **Bug ID:** \`b_54e477c51122\`
- **Error Type:** AssertionError
- **Inferred Source:** \`src/calculator.py\`

**Error Message:**
\`\`\`
assert 0.2 == 5
 +  where 0.2 = divide(10, 2)
\`\`\`

**Root Cause:** \`divide()\` returns \`b / a\` instead of \`a / b\`

**Rerun:** \`pytest "tests/test_calculator.py::test_divide"\`

---

### Bug #3: tests/test_calculator.py::test_modulo

- **Bug ID:** \`b_bd675980c5ec\`
- **Error Type:** AssertionError
- **Inferred Source:** \`src/calculator.py\`

**Error Message:**
\`\`\`
assert 0 == 1
 +  where 0 = modulo(10, 3)
\`\`\`

**Root Cause:** \`modulo()\` returns \`a % (b - 1)\` instead of \`a % b\`

**Rerun:** \`pytest "tests/test_calculator.py::test_modulo"\`

---

### Bug #4: tests/test_string_utils.py::test_reverse_string

- **Bug ID:** \`b_e6f0145b1e87\`
- **Error Type:** AssertionError
- **Inferred Source:** \`src/string_utils.py\`

**Error Message:**
\`\`\`
assert 'hello' == 'olleh'
\`\`\`

**Root Cause:** \`reverse_string()\` returns \`s\` unchanged instead of \`s[::-1]\`

**Rerun:** \`pytest "tests/test_string_utils.py::test_reverse_string"\`

---

### Bug #5: tests/test_string_utils.py::test_count_vowels

- **Bug ID:** \`b_3d27458021e3\`
- **Error Type:** AssertionError
- **Inferred Source:** \`src/string_utils.py\`

**Error Message:**
\`\`\`
assert 3 == 2
 +  where 3 = count_vowels('hello')
\`\`\`

**Root Cause:** \`count_vowels()\` double-counts 'e' and 'E' characters

**Rerun:** \`pytest "tests/test_string_utils.py::test_count_vowels"\`

---

### Bug #6: tests/test_string_utils.py::test_is_palindrome

- **Bug ID:** \`b_c283258e46bb\`
- **Error Type:** AssertionError
- **Inferred Source:** \`src/string_utils.py\`

**Error Message:**
\`\`\`
assert False == True
 +  where False = is_palindrome('racecar')
\`\`\`

**Root Cause:** \`is_palindrome()\` uses \`!=\` instead of \`==\` — comparison logic is inverted

**Rerun:** \`pytest "tests/test_string_utils.py::test_is_palindrome"\`

---

*Note: Validate patches by re-running the full test node IDs listed above.*
`;

export const STATIC_RUNS_DIR_LIST = [
  { run_dir: 'r_20261004_220336', has_markdown: true, files: ['detector/bug_report.json', 'detector/baseline_results.json', 'grouping/bug_groups.json', 'index/index.json'] },
  { run_dir: 'r_20261004_215604', has_markdown: true, files: ['detector/bug_report.json', 'detector/baseline_results.json', 'grouping/bug_groups.json', 'index/index.json'] },
  { run_dir: 'r_20261004_214835', has_markdown: true, files: ['detector/bug_report.json', 'detector/baseline_results.json', 'grouping/bug_groups.json', 'index/index.json'] },
  { run_dir: 'r_20261004_214052', has_markdown: true, files: ['detector/bug_report.json', 'detector/baseline_results.json', 'grouping/bug_groups.json', 'index/index.json'] },
  { run_dir: 'r_20261004_213624', has_markdown: true, files: ['detector/bug_report.json', 'detector/baseline_results.json', 'grouping/bug_groups.json', 'index/index.json'] },
];
