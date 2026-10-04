"""Helper module for working with pytest plugin results."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class PytestSummary:
    """Summary statistics from a pytest run."""
    exit_code: int
    duration: float
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    xfailed: int
    xpassed: int
    
    @property
    def consistency_ok(self) -> bool:
        """Check if the counts are consistent."""
        # Total should equal sum of outcomes
        counted = self.passed + self.failed + self.errors + self.skipped + self.xfailed + self.xpassed
        return counted == self.total_tests


def load_pytest_results(result_file: Path) -> Dict[str, Any]:
    """Load pytest results from JSON file.
    
    Args:
        result_file: Path to JSON results file created by pytest plugin
        
    Returns:
        Dictionary with 'exit_code', 'duration', 'total_tests', 'results'
        
    Raises:
        FileNotFoundError: If result file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    with open(result_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_summary(results_data: Dict[str, Any]) -> PytestSummary:
    """Extract summary statistics from pytest results.
    
    Args:
        results_data: Pytest results dictionary
        
    Returns:
        PytestSummary object
    """
    results = results_data.get('results', [])
    
    # Count outcomes
    passed = sum(1 for r in results if r['outcome'] == 'passed')
    failed = sum(1 for r in results if r['outcome'] == 'failed')
    errors = sum(1 for r in results if r['outcome'] == 'error')
    skipped = sum(1 for r in results if r['outcome'] == 'skipped')
    xfailed = sum(1 for r in results if r['outcome'] == 'xfailed')
    xpassed = sum(1 for r in results if r['outcome'] == 'xpassed')
    
    return PytestSummary(
        exit_code=results_data.get('exit_code', 0),
        duration=results_data.get('duration', 0.0),
        total_tests=results_data.get('total_tests', len(results)),
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        xfailed=xfailed,
        xpassed=xpassed
    )


def get_failures(results_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract only failed tests from results.
    
    Args:
        results_data: Pytest results dictionary
        
    Returns:
        List of failed test result dictionaries
    """
    results = results_data.get('results', [])
    return [r for r in results if r['outcome'] in ('failed', 'error')]


def get_test_outcome(results_data: Dict[str, Any], node_id: str) -> Optional[str]:
    """Get the outcome for a specific test.
    
    Args:
        results_data: Pytest results dictionary
        node_id: Test node ID (e.g., "tests/test_calc.py::test_add")
        
    Returns:
        Outcome string or None if test not found
    """
    results = results_data.get('results', [])
    for result in results:
        if result['node_id'] == node_id:
            return result['outcome']
    return None


def format_frame(frame: Dict[str, Any]) -> str:
    """Format a traceback frame as a string.
    
    Args:
        frame: Frame dictionary with 'file', 'line', 'function', 'code_line'
        
    Returns:
        Formatted frame string
    """
    file_path = frame.get('file', '?')
    line = frame.get('line', 0)
    function = frame.get('function', '')
    code = frame.get('code_line', '')
    
    parts = [f"{file_path}:{line}"]
    if function:
        parts.append(f"in {function}")
    if code:
        parts.append(f"\n    {code}")
    
    return ' '.join(parts)


def format_traceback(frames: List[Dict[str, Any]]) -> str:
    """Format a list of frames as a traceback string.
    
    Args:
        frames: List of frame dictionaries
        
    Returns:
        Formatted traceback string
    """
    if not frames:
        return ""
    
    lines = ["Traceback:"]
    for frame in frames:
        lines.append("  " + format_frame(frame))
    
    return '\n'.join(lines)
