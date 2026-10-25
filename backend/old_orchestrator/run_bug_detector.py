#!/usr/bin/env python3
"""CLI tool to run Bug Detector on example code and generate reports.

Usage:
    python run_bug_detector.py                    # Scan all examples
    python run_bug_detector.py sample_bugs        # Scan specific example folder
    python run_bug_detector.py --list             # List available examples
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents import BugDetector
from app.models import BugReport, BugDetectionResult


def get_example_folders() -> List[Path]:
    """Get all example folders (those containing Python code and tests)."""
    examples_dir = Path(__file__).parent / "examples"
    
    # Find all subdirectories that have either .py files or a tests/ folder
    example_folders = []
    for item in examples_dir.iterdir():
        if item.is_dir() and item.name != "__pycache__":
            # Check if it has Python files or tests directory
            has_python = any(item.rglob("*.py"))
            if has_python:
                example_folders.append(item)
    
    return sorted(example_folders)


def generate_json_report(result: BugDetectionResult, output_path: Path) -> None:
    """Generate a JSON report of the bug detection results."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests_run": result.total_tests_run,
            "total_failures": result.total_failures,
            "pytest_exit_code": result.pytest_exit_code,
            "bugs_detected": len(result.bugs)
        },
        "bugs": []
    }
    
    for bug in result.bugs:
        report["bugs"].append({
            "test_name": bug.test_name,
            "error_type": bug.error_type,
            "error_message": bug.error_message,
            "location": {
                "file_path": bug.file_path,
                "line_number": bug.line_number
            },
            "inferred_source_module": bug.inferred_source_module,
            "code": {
                "failing_function": bug.failing_function_code,
                "context_before": bug.context_before,
                "context_after": bug.context_after
            },
            "traceback": bug.traceback
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def generate_markdown_report(result: BugDetectionResult, output_path: Path, repo_name: str) -> None:
    """Generate a human-readable markdown report."""
    lines = [
        f"# Bug Detection Report: {repo_name}",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n## Summary",
        f"\n- **Total Tests Run:** {result.total_tests_run}",
        f"- **Total Failures:** {result.total_failures}",
        f"- **Bugs Detected:** {len(result.bugs)}",
        f"- **Pytest Exit Code:** {result.pytest_exit_code}",
        f"- **Status:** {'❌ FAILURES DETECTED' if result.has_failures else '✅ ALL TESTS PASSED'}",
        f"\n---\n"
    ]
    
    if result.has_failures:
        lines.append("\n## Detected Bugs\n")
        
        for i, bug in enumerate(result.bugs, 1):
            lines.append(f"\n### Bug #{i}: {bug.test_name}\n")
            lines.append(f"**Error Type:** `{bug.error_type}`\n")
            lines.append(f"**Error Message:** {bug.error_message}\n")
            lines.append(f"**Location:** `{bug.file_path}:{bug.line_number}`\n")
            lines.append(f"**Inferred Source Module:** `{bug.inferred_source_module}`\n")
            
            lines.append(f"\n#### Failing Function Code\n")
            lines.append(f"```python\n{bug.failing_function_code}\n```\n")
            
            if bug.context_before:
                lines.append(f"\n#### Context Before\n")
                lines.append(f"```python\n{bug.context_before}\n```\n")
            
            if bug.context_after:
                lines.append(f"\n#### Context After\n")
                lines.append(f"```python\n{bug.context_after}\n```\n")
            
            if bug.traceback:
                lines.append(f"\n#### Full Traceback\n")
                lines.append(f"```\n{bug.traceback}\n```\n")
            
            lines.append("\n---\n")
    else:
        lines.append("\n## ✅ No Bugs Detected\n")
        lines.append("\nAll tests passed successfully!\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))


def print_terminal_report(result: BugDetectionResult, repo_name: str) -> None:
    """Print a colorful report to the terminal."""
    print("\n" + "=" * 80)
    print(f"BUG DETECTION REPORT: {repo_name}")
    print("=" * 80)
    
    print(f"\nSummary:")
    print(f"  * Total Tests Run: {result.total_tests_run}")
    print(f"  * Total Failures: {result.total_failures}")
    print(f"  * Bugs Detected: {len(result.bugs)}")
    print(f"  * Pytest Exit Code: {result.pytest_exit_code}")
    
    if result.has_failures:
        print(f"\n[!] Status: FAILURES DETECTED")
        print(f"\n{'=' * 80}")
        print(f"DETECTED BUGS ({len(result.bugs)} found)")
        print("=" * 80)
        
        for i, bug in enumerate(result.bugs, 1):
            print(f"\n[BUG #{i}] {bug.test_name}")
            print(f"   Error Type: {bug.error_type}")
            print(f"   Error Message: {bug.error_message}")
            print(f"   Location: {bug.file_path}:{bug.line_number}")
            print(f"   Inferred Source: {bug.inferred_source_module}")
            
            print(f"\n   Failing Function Code:")
            for line in bug.failing_function_code.splitlines():
                print(f"     {line}")
            
            if bug.context_before:
                print(f"\n   Context Before (last 3 lines):")
                for line in bug.context_before.splitlines()[-3:]:
                    print(f"     {line}")
            
            if bug.context_after:
                print(f"\n   Context After (first 3 lines):")
                for line in bug.context_after.splitlines()[:3]:
                    print(f"     {line}")
            
            print(f"\n   {'-' * 76}")
    else:
        print(f"\n[OK] Status: ALL TESTS PASSED")
        print("\nNo bugs detected! All tests passed successfully.")
    
    print("\n" + "=" * 80 + "\n")


def run_detection(example_path: Path, output_dir: Path) -> Optional[BugDetectionResult]:
    """Run bug detection on a single example folder."""
    print(f"\n[*] Scanning: {example_path.name}")
    print(f"    Path: {example_path}")
    
    try:
        detector = BugDetector(context_lines=5)
        result = detector.run(str(example_path))
        
        # Generate reports
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{example_path.name}_{timestamp}"
        
        # JSON report
        json_path = output_dir / f"{base_name}.json"
        generate_json_report(result, json_path)
        print(f"    [OK] JSON report: {json_path}")
        
        # Markdown report
        md_path = output_dir / f"{base_name}.md"
        generate_markdown_report(result, md_path, example_path.name)
        print(f"    [OK] Markdown report: {md_path}")
        
        # Terminal output
        print_terminal_report(result, example_path.name)
        
        return result
        
    except Exception as e:
        print(f"    [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run Bug Detector on example code and generate reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_bug_detector.py                    # Scan all examples
  python run_bug_detector.py sample_bugs        # Scan specific example
  python run_bug_detector.py --list             # List available examples
        """
    )
    parser.add_argument(
        "example",
        nargs="?",
        help="Specific example folder to scan (default: scan all)"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available example folders"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(__file__).parent / "evaluation" / "results",
        help="Output directory for reports (default: evaluation/results)"
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    args.output.mkdir(parents=True, exist_ok=True)
    
    # Get available examples
    example_folders = get_example_folders()
    
    if args.list:
        print("\nAvailable Example Folders:")
        if not example_folders:
            print("   (No example folders found)")
            print("\n   Create example folders in: backend/examples/")
            print("   Each folder should contain Python code and tests/")
        else:
            for folder in example_folders:
                print(f"   * {folder.name}")
        print()
        return 0
    
    # Determine what to scan
    if args.example:
        # Scan specific example
        example_path = Path(__file__).parent / "examples" / args.example
        if not example_path.exists():
            print(f"[ERROR] Example folder not found: {args.example}")
            print(f"\nAvailable examples:")
            for folder in example_folders:
                print(f"   * {folder.name}")
            return 1
        
        folders_to_scan = [example_path]
    else:
        # Scan all examples
        if not example_folders:
            print("[ERROR] No example folders found!")
            print("\nCreate example folders in: backend/examples/")
            print("   Each folder should contain:")
            print("     - src/ (your Python code)")
            print("     - tests/ (your test files)")
            print("\n   Example structure:")
            print("     backend/examples/my_buggy_code/")
            print("       |- src/")
            print("       |   |- calculator.py")
            print("       |- tests/")
            print("           |- test_calculator.py")
            return 1
        
        folders_to_scan = example_folders
    
    # Run detection on all selected folders
    print("\n" + "=" * 80)
    print("BUG DETECTOR - EXAMPLE CODE SCANNER")
    print("=" * 80)
    print(f"\nOutput directory: {args.output}")
    print(f"Folders to scan: {len(folders_to_scan)}")
    
    results = []
    for folder in folders_to_scan:
        result = run_detection(folder, args.output)
        if result:
            results.append((folder.name, result))
    
    # Summary
    if results:
        print("\n" + "=" * 80)
        print("OVERALL SUMMARY")
        print("=" * 80)
        
        total_bugs = sum(len(r.bugs) for _, r in results)
        total_failures = sum(r.total_failures for _, r in results)
        
        print(f"\nScanned {len(results)} example(s)")
        print(f"   * Total Bugs Detected: {total_bugs}")
        print(f"   * Total Test Failures: {total_failures}")
        print(f"\nReports saved to: {args.output}")
        
        print("\nExample Results:")
        for name, result in results:
            status = "[FAILED]" if result.has_failures else "[PASSED]"
            print(f"   * {name}: {status} ({len(result.bugs)} bugs)")
        
        print("\n" + "=" * 80 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
