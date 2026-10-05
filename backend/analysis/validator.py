"""Run the target test suite after a patch and return structured results."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ValidationResult:
    passed: bool
    exit_code: int
    tests_run: int
    failures: int
    output: str
    baseline_regressions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "exit_code": self.exit_code,
            "tests_run": self.tests_run,
            "failures": self.failures,
            "output": self.output,
            "baseline_regressions": self.baseline_regressions,
        }


class TestValidator:
    """Execute pytest without invoking a shell."""

    def __init__(self, timeout_seconds: int = 300) -> None:
        self.timeout_seconds = timeout_seconds

    def validate(self, project_root: Path, baseline: Optional[Dict[str, str]] = None) -> ValidationResult:
        try:
            completed = subprocess.run(
                ["python", "-m", "pytest", "-q"],
                cwd=Path(project_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
            tests_run, failures = self._parse_summary(output)
            regressions = 0
            if baseline:
                regressions = self._count_regressions(output, baseline)
            return ValidationResult(
                passed=completed.returncode == 0 and regressions == 0,
                exit_code=completed.returncode,
                tests_run=tests_run,
                failures=failures,
                output=output,
                baseline_regressions=regressions,
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            return ValidationResult(False, 124, 0, 0, output + "\npytest timed out", 0)

    @staticmethod
    def _parse_summary(output: str):
        match = re.search(r"(?:(\d+) passed)?(?:, )?(?:(\d+) failed)?", output)
        if not match:
            return 0, 0
        passed = int(match.group(1) or 0)
        failed = int(match.group(2) or 0)
        return passed + failed, failed

    @staticmethod
    def _count_regressions(output: str, baseline: Dict[str, str]) -> int:
        if not baseline:
            return 0
        failed_tests = set(re.findall(r"FAILED\s+([^\s]+)", output))
        return sum(1 for test_name, status in baseline.items() if status == "passed" and test_name in failed_tests)