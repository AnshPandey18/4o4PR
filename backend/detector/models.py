"""Data models for Bug Detector schema v2.0."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FailureAssertion:
    """Information about the first failing assertion."""
    statement: str
    line: int
    operator: Optional[str] = None
    actual: Optional[str] = None
    expected: Optional[str] = None
    assertion_index: int = 1
    assert_total: int = 1
    assertions_not_evaluated: int = 0


@dataclass
class TracebackFrame:
    """A single frame in the traceback."""
    file: str  # POSIX relative path
    line: int
    function: str
    code_line: str
    external: bool = False


@dataclass
class CalledSymbol:
    """Information about a symbol called in the test."""
    name: str
    symbol_id: Optional[str] = None
    file: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    resolution: str = "unresolved"  # resolved | ambiguous | unresolved
    source_snapshot: Optional[str] = None


@dataclass
class CapturedOutput:
    """Captured stdout and stderr."""
    stdout: str = ""
    stderr: str = ""


@dataclass
class BugReport:
    """A single bug report (schema v2.0)."""
    bug_id: str
    test_name: str  # POSIX path with :: (e.g., "tests/test_calc.py::test_subtract")
    failure_kind: str  # assertion | exception | collection_error | import_error | timeout
    error_type: str
    error_message: str
    
    # Location information
    location: Dict[str, Any]  # file_path, line_number, function
    
    # Assertion details
    first_failing_assertion: Optional[FailureAssertion] = None
    
    # Source resolution
    called_symbols: List[CalledSymbol] = field(default_factory=list)
    inferred_source_module: Optional[str] = None
    
    # Traceback
    frames: List[TracebackFrame] = field(default_factory=list)
    traceback: str = ""
    
    # Test code
    code: str = ""
    
    # Output
    captured_output: Optional[CapturedOutput] = None
    
    # Metadata
    rerun_command: str = ""
    flaky: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'bug_id': self.bug_id,
            'test_name': self.test_name,
            'failure_kind': self.failure_kind,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'location': self.location,
            'first_failing_assertion': {
                'statement': self.first_failing_assertion.statement,
                'line': self.first_failing_assertion.line,
                'operator': self.first_failing_assertion.operator,
                'actual': self.first_failing_assertion.actual,
                'expected': self.first_failing_assertion.expected,
                'assertion_index': self.first_failing_assertion.assertion_index,
                'assert_total': self.first_failing_assertion.assert_total,
                'assertions_not_evaluated': self.first_failing_assertion.assertions_not_evaluated
            } if self.first_failing_assertion else None,
            'called_symbols': [
                {
                    'name': cs.name,
                    'symbol_id': cs.symbol_id,
                    'file': cs.file,
                    'line_start': cs.line_start,
                    'line_end': cs.line_end,
                    'resolution': cs.resolution,
                    'source_snapshot': cs.source_snapshot
                }
                for cs in self.called_symbols
            ],
            'inferred_source_module': self.inferred_source_module,
            'frames': [
                {
                    'file': f.file,
                    'line': f.line,
                    'function': f.function,
                    'code_line': f.code_line,
                    'external': f.external
                }
                for f in self.frames
            ],
            'traceback': self.traceback,
            'code': self.code,
            'captured_output': {
                'stdout': self.captured_output.stdout,
                'stderr': self.captured_output.stderr
            } if self.captured_output else None,
            'rerun_command': self.rerun_command,
            'flaky': self.flaky
        }


@dataclass
class ProjectInfo:
    """Project metadata."""
    root: str
    content_hash: Optional[str] = None
    python_version: str = ""
    pytest_version: str = ""


@dataclass
class Summary:
    """Test run summary statistics."""
    tests_run: int
    passed: int
    failed: int
    errors: int
    skipped: int
    xfailed: int
    xpassed: int
    bugs_detected: int
    pytest_exit_code: int
    duration_seconds: float
    consistency_ok: bool


@dataclass
class BugDetectionResult:
    """Complete bug detection result (schema v2.0)."""
    schema_version: str
    run_id: str
    timestamp: str
    project: ProjectInfo
    summary: Summary
    bugs: List[BugReport]
    validation_hint: str = "Validate patches by re-running the full test node IDs, not just the failing assertion"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'schema_version': self.schema_version,
            'run_id': self.run_id,
            'timestamp': self.timestamp,
            'project': {
                'root': self.project.root,
                'content_hash': self.project.content_hash,
                'python_version': self.project.python_version,
                'pytest_version': self.project.pytest_version
            },
            'summary': {
                'tests_run': self.summary.tests_run,
                'passed': self.summary.passed,
                'failed': self.summary.failed,
                'errors': self.summary.errors,
                'skipped': self.summary.skipped,
                'xfailed': self.summary.xfailed,
                'xpassed': self.summary.xpassed,
                'bugs_detected': self.summary.bugs_detected,
                'pytest_exit_code': self.summary.pytest_exit_code,
                'duration_seconds': self.summary.duration_seconds,
                'consistency_ok': self.summary.consistency_ok
            },
            'bugs': [bug.to_dict() for bug in self.bugs],
            'validation_hint': self.validation_hint
        }


@dataclass
class BaselineResults:
    """Baseline test results for all tests (schema v1.0)."""
    schema_version: str
    run_id: str
    project_content_hash: Optional[str]
    pytest_exit_code: int
    duration_seconds: float
    results: Dict[str, str]  # node_id -> outcome
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'schema_version': self.schema_version,
            'run_id': self.run_id,
            'project_content_hash': self.project_content_hash,
            'pytest_exit_code': self.pytest_exit_code,
            'duration_seconds': self.duration_seconds,
            'results': self.results
        }
