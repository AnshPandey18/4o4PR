# Bug Detection Report

## Run Information

- **Run ID:** eval_api_server_20261025_155829
- **Timestamp:** 2026-10-25T10:28:34.290459Z
- **Project Root:** .
- **Python Version:** 3.13.11
- **Pytest Version:** 9.1.1
- **Content Hash:** 34bab9ce7229ffcc...

## Summary

- **Total Tests Run:** 17

- **Total Failures:** 1

- **Total Errors:** 0

- **Tests Passed:** 16

- **Tests Skipped:** 0

- **Bugs Detected:** 1

- **Pytest Exit Code:** 1

- **Duration:** 0.21s

- **Consistency Check:** ✓ PASS

## Detected Bugs

### Bug #1: tests/test_services.py::test_create_user_validates_password

- **Bug ID:** `b_fdf12715614e`
- **Failure Kind:** assertion
- **Error Type:** AssertionError

**Error Message:**
```
assert True == False
```

**Location:**
- File: `tests/test_services.py`
- Line: 32

**Assertion Details:**
- Statement: `assert result == False`
- Line: 32
- Assertion 1 of 1
- Operator: `==`
- Actual: `True`
- Expected: `False`

**Called Symbols:**
- `UserService` → `src/services.py::UserService` (src/services.py:None)
- `create_user` (unresolved)

**Inferred Source Module:** `src/services.py`

**Traceback:**
```
  tests/test_services.py:32 in 
    def test_create_user_validates_password():        """Test password validation on creation."""        service = UserService()        result = service.create_user("testuser", "short", "test@example.com")>       assert result == FalseE       assert True == False
```

**Test Code:**
```python
def test_create_user_validates_password():
    """Test password validation on creation."""
    service = UserService()
    result = service.create_user("testuser", "short", "test@example.com")
    assert result == False
```

**Rerun Command:** `pytest "tests/test_services.py::test_create_user_validates_password"`

---

---

**Note:** Validate patches by re-running the full test node IDs, not just the failing assertion
