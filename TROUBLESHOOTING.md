# Troubleshooting Guide

## Problem: pip install fails with pydantic-core error

### Error Message
```
TypeError: ForwardRef._evaluate() missing 1 required keyword-only argument: 'recursive_guard'
Failed building wheel for pydantic-core
```

### Cause
You're using **Python 3.13**, which is too new. The pydantic-core package hasn't been updated for Python 3.13's API changes yet.

### Solution 1: Use Python 3.12 (RECOMMENDED)

**This is the fastest and most reliable solution.**

1. Download and install Python 3.12:
   - https://www.python.org/downloads/
   - Latest Python 3.12.x version

2. Create a new virtual environment:
   ```bash
   py -3.12 -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Verify:
   ```bash
   python verify_bug_detector.py
   ```

### Solution 2: Minimal Installation (Just pytest)

The Bug Detector only needs pytest to work! You can skip all other dependencies for now:

```bash
# Just install pytest
pip install pytest

# Test it works
python -c "import pytest; print('✓ Works!')"

# Run the verification
python verify_bug_detector.py
```

Or use the quick install script:
```bash
quick_install.bat
```

### Solution 3: Try Updated Packages

I've updated the requirements.txt with newer versions. Try:

```bash
# Clear pip cache
pip cache purge

# Upgrade pip
python -m pip install --upgrade pip

# Try again
pip install -r requirements.txt
```

If it still fails → Use Solution 1 (Python 3.12)

## Problem: "No module named 'app'"

### Error Message
```
ImportError: No module named 'app'
ModuleNotFoundError: No module named 'app'
```

### Solution
Make sure you're in the backend directory:

```bash
cd s:\Programming\4o4PR\backend
python verify_bug_detector.py
```

## Problem: pytest not found

### Error Message
```
'pytest' is not recognized as an internal or external command
pytest: command not found
```

### Solution
Install pytest:

```bash
pip install pytest
```

Or run through Python:
```bash
python -m pytest tests/test_bug_detector.py -v
```

## Problem: Tests fail to run

### Error Message
```
ERROR: file or directory not found: tests/test_bug_detector.py
```

### Solution
Make sure you're in the backend directory:

```bash
cd backend
pytest tests/test_bug_detector.py -v
```

## Problem: Virtual environment activation fails

### Windows PowerShell Error
```
cannot be loaded because running scripts is disabled
```

### Solution
Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating again:
```bash
venv\Scripts\activate
```

### Alternative
Use Command Prompt (cmd) instead:
```bash
venv\Scripts\activate.bat
```

## Problem: Multiple Python versions confusion

### Check Your Python Version
```bash
# Check default Python
python --version

# List all Python versions
py --list

# Use specific version
py -3.12 --version
py -3.11 --version
```

### Create venv with Specific Version
```bash
# Use Python 3.12
py -3.12 -m venv venv312
venv312\Scripts\activate

# Or Python 3.11
py -3.11 -m venv venv311
venv311\Scripts\activate
```

## Problem: Import errors even after installation

### Check if you're in the right directory
```bash
pwd  # or cd to see current directory
# Should be: s:\Programming\4o4PR\backend
```

### Check if __init__.py files exist
```bash
dir app\agents\__init__.py
dir app\models\__init__.py
```

If missing, they should be created (they're part of the deliverables).

## Problem: Tests pass but verification fails

### Symptom
Pytest runs fine but the verification script shows errors.

### Solution
The verification script creates a temporary repository and runs the detector on it. Check:

1. Do you have write permissions?
   ```bash
   python -c "import tempfile; print(tempfile.gettempdir())"
   ```

2. Is pytest actually working?
   ```bash
   pytest --version
   ```

3. Try running the example:
   ```bash
   python examples/bug_detector_example.py
   ```

## Quick Diagnostic Script

Run this to check your setup:

```bash
# Save as check_setup.py
import sys
import subprocess

print("Python Version:", sys.version)
print("Python Executable:", sys.executable)
print()

try:
    import pytest
    print("✓ pytest installed:", pytest.__version__)
except ImportError:
    print("✗ pytest NOT installed")

try:
    from app.agents import BugDetector
    print("✓ BugDetector can be imported")
except ImportError as e:
    print("✗ BugDetector import failed:", e)

try:
    result = subprocess.run(["pytest", "--version"], capture_output=True, text=True)
    print("✓ pytest command works")
except Exception as e:
    print("✗ pytest command failed:", e)
```

## Still Having Issues?

### For Bug Detector Development
**Minimum Requirements:**
- Python 3.11 or 3.12 (NOT 3.13)
- pytest
- Backend directory structure intact

**That's it!** The Bug Detector uses only Python standard library + pytest.

### For Full Stack Development
You'll need all dependencies in requirements.txt, which means:
- Python 3.12 (recommended)
- OR wait for package updates to support Python 3.13

## Step-by-Step Clean Installation

Starting from scratch:

```bash
# 1. Navigate to project
cd s:\Programming\4o4PR\backend

# 2. Remove old virtual environment if exists
rmdir /s venv  # Windows cmd
# or
Remove-Item -Recurse -Force venv  # PowerShell

# 3. Create fresh virtual environment with Python 3.12
py -3.12 -m venv venv

# 4. Activate it
venv\Scripts\activate

# 5. Upgrade pip
python -m pip install --upgrade pip

# 6. Install minimal requirements first
pip install pytest

# 7. Test Bug Detector
python verify_bug_detector.py

# 8. If that works, install full requirements
pip install -r requirements.txt
```

## Summary of Solutions

| Problem | Quick Fix |
|---------|-----------|
| pydantic-core build fails | Use Python 3.12 |
| Import errors | Check directory (must be in backend/) |
| pytest not found | `pip install pytest` |
| PowerShell script execution | `Set-ExecutionPolicy RemoteSigned` |
| Want to test quickly | Use `requirements-minimal.txt` |

## Documentation

- **Python version issues**: `PYTHON_VERSION_GUIDE.md`
- **Setup instructions**: `SETUP.md`
- **Quick start**: `app/agents/QUICK_START.md`
- **Full documentation**: `app/agents/README.md`

## Contact

If none of these solutions work, check:
1. Are you using Python 3.13? → Use 3.12
2. Are you in the backend/ directory? → cd there
3. Is pytest installed? → pip install pytest
4. Can you import pytest? → python -c "import pytest"

These 4 checks solve 95% of installation issues!
