"""Bug Detector v2.0 - Identifies failing tests and extracts detailed context.

Fixes from v1.0:
1. Correct summary counts using pytest plugin
2. Resolve real source symbols via pyresolve
3. Normalize all paths to POSIX
4. Extract and count assertions
5. Add bug_id and flaky detection
6. Generate baseline_results.json
"""

import ast
import logging
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from common.paths import to_posix_rel, normalize_path_in_string
from common.pyresolve import ImportResolver
from common.hashing import sha1_string, short_hash
from common.io import write_json
from .models import (
    BugReport, BugDetectionResult, BaselineResults, ProjectInfo, Summary,
    FailureAssertion, TracebackFrame, CalledSymbol, CapturedOutput
)
from .pytest_results import load_pytest_results, get_summary

logger = logging.getLogger(__name__)


class BugDetector:
    """Detects bugs by running pytest and analyzing failures."""
    
    def __init__(
        self,
        project_root: Path,
        import_roots: List[str],
        timeout_seconds: int = 300,
        flaky_reruns: int = 2,
        embed_source_snapshot: bool = True,
        snapshot_max_lines: int = 80
    ):
        """Initialize the bug detector.
        
        Args:
            project_root: Project root directory
            import_roots: Directories where imports resolve from
            timeout_seconds: Timeout for pytest execution
            flaky_reruns: Number of reruns to detect flaky tests
            embed_source_snapshot: Include source snapshots in bug reports
            snapshot_max_lines: Maximum lines per source snapshot
        """
        self.project_root = Path(project_root)
        self.import_roots = import_roots
        self.timeout_seconds = timeout_seconds
        self.flaky_reruns = flaky_reruns
        self.embed_source_snapshot = embed_source_snapshot
        self.snapshot_max_lines = snapshot_max_lines
        
        self.resolver = ImportResolver(self.project_root, import_roots)
    
    def detect(
        self,
        run_id: str,
        schema_version: str = "2.0",
        content_hash: Optional[str] = None
    ) -> BugDetectionResult:
        """Run bug detection.
        
        Args:
            run_id: Unique run identifier
            schema_version: Schema version for output
            content_hash: Optional content hash of the project
            
        Returns:
            BugDetectionResult with all detected bugs
        """
        logger.info(f"Starting bug detection (run_id: {run_id})")
        
        # Run pytest with plugin
        with tempfile.TemporaryDirectory() as tmpdir:
            results_file = Path(tmpdir) / "pytest_results.json"
            
            pytest_data = self._run_pytest(results_file)
            
            # Get summary statistics
            pytest_summary = get_summary(pytest_data)
            
            # Extract bug reports from failures
            bugs = self._process_failures(pytest_data)
            
            # Detect flaky tests
            self._detect_flaky_tests(bugs)
            
            # Filter out flaky bugs from count
            non_flaky_bugs = [b for b in bugs if not b.flaky]
            
            # Check consistency
            consistency_ok = (
                pytest_summary.failed + pytest_summary.errors == len(non_flaky_bugs)
            )
            
            if not consistency_ok:
                logger.error(
                    f"Consistency check failed: "
                    f"pytest reported {pytest_summary.failed + pytest_summary.errors} failures, "
                    f"but we detected {len(non_flaky_bugs)} non-flaky bugs"
                )
            
            # Get Python and pytest versions
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            pytest_version = self._get_pytest_version()
            
            # Create project info
            project_info = ProjectInfo(
                root=str(to_posix_rel(self.project_root, self.project_root)[0]),
                content_hash=content_hash,
                python_version=python_version,
                pytest_version=pytest_version
            )
            
            # Create summary
            summary = Summary(
                tests_run=pytest_summary.total_tests,
                passed=pytest_summary.passed,
                failed=pytest_summary.failed,
                errors=pytest_summary.errors,
                skipped=pytest_summary.skipped,
                xfailed=pytest_summary.xfailed,
                xpassed=pytest_summary.xpassed,
                bugs_detected=len(bugs),  # Include flaky in total
                pytest_exit_code=pytest_summary.exit_code,
                duration_seconds=pytest_summary.duration,
                consistency_ok=consistency_ok
            )
            
            # Create result
            result = BugDetectionResult(
                schema_version=schema_version,
                run_id=run_id,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                project=project_info,
                summary=summary,
                bugs=bugs
            )
            
            logger.info(
                f"Bug detection complete: {len(bugs)} bugs detected "
                f"({len(non_flaky_bugs)} non-flaky, {len(bugs) - len(non_flaky_bugs)} flaky)"
            )
            
            return result
    
    def generate_baseline(
        self,
        run_id: str,
        content_hash: Optional[str] = None
    ) -> BaselineResults:
        """Generate baseline results for all tests.
        
        Args:
            run_id: Unique run identifier
            content_hash: Optional content hash of the project
            
        Returns:
            BaselineResults with all test outcomes
        """
        logger.info("Generating baseline test results")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            results_file = Path(tmpdir) / "pytest_results.json"
            pytest_data = self._run_pytest(results_file)
            
            # Extract all test outcomes
            results = {}
            for test in pytest_data.get('results', []):
                node_id = test['node_id']
                outcome = test['outcome']
                # Normalize path in node_id
                node_id_normalized = self._normalize_node_id(node_id)
                results[node_id_normalized] = outcome
            
            baseline = BaselineResults(
                schema_version="1.0",
                run_id=run_id,
                project_content_hash=content_hash,
                pytest_exit_code=pytest_data.get('exit_code', 0),
                duration_seconds=pytest_data.get('duration', 0.0),
                results=results
            )
            
            logger.info(f"Baseline generated: {len(results)} tests")
            return baseline
    
    def _run_pytest(self, results_file: Path) -> Dict:
        """Run pytest with the structured results plugin.
        
        Args:
            results_file: Path where pytest plugin will write results
            
        Returns:
            Dictionary with pytest results
        """
        # Build pytest command
        plugin_path = Path(__file__).parent / "pytest_plugin.py"
        
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-p", "no:cacheprovider",
            "-p", f"pytest_plugin",
            "--json-report", str(results_file),
            "-v"
        ]
        
        logger.info(f"Running pytest: {' '.join(cmd)}")
        
        try:
            # Set PYTHONPATH to include detector directory for plugin import
            env = {**subprocess.os.environ}
            detector_dir = Path(__file__).parent
            pythonpath = env.get('PYTHONPATH', '')
            if pythonpath:
                env['PYTHONPATH'] = f"{detector_dir}{subprocess.os.pathsep}{pythonpath}"
            else:
                env['PYTHONPATH'] = str(detector_dir)
            
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env
            )
            
            # Load results from plugin output
            if results_file.exists():
                return load_pytest_results(results_file)
            else:
                logger.error("Pytest plugin did not create results file")
                return {'exit_code': result.returncode, 'duration': 0, 'total_tests': 0, 'results': []}
        
        except subprocess.TimeoutExpired:
            logger.error(f"Pytest timed out after {self.timeout_seconds} seconds")
            return {'exit_code': -1, 'duration': self.timeout_seconds, 'total_tests': 0, 'results': []}
        
        except Exception as e:
            logger.error(f"Failed to run pytest: {e}")
            return {'exit_code': -1, 'duration': 0, 'total_tests': 0, 'results': []}
    
    def _process_failures(self, pytest_data: Dict) -> List[BugReport]:
        """Process failure results and create bug reports.
        
        Args:
            pytest_data: Pytest results dictionary
            
        Returns:
            List of BugReport objects
        """
        bugs = []
        
        for test_result in pytest_data.get('results', []):
            if test_result['outcome'] in ('failed', 'error'):
                try:
                    bug = self._create_bug_report(test_result)
                    bugs.append(bug)
                except Exception as e:
                    logger.error(f"Failed to create bug report for {test_result['node_id']}: {e}")
        
        return bugs
    
    def _create_bug_report(self, test_result: Dict) -> BugReport:
        """Create a detailed bug report from a test failure.
        
        Args:
            test_result: Test result dictionary from pytest plugin
            
        Returns:
            BugReport object
        """
        node_id = test_result['node_id']
        outcome = test_result['outcome']
        
        # Normalize node_id
        node_id_normalized = self._normalize_node_id(node_id)
        
        # Parse node_id to get file and test name
        if '::' in node_id_normalized:
            file_part, test_part = node_id_normalized.split('::', 1)
        else:
            file_part, test_part = node_id_normalized, ''
        
        # Determine failure kind
        failure_kind = self._determine_failure_kind(test_result, file_part)
        
        # Get error info
        error_type = test_result.get('error_type', 'Error')
        error_message = test_result.get('error_message', 'Test failed')
        
        # Normalize paths in error message
        error_message_normalized = normalize_path_in_string(error_message, self.project_root)
        
        # Extract frames
        frames = self._extract_frames(test_result.get('frames', []))
        
        # Build traceback string
        traceback = self._build_traceback(frames, error_type, error_message_normalized)
        
        # Determine location (first test file frame)
        location = self._determine_location(frames, file_part)
        
        # Extract test code
        test_code = self._extract_test_code(file_part, test_part)
        
        # Extract assertions
        first_assertion = self._extract_first_assertion(
            file_part, test_part, location.get('line_number', 0), error_message_normalized
        )
        
        # Resolve called symbols
        called_symbols = self._resolve_called_symbols(file_part, test_part, first_assertion)
        
        # Infer source module
        inferred_source = self._infer_source_module(called_symbols)
        
        # Capture output
        captured_output = CapturedOutput(
            stdout=test_result.get('stdout', '')[:2000],
            stderr=test_result.get('stderr', '')[:2000]
        )
        
        # Generate bug_id
        bug_id = self._generate_bug_id(node_id_normalized, error_type, error_message_normalized)
        
        # Generate rerun command
        rerun_command = f'pytest "{node_id_normalized}"'
        
        return BugReport(
            bug_id=bug_id,
            test_name=node_id_normalized,
            failure_kind=failure_kind,
            error_type=error_type,
            error_message=error_message_normalized,
            location=location,
            first_failing_assertion=first_assertion,
            called_symbols=called_symbols,
            inferred_source_module=inferred_source,
            frames=frames,
            traceback=traceback,
            code=test_code,
            captured_output=captured_output,
            rerun_command=rerun_command,
            flaky=False  # Will be updated in flaky detection
        )
    
    def _normalize_node_id(self, node_id: str) -> str:
        """Normalize a pytest node ID to use POSIX paths.
        
        Args:
            node_id: Pytest node ID (may have backslashes on Windows)
            
        Returns:
            Normalized node ID with forward slashes
        """
        # Split on :: to separate file path from test name
        if '::' in node_id:
            parts = node_id.split('::', 1)
            file_part = parts[0]
            test_part = parts[1]
            
            # Normalize file path
            normalized_file, _ = to_posix_rel(file_part, self.project_root)
            return f"{normalized_file}::{test_part}"
        else:
            # Just a file path
            normalized, _ = to_posix_rel(node_id, self.project_root)
            return normalized
    
    def _determine_failure_kind(self, test_result: Dict, file_path: str) -> str:
        """Determine the kind of failure.
        
        Args:
            test_result: Test result dictionary
            file_path: Normalized file path
            
        Returns:
            Failure kind string
        """
        error_type = test_result.get('error_type', '')
        error_message = test_result.get('error_message', '')
        
        # Collection errors
        if 'import' in error_message.lower() or error_type in ('ImportError', 'ModuleNotFoundError'):
            if 'conftest' in file_path or not file_path.endswith('.py'):
                return 'collection_error'
            return 'import_error'
        
        # Assertion errors
        if error_type == 'AssertionError' or 'assert' in error_message.lower():
            return 'assertion'
        
        # Timeout (would need to be detected by pytest)
        if 'timeout' in error_message.lower():
            return 'timeout'
        
        # Everything else is an exception
        return 'exception'
    
    def _extract_frames(self, frames_data: List[Dict]) -> List[TracebackFrame]:
        """Extract and normalize traceback frames.
        
        Args:
            frames_data: List of frame dictionaries from pytest plugin
            
        Returns:
            List of TracebackFrame objects
        """
        frames = []
        
        for frame_data in frames_data:
            file_path = frame_data.get('file', '')
            
            # Normalize path
            normalized_path, is_external = to_posix_rel(file_path, self.project_root)
            
            frame = TracebackFrame(
                file=normalized_path,
                line=frame_data.get('line', 0),
                function=frame_data.get('function', ''),
                code_line=frame_data.get('code_line', ''),
                external=is_external
            )
            frames.append(frame)
        
        return frames
    
    def _build_traceback(
        self,
        frames: List[TracebackFrame],
        error_type: str,
        error_message: str
    ) -> str:
        """Build a traceback string from frames.
        
        Args:
            frames: List of TracebackFrame objects
            error_type: Error type
            error_message: Error message
            
        Returns:
            Formatted traceback string
        """
        lines = []
        
        for frame in frames:
            lines.append(f"  File \"{frame.file}\", line {frame.line}, in {frame.function}")
            if frame.code_line:
                lines.append(f"    {frame.code_line}")
        
        if lines:
            lines.insert(0, "Traceback (most recent call last):")
        
        lines.append(f"{error_type}: {error_message}")
        
        return '\n'.join(lines)
    
    def _determine_location(self, frames: List[TracebackFrame], test_file: str) -> Dict[str, Any]:
        """Determine the location of the failure.
        
        Args:
            frames: List of TracebackFrame objects
            test_file: Test file path
            
        Returns:
            Location dictionary
        """
        # Find the first frame in the test file
        for frame in frames:
            if frame.file == test_file or test_file in frame.file:
                return {
                    'file_path': frame.file,
                    'line_number': frame.line,
                    'function': frame.function
                }
        
        # Fallback to first frame
        if frames:
            return {
                'file_path': frames[0].file,
                'line_number': frames[0].line,
                'function': frames[0].function
            }
        
        # No frames
        return {
            'file_path': test_file,
            'line_number': 0,
            'function': ''
        }
    
    def _extract_test_code(self, file_path: str, test_name: str) -> str:
        """Extract the test function code.
        
        Args:
            file_path: POSIX relative path to test file
            test_name: Test function name
            
        Returns:
            Test function code as string
        """
        full_path = self.project_root / file_path
        
        if not full_path.exists():
            return ""
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            # Extract the test function name (may include class)
            if '::' in test_name:
                # Class method
                parts = test_name.split('::')
                func_name = parts[-1]
            else:
                func_name = test_name
            
            # Find the function
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        lines = source.splitlines()
                        start = node.lineno - 1
                        end = node.end_lineno if node.end_lineno else start + 1
                        return '\n'.join(lines[start:end])
            
            return ""
        
        except Exception as e:
            logger.warning(f"Failed to extract test code from {file_path}: {e}")
            return ""
    
    def _extract_first_assertion(
        self,
        file_path: str,
        test_name: str,
        failing_line: int,
        error_message: str
    ) -> Optional[FailureAssertion]:
        """Extract information about the first failing assertion.
        
        Args:
            file_path: POSIX relative path to test file
            test_name: Test function name
            failing_line: Line number where failure occurred
            error_message: Error message from pytest
            
        Returns:
            FailureAssertion object or None
        """
        full_path = self.project_root / file_path
        
        if not full_path.exists():
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            lines = source.splitlines()
            
            # Extract function name
            if '::' in test_name:
                parts = test_name.split('::')
                func_name = parts[-1]
            else:
                func_name = test_name
            
            # Find the test function
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        # Count assertions in the function
                        assertions = []
                        for child in ast.walk(node):
                            if isinstance(child, ast.Assert):
                                assertions.append(child)
                        
                        assert_total = len(assertions)
                        
                        # Find the failing assertion (closest to failing_line)
                        if assertions:
                            # Find assertion at or before failing_line
                            failing_assert = None
                            assertion_index = 0
                            
                            for i, assert_node in enumerate(assertions, 1):
                                if assert_node.lineno <= failing_line:
                                    failing_assert = assert_node
                                    assertion_index = i
                            
                            if not failing_assert:
                                # Use first assertion
                                failing_assert = assertions[0]
                                assertion_index = 1
                            
                            # Extract assertion statement
                            assert_line = failing_assert.lineno
                            statement = lines[assert_line - 1].strip()
                            
                            # Parse operator, actual, expected from error message
                            operator, actual, expected = self._parse_assertion_values(error_message)
                            
                            assertions_not_evaluated = assert_total - assertion_index
                            
                            return FailureAssertion(
                                statement=statement,
                                line=assert_line,
                                operator=operator,
                                actual=actual,
                                expected=expected,
                                assertion_index=assertion_index,
                                assert_total=assert_total,
                                assertions_not_evaluated=assertions_not_evaluated
                            )
            
            return None
        
        except Exception as e:
            logger.warning(f"Failed to extract assertion from {file_path}: {e}")
            return None
    
    def _parse_assertion_values(self, error_message: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse actual and expected values from pytest's error message.
        
        Args:
            error_message: Error message from pytest
            
        Returns:
            Tuple of (operator, actual, expected) or (None, None, None)
        """
        # Pytest formats assertions like: "assert 2 == 3" or "where 8 = subtract(5, 3)"
        # Try to extract operator and values
        
        # Pattern: "assert <actual> <op> <expected>"
        comparison_pattern = r'assert\s+(.+?)\s+(==|!=|<|>|<=|>=|is|is not|in|not in)\s+(.+?)(?:\s|$)'
        match = re.search(comparison_pattern, error_message)
        
        if match:
            actual = match.group(1).strip()
            operator = match.group(2).strip()
            expected = match.group(3).strip()
            return operator, actual, expected
        
        return None, None, None
    
    def _resolve_called_symbols(
        self,
        file_path: str,
        test_name: str,
        first_assertion: Optional[FailureAssertion]
    ) -> List[CalledSymbol]:
        """Resolve symbols called in the failing assertion.
        
        Args:
            file_path: POSIX relative path to test file
            test_name: Test function name
            first_assertion: First failing assertion info
            
        Returns:
            List of CalledSymbol objects
        """
        if not first_assertion:
            return []
        
        full_path = self.project_root / file_path
        
        if not full_path.exists():
            return []
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            # Find the test function
            if '::' in test_name:
                parts = test_name.split('::')
                func_name = parts[-1]
            else:
                func_name = test_name
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        # Get imports from the file
                        imports = self.resolver.extract_imports_from_file(full_path)
                        import_map = self._build_import_map(imports)
                        
                        # Find the assertion node
                        for child in ast.walk(node):
                            if isinstance(child, ast.Assert) and child.lineno == first_assertion.line:
                                # Extract function calls from the assertion
                                return self._extract_calls_from_assertion(child, file_path, import_map)
            
            return []
        
        except Exception as e:
            logger.warning(f"Failed to resolve symbols in {file_path}: {e}")
            return []
    
    def _build_import_map(self, imports: List[Dict]) -> Dict[str, str]:
        """Build a mapping from imported names to their files.
        
        Args:
            imports: List of import dictionaries
            
        Returns:
            Dict mapping name to file path
        """
        import_map = {}
        
        for imp in imports:
            resolved_file = imp.get('resolved_file')
            if resolved_file:
                for name_info in imp.get('names', []):
                    name = name_info.get('name', '')
                    asname = name_info.get('asname')
                    key = asname if asname else name
                    if key:
                        import_map[key] = resolved_file
        
        return import_map
    
    def _extract_calls_from_assertion(
        self,
        assert_node: ast.Assert,
        file_path: str,
        import_map: Dict[str, str]
    ) -> List[CalledSymbol]:
        """Extract function calls from an assertion node.
        
        Args:
            assert_node: AST Assert node
            file_path: POSIX relative path to test file
            import_map: Import name to file mapping
            
        Returns:
            List of CalledSymbol objects
        """
        called_symbols = []
        seen_names = set()
        
        # Walk the assertion to find function calls
        for node in ast.walk(assert_node.test):
            if isinstance(node, ast.Call):
                symbol = self._resolve_call_to_symbol(node, file_path, import_map)
                if symbol and symbol.name not in seen_names:
                    called_symbols.append(symbol)
                    seen_names.add(symbol.name)
        
        return called_symbols
    
    def _resolve_call_to_symbol(
        self,
        call_node: ast.Call,
        file_path: str,
        import_map: Dict[str, str]
    ) -> Optional[CalledSymbol]:
        """Resolve a function call to a CalledSymbol.
        
        Args:
            call_node: AST Call node
            file_path: POSIX relative path to test file
            import_map: Import name to file mapping
            
        Returns:
            CalledSymbol or None
        """
        func = call_node.func
        
        # Simple name call: func()
        if isinstance(func, ast.Name):
            name = func.id
            
            # Check if it's imported
            if name in import_map:
                target_file = import_map[name]
                symbol_id = f"{target_file}::{name}"
                
                # Try to get source code
                source_snapshot = None
                line_start = None
                line_end = None
                
                if self.embed_source_snapshot:
                    try:
                        full_path = self.project_root / target_file
                        with open(full_path, 'r', encoding='utf-8') as f:
                            source = f.read()
                        
                        # Find the function in the file
                        tree = ast.parse(source)
                        lines = source.splitlines()
                        
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if node.name == name:
                                    line_start = node.lineno
                                    line_end = node.end_lineno or line_start
                                    
                                    # Extract snapshot
                                    snapshot_lines = lines[line_start - 1:line_end]
                                    if len(snapshot_lines) > self.snapshot_max_lines:
                                        snapshot_lines = snapshot_lines[:self.snapshot_max_lines]
                                        snapshot_lines.append("    # ... (truncated)")
                                    
                                    source_snapshot = '\n'.join(snapshot_lines)
                                    break
                    except:
                        pass
                
                return CalledSymbol(
                    name=name,
                    symbol_id=symbol_id,
                    file=target_file,
                    line_start=line_start,
                    line_end=line_end,
                    resolution="resolved",
                    source_snapshot=source_snapshot
                )
            
            # Unresolved
            return CalledSymbol(
                name=name,
                resolution="unresolved"
            )
        
        # Attribute call: module.func()
        elif isinstance(func, ast.Attribute):
            attr_name = func.attr
            
            if isinstance(func.value, ast.Name):
                module_name = func.value.id
                
                if module_name in import_map:
                    target_file = import_map[module_name]
                    symbol_id = f"{target_file}::{attr_name}"
                    
                    return CalledSymbol(
                        name=attr_name,
                        symbol_id=symbol_id,
                        file=target_file,
                        resolution="resolved"
                    )
            
            return CalledSymbol(
                name=attr_name,
                resolution="unresolved"
            )
        
        return None
    
    def _infer_source_module(self, called_symbols: List[CalledSymbol]) -> Optional[str]:
        """Infer the source module from called symbols.
        
        Args:
            called_symbols: List of CalledSymbol objects
            
        Returns:
            POSIX relative path to inferred source file or None
        """
        # Use the first resolved symbol's file
        for symbol in called_symbols:
            if symbol.resolution == "resolved" and symbol.file:
                return symbol.file
        
        return None
    
    def _generate_bug_id(self, node_id: str, error_type: str, error_message: str) -> str:
        """Generate a stable bug ID.
        
        Args:
            node_id: Normalized test node ID
            error_type: Error type
            error_message: Error message (normalized)
            
        Returns:
            Bug ID string (e.g., "b_a1b2c3d4e5f6")
        """
        # Normalize error message: collapse whitespace, strip numbers that look like addresses
        normalized_msg = re.sub(r'\s+', ' ', error_message)
        normalized_msg = re.sub(r'0x[0-9a-fA-F]+', '0x...', normalized_msg)
        normalized_msg = re.sub(r'at line \d+', 'at line N', normalized_msg)
        
        # Combine and hash
        combined = f"{node_id}|{error_type}|{normalized_msg}"
        hash_val = short_hash(combined, length=12)
        
        return f"b_{hash_val}"
    
    def _detect_flaky_tests(self, bugs: List[BugReport]) -> None:
        """Detect flaky tests by re-running them.
        
        Modifies bugs in place to set flaky flag.
        
        Args:
            bugs: List of BugReport objects
        """
        if self.flaky_reruns <= 0:
            return
        
        logger.info(f"Detecting flaky tests (reruns: {self.flaky_reruns})")
        
        for bug in bugs:
            # Skip collection errors
            if bug.failure_kind in ('collection_error', 'import_error'):
                continue
            
            # Rerun the test multiple times
            passed_once = False
            
            for rerun in range(self.flaky_reruns):
                if self._rerun_single_test(bug.test_name):
                    passed_once = True
                    break
            
            if passed_once:
                bug.flaky = True
                logger.info(f"Detected flaky test: {bug.test_name}")
    
    def _rerun_single_test(self, node_id: str) -> bool:
        """Rerun a single test to check if it passes.
        
        Args:
            node_id: Test node ID
            
        Returns:
            True if test passed, False otherwise
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-p", "no:cacheprovider",
            "-x",  # Stop on first failure
            node_id
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                timeout=30  # Short timeout for rerun
            )
            return result.returncode == 0
        except:
            return False
    
    def _get_pytest_version(self) -> str:
        """Get pytest version.
        
        Returns:
            Pytest version string
        """
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse "pytest X.Y.Z"
            output = result.stdout.strip()
            match = re.search(r'pytest\s+([\d.]+)', output)
            if match:
                return match.group(1)
        except:
            pass
        
        return "unknown"
