"""Markdown report generator for bug detection results."""

from typing import List
from .models import BugDetectionResult, BugReport


def generate_markdown_report(result: BugDetectionResult) -> str:
    """Generate a markdown report from bug detection results.
    
    Args:
        result: BugDetectionResult object
        
    Returns:
        Markdown formatted report string
    """
    lines = []
    
    # Title
    lines.append("# Bug Detection Report")
    lines.append("")
    
    # Metadata
    lines.append("## Run Information")
    lines.append("")
    lines.append(f"- **Run ID:** {result.run_id}")
    lines.append(f"- **Timestamp:** {result.timestamp}")
    lines.append(f"- **Project Root:** {result.project.root}")
    lines.append(f"- **Python Version:** {result.project.python_version}")
    lines.append(f"- **Pytest Version:** {result.project.pytest_version}")
    if result.project.content_hash:
        lines.append(f"- **Content Hash:** {result.project.content_hash[:16]}...")
    lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Tests Run:** {result.summary.tests_run}")
    lines.append("")
    lines.append(f"- **Total Failures:** {result.summary.failed}")
    lines.append("")
    lines.append(f"- **Total Errors:** {result.summary.errors}")
    lines.append("")
    lines.append(f"- **Tests Passed:** {result.summary.passed}")
    lines.append("")
    lines.append(f"- **Tests Skipped:** {result.summary.skipped}")
    lines.append("")
    lines.append(f"- **Bugs Detected:** {result.summary.bugs_detected}")
    lines.append("")
    lines.append(f"- **Pytest Exit Code:** {result.summary.pytest_exit_code}")
    lines.append("")
    lines.append(f"- **Duration:** {result.summary.duration_seconds:.2f}s")
    lines.append("")
    lines.append(f"- **Consistency Check:** {'✓ PASS' if result.summary.consistency_ok else '✗ FAIL'}")
    lines.append("")
    
    # Bugs
    if result.bugs:
        lines.append("## Detected Bugs")
        lines.append("")
        
        for i, bug in enumerate(result.bugs, 1):
            lines.extend(_format_bug(bug, i))
    else:
        lines.append("## No Bugs Detected")
        lines.append("")
        lines.append("All tests passed successfully!")
        lines.append("")
    
    # Validation hint
    lines.append("---")
    lines.append("")
    lines.append(f"**Note:** {result.validation_hint}")
    lines.append("")
    
    return '\n'.join(lines)


def _format_bug(bug: BugReport, index: int) -> List[str]:
    """Format a single bug report for markdown.
    
    Args:
        bug: BugReport object
        index: Bug number (for display)
        
    Returns:
        List of markdown lines
    """
    lines = []
    
    # Bug header
    lines.append(f"### Bug #{index}: {bug.test_name}")
    lines.append("")
    
    # Metadata
    lines.append(f"- **Bug ID:** `{bug.bug_id}`")
    lines.append(f"- **Failure Kind:** {bug.failure_kind}")
    lines.append(f"- **Error Type:** {bug.error_type}")
    if bug.flaky:
        lines.append(f"- **Status:** ⚠️ FLAKY (passed on rerun)")
    lines.append("")
    
    # Error message
    lines.append("**Error Message:**")
    lines.append("```")
    lines.append(bug.error_message)
    lines.append("```")
    lines.append("")
    
    # Location
    lines.append("**Location:**")
    lines.append(f"- File: `{bug.location['file_path']}`")
    lines.append(f"- Line: {bug.location['line_number']}")
    if bug.location.get('function'):
        lines.append(f"- Function: `{bug.location['function']}`")
    lines.append("")
    
    # Assertion details
    if bug.first_failing_assertion:
        assertion = bug.first_failing_assertion
        lines.append("**Assertion Details:**")
        lines.append(f"- Statement: `{assertion.statement}`")
        lines.append(f"- Line: {assertion.line}")
        lines.append(f"- Assertion {assertion.assertion_index} of {assertion.assert_total}")
        if assertion.assertions_not_evaluated > 0:
            lines.append(f"- {assertion.assertions_not_evaluated} assertion(s) not evaluated after this failure")
        if assertion.operator:
            lines.append(f"- Operator: `{assertion.operator}`")
        if assertion.actual:
            lines.append(f"- Actual: `{assertion.actual}`")
        if assertion.expected:
            lines.append(f"- Expected: `{assertion.expected}`")
        lines.append("")
    
    # Called symbols
    if bug.called_symbols:
        lines.append("**Called Symbols:**")
        for symbol in bug.called_symbols:
            if symbol.resolution == "resolved":
                lines.append(f"- `{symbol.name}` → `{symbol.symbol_id}` ({symbol.file}:{symbol.line_start})")
            else:
                lines.append(f"- `{symbol.name}` (unresolved)")
        lines.append("")
        
        if bug.inferred_source_module:
            lines.append(f"**Inferred Source Module:** `{bug.inferred_source_module}`")
            lines.append("")
    
    # Traceback
    if bug.frames:
        lines.append("**Traceback:**")
        lines.append("```")
        for frame in bug.frames:
            external_marker = " [EXTERNAL]" if frame.external else ""
            lines.append(f"  {frame.file}:{frame.line} in {frame.function}{external_marker}")
            if frame.code_line:
                lines.append(f"    {frame.code_line}")
        lines.append("```")
        lines.append("")
    
    # Test code
    if bug.code:
        lines.append("**Test Code:**")
        lines.append("```python")
        lines.append(bug.code)
        lines.append("```")
        lines.append("")
    
    # Source snapshot
    if bug.called_symbols:
        for symbol in bug.called_symbols:
            if symbol.source_snapshot:
                lines.append(f"**Source Snapshot ({symbol.name}):**")
                lines.append("```python")
                lines.append(symbol.source_snapshot)
                lines.append("```")
                lines.append("")
    
    # Rerun command
    lines.append(f"**Rerun Command:** `{bug.rerun_command}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    return lines
