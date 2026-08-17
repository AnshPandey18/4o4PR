"""Example usage of the Bug Detector module.

This demonstrates how the Patch Generator (Step 2) will use the Bug Detector.
"""

from pathlib import Path
from app.agents import BugDetector


def main():
    """Run bug detection on a sample repository."""
    
    # Initialize the detector
    detector = BugDetector(context_lines=5)
    
    # Example 1: Detect bugs in a repository
    print("=" * 70)
    print("Example 1: Running bug detection on a repository")
    print("=" * 70)
    
    try:
        # Replace with actual repo path
        repo_path = "/path/to/your/python/repo"
        
        # Run detection
        result = detector.run(repo_path)
        
        # Check results
        print(f"\nTest Results:")
        print(f"  Total tests run: {result.total_tests_run}")
        print(f"  Total failures: {result.total_failures}")
        print(f"  Pytest exit code: {result.pytest_exit_code}")
        
        if result.has_failures:
            print(f"\n{len(result.bugs)} bug(s) detected:\n")
            
            for i, bug in enumerate(result.bugs, 1):
                print(f"Bug #{i}:")
                print(f"  Test: {bug.test_name}")
                print(f"  Error Type: {bug.error_type}")
                print(f"  Error Message: {bug.error_message}")
                print(f"  Location: {bug.file_path}:{bug.line_number}")
                print(f"\n  Failing Function Code:")
                print("  " + "\n  ".join(bug.failing_function_code.splitlines()))
                
                if bug.context_before:
                    print(f"\n  Context Before:")
                    print("  " + "\n  ".join(bug.context_before.splitlines()[:3]))
                
                if bug.context_after:
                    print(f"\n  Context After:")
                    print("  " + "\n  ".join(bug.context_after.splitlines()[:3]))
                
                print("\n" + "-" * 70)
        else:
            print("\n✓ No bugs detected! All tests passed.")
    
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Run specific test files
    print("\n" + "=" * 70)
    print("Example 2: Running specific test files")
    print("=" * 70)
    
    try:
        result = detector.run(
            repo_path,
            test_files=["tests/test_math.py", "tests/test_utils.py"]
        )
        print(f"Detected {len(result.bugs)} bugs in specified test files")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 3: Custom pytest arguments
    print("\n" + "=" * 70)
    print("Example 3: Using custom pytest arguments")
    print("=" * 70)
    
    try:
        result = detector.run(
            repo_path,
            pytest_args=["-v", "--tb=long", "-x"]  # Stop after first failure
        )
        print(f"Detected {len(result.bugs)} bugs with custom pytest args")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 4: Integration with Patch Generator (Step 2)
    print("\n" + "=" * 70)
    print("Example 4: How Step 2 (Patch Generator) will use this")
    print("=" * 70)
    
    print("""
    # In your Patch Generator module:
    from app.agents import BugDetector
    
    class PatchGenerator:
        def __init__(self):
            self.bug_detector = BugDetector()
        
        def generate_fixes(self, repo_path):
            # Step 1: Detect bugs
            result = self.bug_detector.run(repo_path)
            
            if not result.has_failures:
                return "No bugs to fix!"
            
            # Step 2: For each bug, generate a patch
            patches = []
            for bug in result.bugs:
                patch = self._generate_patch_for_bug(bug)
                patches.append(patch)
            
            return patches
        
        def _generate_patch_for_bug(self, bug):
            # Use bug.failing_function_code to understand the bug
            # Use bug.error_message to know what's expected
            # Use bug.context_before/after for surrounding code
            # Generate and return a patch
            pass
    """)


def example_bug_report_structure():
    """Show the structure of a BugReport object."""
    print("\n" + "=" * 70)
    print("BugReport Structure (what you'll receive from detector.run())")
    print("=" * 70)
    
    print("""
    BugReport(
        test_name='tests/test_math.py::test_divide',
        error_type='AssertionError',
        error_message='assert 12 == 5',
        file_path='src/math_utils.py',
        line_number=13,
        failing_function_code='''
def divide(a, b):
    \"\"\"Divide a by b. BUG: returns addition instead.\"\"\"
    return a + b  # Bug: should be a / b
''',
        context_before='''
def subtract(a, b):
    \"\"\"Subtract b from a.\"\"\"
    return a - b
''',
        context_after='''
def multiply(a, b):
    \"\"\"Multiply two numbers.\"\"\"
    return a * b
''',
        traceback='...full stack trace...'
    )
    """)


if __name__ == "__main__":
    main()
    example_bug_report_structure()
