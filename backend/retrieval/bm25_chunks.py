"""BM25 chunk builder - creates searchable chunks from index and source files.

Builds one chunk per function/method/constant with freshness validation.
Classes produce skeleton chunks (signature + docstring only, no method bodies).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import json

from common.hashing import sha1_file
from retrieval.tokenizer import tokenize


# Configuration
CLASS_CHUNK = "skeleton"  # Only name + signature + docstring for classes
INCLUDE_TEST_CHUNKS = False  # Exclude test symbols from search by default


class StaleIndexError(Exception):
    """Raised when source files have changed since index was built."""
    pass


@dataclass
class Chunk:
    """A searchable chunk of code."""
    id: str  # Symbol ID
    kind: str  # function, method, class, constant
    file: str  # POSIX relative path
    line_start: int
    line_end: int
    is_test: bool
    token_count: int
    term_frequencies: Dict[str, int]  # term -> count (sorted by term)


def build_chunks(
    index_path: Path,
    repo_root: Path
) -> List[Chunk]:
    """Build BM25 chunks from index and source files.
    
    Process:
    1. Load index.json
    2. Validate source file freshness (compare sha1)
    3. For each symbol:
       - Read source text from disk (line_start to line_end)
       - For classes: extract skeleton only (name + signature + docstring)
       - Tokenize: name + signature + docstring + source segment
       - Compute term frequencies
       - Create chunk with metadata
    4. Return list of chunks
    
    Args:
        index_path: Path to index.json
        repo_root: Root directory of the repository
        
    Returns:
        List of Chunk objects
        
    Raises:
        StaleIndexError: If any source file has changed since indexing
    """
    # Load index
    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
    
    # Validate freshness
    changed_files = []
    file_sha1s = {}
    
    # Handle both dict and array formats for files
    files_raw = index_data.get('files', {})
    if isinstance(files_raw, list):
        # Convert array format [{"path": ..., "sha1": ...}] to dict {"path": {"sha1": ...}}
        files_dict = {item['path']: item for item in files_raw}
    else:
        # Already a dict
        files_dict = files_raw
    
    for file_path, file_info in files_dict.items():
        expected_sha1 = file_info['sha1']
        file_sha1s[file_path] = expected_sha1
        
        # Compute current sha1
        full_path = repo_root / file_path
        if not full_path.exists():
            changed_files.append(f"{file_path} (deleted)")
            continue
        
        actual_sha1 = sha1_file(full_path)
        if actual_sha1 != expected_sha1:
            changed_files.append(file_path)
    
    if changed_files:
        raise StaleIndexError(
            f"Source files have changed since indexing: {', '.join(changed_files)}"
        )
    
    # Build chunks
    chunks = []
    
    # Handle both dict and array formats for symbols
    symbols_raw = index_data.get('symbols', {})
    if isinstance(symbols_raw, list):
        # Convert array format [{"symbol_id": ..., ...}] to dict {"symbol_id": {...}}
        symbols_dict = {item['symbol_id']: item for item in symbols_raw}
    else:
        # Already a dict
        symbols_dict = symbols_raw
    
    for symbol_id, symbol in symbols_dict.items():
        # Add symbol_id to the symbol dict for processing
        symbol_with_id = {**symbol, 'symbol_id': symbol_id}
        kind = symbol['kind']
        
        # Only chunk functions, methods, constants
        if kind not in ('function', 'method', 'constant'):
            # Classes get skeleton chunks
            if kind == 'class':
                chunk = _build_class_skeleton_chunk(symbol_with_id, repo_root)
                if chunk:
                    chunks.append(chunk)
            continue
        
        # Build regular chunk
        chunk = _build_chunk(symbol_with_id, repo_root)
        if chunk:
            chunks.append(chunk)
    
    return chunks


def _build_chunk(symbol: Dict, repo_root: Path) -> Optional[Chunk]:
    """Build a chunk for a function/method/constant.
    
    Args:
        symbol: Symbol dictionary from index
        repo_root: Repository root path
        
    Returns:
        Chunk object or None if chunk is empty
    """
    symbol_id = symbol['symbol_id']
    kind = symbol['kind']
    file_path = symbol['file']
    line_start = symbol['line_start']
    line_end = symbol['line_end']
    is_test = symbol.get('is_test', False)
    
    # Build chunk text
    text_parts = []
    
    # Add name
    text_parts.append(symbol['name'])
    
    # Add signature if present
    if symbol.get('signature'):
        text_parts.append(symbol['signature'])
    
    # Add docstring if present
    if symbol.get('docstring'):
        text_parts.append(symbol['docstring'])
    
    # Read source segment from disk
    full_path = repo_root / file_path
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # line_start and line_end are 1-indexed
            segment_lines = lines[line_start - 1:line_end]
            source_segment = ''.join(segment_lines)
            text_parts.append(source_segment)
    except (IOError, IndexError) as e:
        # If reading fails, use value_preview for constants
        if kind == 'constant' and symbol.get('value_preview'):
            text_parts.append(symbol['value_preview'])
        # Otherwise, just use what we have (name + signature + docstring)
    
    # Tokenize
    chunk_text = ' '.join(text_parts)
    tokens = tokenize(chunk_text)
    
    # Compute term frequencies
    term_freq = {}
    for token in tokens:
        term_freq[token] = term_freq.get(token, 0) + 1
    
    # Skip chunks with zero tokens
    if not term_freq:
        return None
    
    # Create chunk
    chunk = Chunk(
        id=symbol_id,
        kind=kind,
        file=file_path,
        line_start=line_start,
        line_end=line_end,
        is_test=is_test,
        token_count=len(tokens),
        term_frequencies=dict(sorted(term_freq.items()))  # Sort by term
    )
    
    return chunk


def _build_class_skeleton_chunk(symbol: Dict, repo_root: Path) -> Optional[Chunk]:
    """Build a skeleton chunk for a class (name + signature + docstring only).
    
    Args:
        symbol: Class symbol dictionary from index
        repo_root: Repository root path
        
    Returns:
        Chunk object or None if chunk is empty
    """
    symbol_id = symbol['symbol_id']
    file_path = symbol['file']
    line_start = symbol['line_start']
    line_end = symbol['line_end']
    is_test = symbol.get('is_test', False)
    
    # Build skeleton text (no method bodies)
    text_parts = []
    
    # Add class name
    text_parts.append(symbol['name'])
    
    # Add signature if present (class definition line)
    if symbol.get('signature'):
        text_parts.append(symbol['signature'])
    
    # Add docstring if present
    if symbol.get('docstring'):
        text_parts.append(symbol['docstring'])
    
    # Tokenize
    chunk_text = ' '.join(text_parts)
    tokens = tokenize(chunk_text)
    
    # Compute term frequencies
    term_freq = {}
    for token in tokens:
        term_freq[token] = term_freq.get(token, 0) + 1
    
    # Skip chunks with zero tokens
    if not term_freq:
        return None
    
    # Create chunk
    chunk = Chunk(
        id=symbol_id,
        kind='class',
        file=file_path,
        line_start=line_start,
        line_end=line_end,
        is_test=is_test,
        token_count=len(tokens),
        term_frequencies=dict(sorted(term_freq.items()))
    )
    
    return chunk


def get_searchable_chunks(chunks: List[Chunk]) -> List[Chunk]:
    """Filter chunks to get searchable ones (non-test, non-empty).
    
    Args:
        chunks: List of all chunks
        
    Returns:
        List of chunks that should be searchable
    """
    if INCLUDE_TEST_CHUNKS:
        return [c for c in chunks if c.token_count > 0]
    else:
        return [c for c in chunks if c.token_count > 0 and not c.is_test]
