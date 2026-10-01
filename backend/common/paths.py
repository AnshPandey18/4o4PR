"""Path normalization utilities for cross-platform compatibility.

Handles Windows/Unix path differences and converts all paths to POSIX format
relative to project root.
"""

import os
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import Tuple


def to_posix_rel(path: str | Path, root: str | Path) -> Tuple[str, bool]:
    """Convert a path to POSIX format relative to project root.
    
    Handles:
    - Windows backslashes and forward slashes
    - Windows drive letters (C:\\, D:\\, etc.)
    - Relative and absolute paths
    - Paths outside the project root (marked as external)
    
    Args:
        path: Path to normalize (can be absolute or relative)
        root: Project root path
        
    Returns:
        Tuple of (posix_relative_path, is_external)
        - posix_relative_path: POSIX-style path relative to root, or absolute if external
        - is_external: True if path is outside root or in site-packages
        
    Examples:
        >>> to_posix_rel("src\\calculator.py", "/project")
        ("src/calculator.py", False)
        >>> to_posix_rel("C:\\other\\file.py", "C:\\project")
        ("C:/other/file.py", True)
        >>> to_posix_rel("/usr/lib/python3.10/site-packages/pytest.py", "/project")
        ("/usr/lib/python3.10/site-packages/pytest.py", True)
    """
    # Convert to Path objects
    path_obj = Path(path)
    root_obj = Path(root).resolve()
    
    # Check if it's a site-packages or external library path
    path_str = str(path_obj)
    if 'site-packages' in path_str or 'dist-packages' in path_str:
        # Keep as POSIX absolute path and mark as external
        return path_str.replace('\\', '/'), True
    
    # Try to resolve the path
    try:
        # If path is relative, resolve it against root
        if not path_obj.is_absolute():
            resolved_path = (root_obj / path_obj).resolve()
        else:
            resolved_path = path_obj.resolve()
    except (OSError, ValueError):
        # If resolution fails (e.g., path doesn't exist), work with the path as-is
        if not path_obj.is_absolute():
            resolved_path = root_obj / path_obj
        else:
            resolved_path = path_obj
    
    # Try to make it relative to root
    try:
        rel_path = resolved_path.relative_to(root_obj)
        # Convert to POSIX format
        posix_path = rel_path.as_posix()
        return posix_path, False
    except ValueError:
        # Path is outside root - mark as external
        posix_path = resolved_path.as_posix()
        return posix_path, True


def normalize_path_in_string(text: str, root: str | Path) -> str:
    """Normalize path tokens in a string (e.g., traceback or error message).
    
    Replaces Windows-style paths with POSIX paths relative to root.
    Only normalizes tokens that look like file paths (contain .py and path separators).
    
    Args:
        text: Text containing path tokens
        root: Project root path
        
    Returns:
        Text with normalized paths
        
    Examples:
        >>> normalize_path_in_string("tests\\test_calc.py:21", "/project")
        "tests/test_calc.py:21"
        >>> normalize_path_in_string("Error in C:\\project\\src\\calc.py", "C:\\project")
        "Error in src/calc.py"
    """
    import re
    
    # Pattern to match file paths with .py extension
    # Matches: path\to\file.py or path/to/file.py or C:\path\to\file.py
    # Captures optional line number suffix like :123
    path_pattern = re.compile(
        r'(?:[A-Za-z]:[\\\/])?(?:[^\s:]+[\\\/])*[^\s:]+\.py(?::\d+)?'
    )
    
    def replace_path(match):
        path_token = match.group(0)
        # Check if it has a line number suffix
        if ':' in path_token and path_token.rsplit(':', 1)[1].isdigit():
            path_part, line_part = path_token.rsplit(':', 1)
            normalized, _ = to_posix_rel(path_part, root)
            return f"{normalized}:{line_part}"
        else:
            normalized, _ = to_posix_rel(path_token, root)
            return normalized
    
    return path_pattern.sub(replace_path, text)


def is_python_file(path: str | Path) -> bool:
    """Check if a path is a Python file.
    
    Args:
        path: Path to check
        
    Returns:
        True if path ends with .py
    """
    return str(path).endswith('.py')


def is_test_file(path: str | Path, test_dirs: list[str] = None) -> bool:
    """Check if a path is a test file.
    
    Args:
        path: Path to check
        test_dirs: List of test directory names (default: ["tests"])
        
    Returns:
        True if path is in a test directory or named test_*.py or *_test.py
    """
    if test_dirs is None:
        test_dirs = ["tests"]
    
    path_str = str(path).replace('\\', '/')
    parts = path_str.split('/')
    filename = parts[-1] if parts else ""
    
    # Check if in test directory
    for test_dir in test_dirs:
        if test_dir in parts:
            return True
    
    # Check if filename matches test pattern
    if filename.startswith('test_') or filename.endswith('_test.py') or filename == 'conftest.py':
        return True
    
    return False


def should_exclude(path: str | Path, exclude_patterns: list[str]) -> bool:
    """Check if a path should be excluded based on exclude patterns.
    
    Args:
        path: Path to check
        exclude_patterns: List of directory/file patterns to exclude
        
    Returns:
        True if path matches any exclude pattern
    """
    path_str = str(path).replace('\\', '/')
    parts = path_str.split('/')
    
    for pattern in exclude_patterns:
        if pattern in parts:
            return True
        if path_str.endswith(pattern):
            return True
    
    return False
