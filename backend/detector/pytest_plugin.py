"""Pytest plugin for capturing structured test results.

This plugin runs within pytest's process and captures detailed information
about each test execution, including outcomes, tracebacks, and timing.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class TestFrame:
    """A single frame in a traceback."""
    file: str
    line: int
    function: str
    code_line: str


@dataclass
class TestResult:
    """Structured result for a single test."""
    node_id: str
    outcome: str  # passed, failed, skipped, error, xfailed, xpassed
    duration: float
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    frames: List[TestFrame] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'node_id': self.node_id,
            'outcome': self.outcome,
            'duration': self.duration,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'frames': [asdict(f) for f in self.frames],
            'stdout': self.stdout,
            'stderr': self.stderr
        }


class ResultCollectorPlugin:
    """Pytest plugin that collects structured test results."""
    
    def __init__(self, output_file: str):
        """Initialize the plugin.
        
        Args:
            output_file: Path where results JSON will be written
        """
        self.output_file = output_file
        self.results: List[TestResult] = []
        self.session_start_time: float = 0
        self.session_end_time: float = 0
    
    def pytest_sessionstart(self, session):
        """Called at the start of test session."""
        import time
        self.session_start_time = time.time()
    
    def pytest_sessionfinish(self, session, exitstatus):
        """Called at the end of test session - write results to file."""
        import time
        self.session_end_time = time.time()
        
        # Prepare output data
        output_data = {
            'exit_code': exitstatus,
            'duration': self.session_end_time - self.session_start_time,
            'total_tests': len(self.results),
            'results': [r.to_dict() for r in self.results]
        }
        
        # Write to file
        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    def pytest_runtest_logreport(self, report):
        """Called for each test phase (setup, call, teardown).
        
        We only care about the 'call' phase for actual test results.
        """
        if report.when != 'call':
            return
        
        # Extract test result information
        result = TestResult(
            node_id=report.nodeid,
            outcome=report.outcome,
            duration=report.duration
        )
        
        # Capture stdout/stderr
        if hasattr(report, 'capstdout'):
            result.stdout = report.capstdout
        if hasattr(report, 'capstderr'):
            result.stderr = report.capstderr
        
        # For failures and errors, extract traceback info
        if report.failed or report.outcome == 'error':
            if hasattr(report, 'longrepr'):
                self._extract_error_info(report.longrepr, result)
        
        self.results.append(result)
    
    def _extract_error_info(self, longrepr, result: TestResult):
        """Extract error information from longrepr.
        
        Args:
            longrepr: Pytest's long representation of the error
            result: TestResult to populate
        """
        try:
            # Handle different longrepr types
            if hasattr(longrepr, 'reprcrash'):
                # ExceptionInfo with reprcrash
                crash = longrepr.reprcrash
                if crash:
                    result.error_message = crash.message
                    
                    # Extract error type from message if possible
                    if ':' in crash.message:
                        parts = crash.message.split(':', 1)
                        if parts[0] and not parts[0].startswith(' '):
                            result.error_type = parts[0].strip()
                            result.error_message = parts[1].strip()
            
            # Extract traceback frames
            if hasattr(longrepr, 'reprtraceback'):
                reprtb = longrepr.reprtraceback
                if hasattr(reprtb, 'reprentries'):
                    for entry in reprtb.reprentries:
                        if hasattr(entry, 'reprfileloc'):
                            fileloc = entry.reprfileloc
                            
                            # Get function name
                            function = ""
                            if hasattr(entry, 'reprfuncargs'):
                                function = str(entry.reprfuncargs) if entry.reprfuncargs else ""
                            
                            # Get the code line
                            code_line = ""
                            if hasattr(entry, 'lines'):
                                # Join the source lines
                                code_line = ''.join(entry.lines).strip()
                            
                            frame = TestFrame(
                                file=str(fileloc.path),
                                line=fileloc.lineno,
                                function=function,
                                code_line=code_line
                            )
                            result.frames.append(frame)
            
            # If we still don't have an error type, try to extract it from the string representation
            if not result.error_type:
                longrepr_str = str(longrepr)
                
                # Look for common error patterns
                error_keywords = [
                    'AssertionError', 'AttributeError', 'TypeError', 'ValueError',
                    'KeyError', 'IndexError', 'RuntimeError', 'ImportError',
                    'ModuleNotFoundError', 'ZeroDivisionError', 'FileNotFoundError'
                ]
                
                for keyword in error_keywords:
                    if keyword in longrepr_str:
                        result.error_type = keyword
                        break
                
                if not result.error_type:
                    result.error_type = "Error"
                
                # Extract error message if we don't have one
                if not result.error_message:
                    # Get the last non-empty line from longrepr
                    lines = longrepr_str.strip().split('\n')
                    for line in reversed(lines):
                        line = line.strip()
                        if line and not line.startswith('_') and not line.startswith('='):
                            result.error_message = line
                            break
        
        except Exception as e:
            # Fallback: just use string representation
            result.error_type = "Error"
            result.error_message = str(longrepr)[:200]


def pytest_configure(config):
    """Register the plugin with pytest.
    
    This function is called by pytest when the plugin is loaded.
    """
    # Check if output file is specified
    output_file = config.getoption('--json-report', default=None)
    
    if output_file:
        plugin = ResultCollectorPlugin(output_file)
        config.pluginmanager.register(plugin, 'result_collector')


def pytest_addoption(parser):
    """Add command-line options for this plugin.
    
    This function is called by pytest to add custom options.
    """
    group = parser.getgroup('4o4pr', '4o4PR bug detector options')
    group.addoption(
        '--json-report',
        action='store',
        dest='json_report',
        default=None,
        help='Path to write structured test results as JSON'
    )
