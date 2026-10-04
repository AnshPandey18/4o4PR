"""Atomic file I/O operations with deterministic JSON serialization."""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict


def write_json(file_path: Path, data: Dict[str, Any]) -> None:
    """Write JSON to file atomically with deterministic formatting.
    
    Uses atomic write pattern: write to temp file, then rename.
    JSON is formatted with sorted keys and 2-space indentation for
    deterministic output.
    
    Args:
        file_path: Destination file path
        data: Dictionary to serialize
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Serialize with deterministic formatting
    json_content = json.dumps(
        data,
        indent=2,
        sort_keys=True,
        ensure_ascii=False
    )
    
    # Write to temp file in the same directory (for atomic rename)
    temp_fd, temp_path = tempfile.mkstemp(
        dir=file_path.parent,
        prefix=f".{file_path.name}.",
        suffix=".tmp"
    )
    
    try:
        # Write content
        with open(temp_fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(json_content)
            if not json_content.endswith('\n'):
                f.write('\n')
        
        # Atomic rename
        Path(temp_path).replace(file_path)
    except:
        # Clean up temp file on error
        try:
            Path(temp_path).unlink()
        except:
            pass
        raise


def read_json(file_path: Path) -> Dict[str, Any]:
    """Read JSON from file.
    
    Args:
        file_path: Source file path
        
    Returns:
        Parsed JSON data
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_text(file_path: Path, text: str) -> None:
    """Write text to file atomically.
    
    Args:
        file_path: Destination file path
        text: Text content to write
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file in the same directory
    temp_fd, temp_path = tempfile.mkstemp(
        dir=file_path.parent,
        prefix=f".{file_path.name}.",
        suffix=".tmp"
    )
    
    try:
        # Write content
        with open(temp_fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
            if not text.endswith('\n'):
                f.write('\n')
        
        # Atomic rename
        Path(temp_path).replace(file_path)
    except:
        # Clean up temp file on error
        try:
            Path(temp_path).unlink()
        except:
            pass
        raise


def read_text(file_path: Path) -> str:
    """Read text from file.
    
    Args:
        file_path: Source file path
        
    Returns:
        File contents as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def ensure_dir(dir_path: Path) -> None:
    """Ensure a directory exists.
    
    Args:
        dir_path: Directory path to create
    """
    Path(dir_path).mkdir(parents=True, exist_ok=True)
