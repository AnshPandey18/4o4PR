@echo off
echo ========================================
echo Bug Detector Quick Installation
echo ========================================
echo.

echo Checking Python version...
python --version
echo.

echo Installing minimal requirements (pytest only)...
python -m pip install --upgrade pip
pip install pytest>=8.0.0
echo.

echo Testing installation...
python -c "import pytest; print('✓ pytest installed successfully')"
echo.

echo Running verification...
python verify_bug_detector.py
echo.

echo ========================================
echo Installation complete!
echo ========================================
echo.
echo Next steps:
echo 1. If verification passed, you're ready to go!
echo 2. If you see errors, read PYTHON_VERSION_GUIDE.md
echo 3. For full features, install: pip install -r requirements.txt
echo.
pause
