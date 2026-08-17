# Python Version Compatibility Guide

## Issue: Python 3.13 Compatibility

You're using **Python 3.13**, which was released very recently. Some packages (particularly pydantic-core) have compatibility issues with this new version.

## Recommended Solution: Use Python 3.11 or 3.12

### Option 1: Install Python 3.12 (Recommended)

1. **Download Python 3.12**:
   - Visit: https://www.python.org/downloads/
   - Download Python 3.12.x (latest stable 3.12 version)

2. **Install Python 3.12**:
   - Run the installer
   - ✅ **Check "Add Python to PATH"**
   - Choose "Customize installation"
   - Install for all users (optional)

3. **Verify Installation**:
   ```bash
   py -3.12 --version
   # Should show: Python 3.12.x
   ```

4. **Create Virtual Environment with Python 3.12**:
   ```bash
   # In your project directory
   cd s:\Programming\4o4PR\backend
   
   # Create venv with Python 3.12
   py -3.12 -m venv venv312
   
   # Activate it
   venv312\Scripts\activate
   
   # Verify version
   python --version
   # Should show: Python 3.12.x
   ```

5. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Option 2: Use Python 3.11

Same steps as above, but use Python 3.11:
```bash
py -3.11 -m venv venv311
venv311\Scripts\activate
pip install -r requirements.txt
```

### Option 3: Try Updated Dependencies with Python 3.13

I've updated `requirements.txt` with newer package versions that may work with Python 3.13. Try:

```bash
# Make sure you're in backend directory
cd s:\Programming\4o4PR\backend

# Upgrade pip first
python -m pip install --upgrade pip

# Try installing again
pip install -r requirements.txt
```

If this still fails, **use Python 3.12** (Option 1).

## Quick Fix Commands

### Windows with Multiple Python Versions

```powershell
# List installed Python versions
py --list

# Use specific version
py -3.12 -m venv venv
venv\Scripts\activate

# Or
py -3.11 -m venv venv
venv\Scripts\activate
```

### After Creating Virtual Environment

```bash
# Activate virtual environment
venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Verify installation
python verify_bug_detector.py
```

## Why This Happens

- **Python 3.13** is very new (released October 2024)
- Many Python packages use compiled extensions (like pydantic-core)
- These packages need time to build wheels for new Python versions
- The `ForwardRef._evaluate()` API changed in Python 3.13

## Verification After Installation

Once installed, verify everything works:

```bash
# Test Python version
python --version

# Test pytest
pytest --version

# Test imports
python -c "from app.agents import BugDetector; print('✓ Import successful')"

# Run verification script
python verify_bug_detector.py

# Run tests
pytest tests/test_bug_detector.py -v
```

## Recommended Python Version

✅ **Python 3.12** - Best compatibility  
✅ **Python 3.11** - Fully stable  
⚠️ **Python 3.13** - Too new, limited package support  
❌ **Python 3.10 or older** - Works but outdated  

## If You Can't Install Another Python Version

Try installing packages one by one to identify the problematic one:

```bash
# Install core packages first
pip install pytest

# Try pydantic separately with latest version
pip install pydantic>=2.10

# Install FastAPI
pip install fastapi uvicorn

# Install remaining packages
pip install anthropic PyGithub docker httpx requests python-dotenv
```

## Common Error Messages

### "ForwardRef._evaluate() missing 1 required keyword-only argument"
**Solution**: Use Python 3.12 or 3.11

### "Failed building wheel for pydantic-core"
**Solution**: Use Python 3.12 or 3.11, or wait for updated wheel

### "No matching distribution found"
**Solution**: Package not available for Python 3.13 yet

## Need Help?

If you continue having issues:

1. Check your Python version: `python --version`
2. Try creating a new virtual environment with Python 3.12
3. Clear pip cache: `pip cache purge`
4. Update pip: `python -m pip install --upgrade pip`

## Summary

**For immediate success:**
1. Install Python 3.12
2. Create new virtual environment with Python 3.12
3. Install requirements.txt
4. Run verification script

This will save you time and frustration! 🚀
