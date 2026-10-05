"""Deterministic application of validated function replacement candidates."""

from __future__ import annotations

import ast
import difflib
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from common.io import write_text
from .patch_generator import PatchCandidate


class PatchApplicationError(ValueError):
    """Raised when a patch candidate cannot be safely applied."""


@dataclass
class PatchApplicationResult:
    file: str
    qualified_name: str
    diff: str
    changed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "qualified_name": self.qualified_name,
            "diff": self.diff,
            "changed": self.changed,
        }


class PatchApplier:
    """Apply only a complete function replacement inside a source file."""

    def apply(self, project_root: Path, candidate: PatchCandidate) -> PatchApplicationResult:
        relative_file = self._validate_target(candidate)
        path = (Path(project_root) / relative_file).resolve()
        root = Path(project_root).resolve()
        if root not in path.parents:
            raise PatchApplicationError("Patch target escapes the project root")
        if not path.exists() or not path.is_file():
            raise PatchApplicationError(f"Patch target does not exist: {relative_file}")

        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        start = candidate.target["line_start"] - 1
        end = candidate.target["line_end"]
        if start >= len(lines) or end > len(lines):
            raise PatchApplicationError("Patch target line range is outside the file")

        replacement = textwrap.dedent(candidate.replacement_code).strip("\n") + "\n"
        try:
            ast.parse(replacement)
        except SyntaxError as exc:
            raise PatchApplicationError(f"Replacement code is invalid Python: {exc}") from exc

        indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
        if indent:
            replacement = "\n".join(
                f"{indent}{line}" if line.strip() else line
                for line in replacement.splitlines()
            ) + "\n"

        updated = "".join(lines[:start]) + replacement + "".join(lines[end:])
        try:
            ast.parse(updated)
        except SyntaxError as exc:
            raise PatchApplicationError(f"Updated file is invalid Python: {exc}") from exc

        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=relative_file.as_posix(),
            tofile=relative_file.as_posix(),
        ))
        if diff:
            write_text(path, updated)
        return PatchApplicationResult(
            file=relative_file.as_posix(),
            qualified_name=candidate.target["qualified_name"],
            diff=diff,
            changed=bool(diff),
        )

    @staticmethod
    def _validate_target(candidate: PatchCandidate) -> Path:
        target = candidate.target
        relative = Path(target["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise PatchApplicationError("Patch target must be a relative path inside the project")
        if relative.suffix != ".py":
            raise PatchApplicationError("Patch target must be a Python source file")
        normalized = relative.as_posix().lower()
        if normalized.startswith("tests/") or "/tests/" in normalized or normalized.endswith("conftest.py"):
            raise PatchApplicationError("Tests cannot be modified by the patch applier")
        if any(part.startswith(".") and part in {".env", ".git"} for part in relative.parts):
            raise PatchApplicationError("Hidden configuration files cannot be modified")
        return relative