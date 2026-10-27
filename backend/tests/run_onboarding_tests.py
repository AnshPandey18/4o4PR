#!/usr/bin/env python
"""
Quick test runner for repository onboarding workflow.

Runs automated tests and generates a summary report.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime


def print_header(title: str):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def run_command(cmd: list, description: str) -> bool:
    """Run command and return success status."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"   ✅ Success")
            return True
        else:
            print(f"   ❌ Failed")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⏱️  Timeout (5 minutes)")
        return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def main():
    """Main test runner."""
    print_header("4o4PR Repository Onboarding Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Test 1: Orchestrator DB unit tests
    print_header("Test 1: OrchestratorDB Unit Tests")
    results["orchestrator_unit"] = run_command(
        [sys.executable, "-m", "pytest", "tests/test_orchestrator_db_onboarding.py", "-v"],
        "Running OrchestratorDB tests"
    )
    
    # Test 2: API integration tests
    print_header("Test 2: API Integration Tests")
    results["api_integration"] = run_command(
        [sys.executable, "-m", "pytest", "tests/test_api_repository_onboarding.py", "-v"],
        "Running API tests"
    )
    
    # Test 3: Validation tests
    print_header("Test 3: Input Validation Tests")
    results["validation"] = run_command(
        [sys.executable, "-m", "pytest", "tests/test_orchestrator_db_onboarding.py::TestRepositoryValidation", "-v"],
        "Running validation tests"
    )
    
    # Test 4: CLI interface
    print_header("Test 4: CLI Interface Tests")
    results["cli"] = run_command(
        [sys.executable, "-m", "pytest", "tests/test_orchestrator_db_onboarding.py::TestCLIInterface", "-v"],
        "Running CLI tests"
    )
    
    # Generate summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print()
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test_name}")
    
    print()
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exit with appropriate code
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
