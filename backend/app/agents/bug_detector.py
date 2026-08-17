"""Bug Detector module for identifying failing tests and extracting code context."""

import ast
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from app.models.schemas import BugReport, BugDetectionResult


class BugDetectorError(Exception):
    """Base exception for Bug Detector errors."""
    pass


class RepositoryNotFoundError(BugDetectorError):
    """Raised when the target repository path does not exist."""
    pass


class PytestNotInstalledError(BugDetectorError):
    """Raised when pytest is not available in the environment."""
    pass


class BugDetector:
    """Detects failing tests in a Python repository and extracts relevant code context.
    
    This class orchestrates the bug detection pipeline:
    1. Run pytest on the target repository
    2. Parse test output to identify failures
    3. Extract code context for each failure
    4. Return structured bug reports
    
    Usage:
        detector = BugDetector()
        result = detector.run("/path/to/repo")
        for bug in result.bugs:
            print(f"Bug in {bug.file_path}:{bug.line_number}")
    """
    
    def __init__(self, context_lines: int = 5):
        """Initialize the Bug Detector.
        
        Args:
            context_lines: Number of lines to extract before/after the failing function
        """
        self.context_lines = context_lines
    
    def run(
        self,
        repo_path: str,
        test_files: Optional[List[str]] = None,
        pytest_args: Optional[List[str]] = None
    ) -> BugDetectionResult:
        """Run bug detection on a repository.
        
        Args:
            repo_path: Path to the target repository (local directory)
            test_files: Optional list of specific test files to run (relative to repo_path)
            pytest_args: Optional additional arguments to pass to pytest
            
        Returns:
            BugDetectionResult containing list of bug reports and metadata
            
        Raises:
            RepositoryNotFoundError: If repo_path does not exist
            PytestNotInstalledError: If pytest is not available
        """
        repo_path = Path(repo_path).resolve()
        self._validate_repository(repo_path)
        self._check_pytest_available()
        
        # Run pytest and capture output
        exit_code, pytest_output = self._run_pytest(repo_path, test_files, pytest_args)
        
        # Parse pytest output to extract failure information
        failures = self._parse_pytest_output(pytest_output)
        
        # Extract code context for each failure
        bugs = []
        for failure_info in failures:
            try:
                bug_report = self._create_bug_report(repo_path, failure_info)
                bugs.append(bug_report)
            except Exception as e:
                # Log error but continue processing other failures
                print(f"Warning: Failed to create bug report for {failure_info.get('test_name')}: {e}")
        
        # Extract test statistics
        total_tests, total_failures = self._extract_test_stats(pytest_output)
        
        return BugDetectionResult(
            bugs=bugs,
            total_tests_run=total_tests,
            total_failures=total_failures,
            pytest_exit_code=exit_code
        )
    
    def _validate_repository(self, repo_path: Path) -> None:
        """Validate that the repository path exists and is a directory.
        
        Args:
            repo_path: Path to validate
            
        Raises:
            RepositoryNotFoundError: If path does not exist or is not a directory
        """
        if not repo_path.exists():
            raise RepositoryNotFoundError(f"Repository path does not exist: {repo_path}")
        if not repo_path.is_dir():
            raise RepositoryNotFoundError(f"Repository path is not a directory: {repo_path}")
    
    def _check_pytest_available(self) -> None:
        """Check if pytest is available in the environment.
        
        Raises:
            PytestNotInstalledError: If pytest command is not found
        """
        try:
            subprocess.run(
                ["pytest", "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise PytestNotInstalledError(
                "pytest is not installed or not available in PATH. "
                "Install it with: pip install pytest"
            )
    
    def _run_pytest(
        self,
        repo_path: Path,
        test_files: Optional[List[str]],
        pytest_args: Optional[List[str]]
    ) -> Tuple[int, str]:
        """Run pytest on the repository and capture output.
        
        Args:
            repo_path: Path to the repository
            test_files: Optional list of test files to run
            pytest_args: Optional additional pytest arguments
            
        Returns:
            Tuple of (exit_code, output_string)
        """
        cmd = ["pytest", "-v", "--tb=short"]
        
        # Add custom arguments if provided
        if pytest_args:
            cmd.extend(pytest_args)
        
        # Add specific test files if provided
        if test_files:
            cmd.extend(test_files)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            # Combine stdout and stderr for complete output
            output = result.stdout + "\n" + result.stderr
            return result.returncode, output
        except subprocess.TimeoutExpired:
            raise BugDetectorError("Pytest execution timed out after 5 minutes")
        except Exception as e:
            raise BugDetectorError(f"Failed to run pytest: {e}")
    
    def _parse_pytest_output(self, output: str) -> List[dict]:
        """Parse pytest output to extract failure information.
        
        Args:
            output: Raw pytest output string
            
        Returns:
            List of dicts with keys: test_name, error_type, error_message, 
            file_path, line_number, traceback
        """
        failures = []
        
        # Pattern to match test failures in verbose mode
        # Example: tests/test_math.py::test_divide FAILED
        test_pattern = re.compile(r'^(.+?)::(.*?)\s+FAILED', re.MULTILINE)
        
        # Find all failed tests
        failed_tests = test_pattern.findall(output)
        
        if not failed_tests:
            return []
        
        # Split output by test sections to extract detailed error info
        # Look for the FAILURES section
        failures_section_match = re.search(
            r'=+ FAILURES =+(.+?)(?:=+ .+ =+|$)',
            output,
            re.DOTALL
        )
        
        if not failures_section_match:
            # No detailed failure section, return basic info
            for test_file, test_name in failed_tests:
                failures.append({
                    'test_name': f"{test_file}::{test_name}",
                    'error_type': 'Unknown',
                    'error_message': 'Test failed (no details available)',
                    'file_path': '',
                    'line_number': 0,
                    'traceback': ''
                })
            return failures
        
        failures_section = failures_section_match.group(1)
        
        # Parse each failure section
        # Pattern: _ TestName _ followed by error details
        failure_blocks = re.split(r'_+ (.*?) _+', failures_section)[1:]
        
        # Process pairs of (test_name, details)
        for i in range(0, len(failure_blocks), 2):
            if i + 1 >= len(failure_blocks):
                break
                
            test_name = failure_blocks[i].strip()
            details = failure_blocks[i + 1]
            
            # Extract file path and line number from traceback
            # Pattern: file.py:123: in function_name
            traceback_pattern = re.compile(r'([^\s]+\.py):(\d+):', re.MULTILINE)
            matches = traceback_pattern.findall(details)
            
            if matches:
                # Get the last file/line in the traceback (usually the actual error location)
                file_path, line_number = matches[-1]
                line_number = int(line_number)
            else:
                file_path, line_number = '', 0
            
            # Extract error type and message
            # Pattern: ErrorType: message or E       assert statement
            error_match = re.search(
                r'(?:([A-Z]\w+(?:Error|Exception|Warning)):\s*(.+?)(?=\n[^\s]|\n\n|$))|'
                r'(?:E\s+(assert.+?)(?=\n[^\sE]|\n\n|$))',
                details,
                re.DOTALL
            )
            
            if error_match:
                if error_match.group(1):  # Exception format
                    error_type = error_match.group(1)
                    error_message = error_match.group(2).strip()
                else:  # Assert format
                    error_type = 'AssertionError'
                    error_message = error_match.group(3).strip()
            else:
                error_type = 'Unknown'
                error_message = 'Test failed'
            
            failures.append({
                'test_name': test_name,
                'error_type': error_type,
                'error_message': error_message,
                'file_path': file_path,
                'line_number': line_number,
                'traceback': details.strip()
            })
        
        return failures
    
    def _create_bug_report(self, repo_path: Path, failure_info: dict) -> BugReport:
        """Create a structured bug report from failure information.
        
        Args:
            repo_path: Path to the repository
            failure_info: Dict containing parsed failure information
            
        Returns:
            BugReport object with extracted code context
        """
        file_path = failure_info['file_path']
        line_number = failure_info['line_number']
        
        # Extract code context
        function_code, context_before, context_after = self._extract_code_context(
            repo_path, file_path, line_number
        )
        
        return BugReport(
            test_name=failure_info['test_name'],
            error_type=failure_info['error_type'],
            error_message=failure_info['error_message'],
            file_path=file_path,
            line_number=line_number,
            failing_function_code=function_code,
            context_before=context_before,
            context_after=context_after,
            traceback=failure_info.get('traceback')
        )
    
    def _extract_code_context(
        self,
        repo_path: Path,
        file_path: str,
        line_number: int
    ) -> Tuple[str, str, str]:
        """Extract code context for a failing line.
        
        Args:
            repo_path: Path to the repository
            file_path: Relative path to the source file
            line_number: Line number of the failure
            
        Returns:
            Tuple of (function_code, context_before, context_after)
        """
        if not file_path or line_number <= 0:
            return "", "", ""
        
        full_path = repo_path / file_path
        
        if not full_path.exists():
            return "", "", ""
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
                lines = source_code.splitlines()
            
            # Use AST to find the function containing the line
            function_code = self._extract_function_by_line(source_code, line_number)
            
            # Extract context before and after the function
            function_start, function_end = self._get_function_line_range(
                source_code, line_number
            )
            
            if function_start > 0:
                # Get context before function
                context_start = max(0, function_start - self.context_lines - 1)
                context_before_lines = lines[context_start:function_start - 1]
                context_before = '\n'.join(context_before_lines)
                
                # Get context after function
                context_end = min(len(lines), function_end + self.context_lines)
                context_after_lines = lines[function_end:context_end]
                context_after = '\n'.join(context_after_lines)
            else:
                context_before = ""
                context_after = ""
            
            return function_code, context_before, context_after
            
        except Exception as e:
            print(f"Warning: Failed to extract code context from {file_path}: {e}")
            return "", "", ""
    
    def _extract_function_by_line(self, source_code: str, line_number: int) -> str:
        """Extract the complete function containing the specified line.
        
        Args:
            source_code: Complete source code of the file
            line_number: Line number within the function
            
        Returns:
            Complete function code as a string
        """
        try:
            tree = ast.parse(source_code)
            lines = source_code.splitlines()
            
            # Find the function or method containing the line
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check if line is within this function's range
                    func_start = node.lineno
                    func_end = self._get_node_end_line(node)
                    
                    if func_start <= line_number <= func_end:
                        # Extract the function code
                        function_lines = lines[func_start - 1:func_end]
                        return '\n'.join(function_lines)
            
            # If no function found, return the line itself with some context
            start = max(0, line_number - 3)
            end = min(len(lines), line_number + 2)
            return '\n'.join(lines[start:end])
            
        except SyntaxError:
            # If parsing fails, return lines around the error
            lines = source_code.splitlines()
            start = max(0, line_number - 3)
            end = min(len(lines), line_number + 2)
            return '\n'.join(lines[start:end])
    
    def _get_function_line_range(self, source_code: str, line_number: int) -> Tuple[int, int]:
        """Get the start and end line numbers of the function containing the line.
        
        Args:
            source_code: Complete source code of the file
            line_number: Line number within the function
            
        Returns:
            Tuple of (start_line, end_line), or (0, 0) if not found
        """
        try:
            tree = ast.parse(source_code)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_start = node.lineno
                    func_end = self._get_node_end_line(node)
                    
                    if func_start <= line_number <= func_end:
                        return func_start, func_end
            
            return 0, 0
            
        except SyntaxError:
            return 0, 0
    
    def _get_node_end_line(self, node: ast.AST) -> int:
        """Get the last line number of an AST node.
        
        Args:
            node: AST node
            
        Returns:
            Last line number of the node
        """
        end_line = node.lineno
        for child in ast.walk(node):
            if hasattr(child, 'lineno') and child.lineno:
                end_line = max(end_line, child.lineno)
            if hasattr(child, 'end_lineno') and child.end_lineno:
                end_line = max(end_line, child.end_lineno)
        return end_line
    
    def _extract_test_stats(self, output: str) -> Tuple[int, int]:
        """Extract test statistics from pytest output.
        
        Args:
            output: Raw pytest output
            
        Returns:
            Tuple of (total_tests, total_failures)
        """
        # Pattern: "=== 2 failed, 3 passed in 0.05s ==="
        stats_pattern = re.search(
            r'=+\s*(?:(\d+)\s+failed)?.*?(?:(\d+)\s+passed)?.*?=+',
            output
        )
        
        if stats_pattern:
            failures = int(stats_pattern.group(1) or 0)
            passed = int(stats_pattern.group(2) or 0)
            total = failures + passed
            return total, failures
        
        return 0, 0
