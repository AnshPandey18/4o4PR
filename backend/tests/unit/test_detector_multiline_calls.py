"""Tests for detector multi-line call detection.

Created: 2026-10-24
Reason: Approved C - Fix detector to find calls on previous lines before assertion
"""

import pytest
import tempfile
from pathlib import Path
from detector.detector import BugDetector


class TestMultiLineCallDetection:
    """Test that detector finds calls on lines before the assertion."""
    
    def test_call_on_previous_line(self):
        """Test call on line before assertion is detected."""
        # Create a temporary test file
        test_code = '''
def test_create_user_validates_password():
    """Test password validation on creation."""
    service = UserService()
    result = service.create_user("testuser", "short", "test@example.com")
    assert result == False
'''
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            test_file = project_root / "test_services.py"
            test_file.write_text(test_code)
            
            # Create service file that would be imported
            src_dir = project_root / "src"
            src_dir.mkdir()
            (src_dir / "services.py").write_text('''
class UserService:
    def create_user(self, username, password, email):
        if len(password) < 8:
            return False
        return True
    
    def _validate_user(self, user):
        return user is not None
''')
            
            # Create detector instance
            detector = BugDetector(project_root=project_root, import_roots=[src_dir])
            
            # Create mock first_assertion
            from detector.models import FailureAssertion
            first_assertion = FailureAssertion(
                line=6,  # assert result == False
                statement="assert result == False",
                operator="==",
                expected="False",
                actual="True",
                assert_total=1,
                assertion_index=1,
                assertions_not_evaluated=0
            )
            
            # Call the resolver
            called_symbols = detector._resolve_called_symbols(
                file_path="test_services.py",
                test_name="test_create_user_validates_password",
                first_assertion=first_assertion
            )
            
            # Should find create_user call from line 5
            assert len(called_symbols) > 0, "Should detect calls from previous lines"
            
            # Check that create_user was found
            symbol_names = [s.name for s in called_symbols]
            assert 'create_user' in symbol_names, f"Should find create_user, got: {symbol_names}"
    
    def test_call_split_across_lines(self):
        """Test call split across multiple lines is detected."""
        test_code = '''
def test_long_function_call():
    """Test with call split across lines."""
    result = some_function(
        arg1="value1",
        arg2="value2",
        arg3="value3"
    )
    assert result is not None
'''
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            test_file = project_root / "test_multiline.py"
            test_file.write_text(test_code)
            
            # Create module with the function
            (project_root / "module.py").write_text('''
def some_function(arg1, arg2, arg3):
    return arg1 + arg2 + arg3
''')
            
            detector = BugDetector(project_root=project_root, import_roots=[project_root])
            
            from detector.models import FailureAssertion
            first_assertion = FailureAssertion(
                line=9,  # assert result is not None
                statement="assert result is not None",
                operator="is not",
                expected="not None",
                actual="None",
                assert_total=1,
                assertion_index=1,
                assertions_not_evaluated=0
            )
            
            called_symbols = detector._resolve_called_symbols(
                file_path="test_multiline.py",
                test_name="test_long_function_call",
                first_assertion=first_assertion
            )
            
            # Should find some_function call
            symbol_names = [s.name for s in called_symbols]
            assert 'some_function' in symbol_names, f"Should find some_function, got: {symbol_names}"
    
    def test_call_in_assertion_still_works(self):
        """Test that calls directly in assertion still work."""
        test_code = '''
def test_inline_call():
    """Test with call in assertion."""
    assert calculate_sum([1, 2, 3]) == 6
'''
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            test_file = project_root / "test_inline.py"
            test_file.write_text(test_code)
            
            (project_root / "math_utils.py").write_text('''
def calculate_sum(values):
    return sum(values)
''')
            
            detector = BugDetector(project_root=project_root, import_roots=[project_root])
            
            from detector.models import FailureAssertion
            first_assertion = FailureAssertion(
                line=4,  # assert calculate_sum([1, 2, 3]) == 6
                statement="assert calculate_sum([1, 2, 3]) == 6",
                operator="==",
                expected="6",
                actual="5",
                assert_total=1,
                assertion_index=1,
                assertions_not_evaluated=0
            )
            
            called_symbols = detector._resolve_called_symbols(
                file_path="test_inline.py",
                test_name="test_inline_call",
                first_assertion=first_assertion
            )
            
            # Should find calculate_sum
            symbol_names = [s.name for s in called_symbols]
            assert 'calculate_sum' in symbol_names, f"Should find calculate_sum, got: {symbol_names}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

