"""Content hashing utilities for cache invalidation and change detection."""

import hashlib
from pathlib import Path
from typing import List


def content_hash(
    project_root: Path,
    import_roots: List[str],
    exclude_patterns: List[str],
    schema_version: str
) -> str:
    """Compute a stable content hash of the project's Python files.
    
    The hash includes:
    - All .py files in the project (sorted by relative path)
    - File contents (bytes)
    - Import roots configuration
    - Schema version
    
    This ensures the hash changes when any code changes, when import roots
    change, or when the indexing schema version changes.
    
    Args:
        project_root: Root directory of the project
        import_roots: List of import root directories
        exclude_patterns: Patterns to exclude from hashing
        schema_version: Version string of the index schema
        
    Returns:
        SHA256 hash as hex string (64 characters)
    """
    hasher = hashlib.sha256()
    
    # Add schema version
    hasher.update(f"schema:{schema_version}".encode('utf-8'))
    
    # Add import roots
    hasher.update(f"import_roots:{','.join(sorted(import_roots))}".encode('utf-8'))
    
    # Collect all Python files
    py_files = []
    for py_file in project_root.rglob("*.py"):
        # Skip excluded directories
        if _should_exclude(py_file, project_root, exclude_patterns):
            continue
        
        try:
            rel_path = py_file.relative_to(project_root)
            py_files.append((str(rel_path).replace('\\', '/'), py_file))
        except ValueError:
            continue
    
    # Sort by relative path for deterministic order
    py_files.sort(key=lambda x: x[0])
    
    # Hash each file
    for rel_path, file_path in py_files:
        hasher.update(f"file:{rel_path}".encode('utf-8'))
        try:
            with open(file_path, 'rb') as f:
                hasher.update(f.read())
        except (IOError, OSError):
            # If we can't read a file, include its path but mark it unreadable
            hasher.update(b"<unreadable>")
    
    return hasher.hexdigest()


def sha1_file(file_path: Path) -> str:
    """Compute SHA1 hash of a file's contents.
    
    Args:
        file_path: Path to file
        
    Returns:
        SHA1 hash as hex string (40 characters)
    """
    hasher = hashlib.sha1()
    
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
    except (IOError, OSError):
        return ""
    
    return hasher.hexdigest()


def sha1_string(text: str) -> str:
    """Compute SHA1 hash of a string.
    
    Args:
        text: String to hash
        
    Returns:
        SHA1 hash as hex string (40 characters)
    """
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


def short_hash(text: str, length: int = 12) -> str:
    """Compute a short hash of a string.
    
    Args:
        text: String to hash
        length: Length of hash to return (default 12)
        
    Returns:
        First 'length' characters of SHA1 hash
    """
    return sha1_string(text)[:length]


def _should_exclude(file_path: Path, project_root: Path, exclude_patterns: List[str]) -> bool:
    """Check if a file should be excluded from hashing.
    
    Args:
        file_path: File path to check
        project_root: Project root directory
        exclude_patterns: List of patterns to exclude
        
    Returns:
        True if file should be excluded
    """
    try:
        rel_path = file_path.relative_to(project_root)
        parts = rel_path.parts
        
        for pattern in exclude_patterns:
            if pattern in parts:
                return True
            if str(rel_path).replace('\\', '/').startswith(pattern):
                return True
        
        return False
    except ValueError:
        return True
