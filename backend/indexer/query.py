"""Query API for repository index.

Provides convenient methods to query the index and retrieve source code.
"""

import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from common.paths import to_posix_rel
from common.hashing import sha1_file
from common.io import read_json
from .models import IndexData, SymbolInfo, FileInfo

logger = logging.getLogger(__name__)


class StaleIndexError(Exception):
    """Raised when the index doesn't match current file state."""
    pass


class RepoIndex:
    """Query interface for repository index."""
    
    def __init__(self, index_data: IndexData, project_root: Path):
        """Initialize the query interface.
        
        Args:
            index_data: Loaded index data
            project_root: Project root directory
        """
        self.data = index_data
        self.project_root = Path(project_root)
        self._symbol_cache: Dict[str, SymbolInfo] = index_data.symbols
        self._file_cache: Dict[str, FileInfo] = index_data.files
    
    @classmethod
    def load(cls, index_path: Path, project_root: Path) -> 'RepoIndex':
        """Load index from JSON file.
        
        Args:
            index_path: Path to index.json
            project_root: Project root directory
            
        Returns:
            RepoIndex instance
        """
        data_dict = read_json(index_path)
        index_data = IndexData.from_dict(data_dict)
        return cls(index_data, project_root)
    
    def get_symbol(self, symbol_id: str) -> Optional[SymbolInfo]:
        """Get symbol by ID.
        
        Args:
            symbol_id: Symbol ID (e.g., "src/calculator.py::subtract")
            
        Returns:
            SymbolInfo or None if not found
        """
        return self._symbol_cache.get(symbol_id)
    
    def find_symbol(self, name: str, hint_file: Optional[str] = None) -> List[SymbolInfo]:
        """Find symbols by name (fuzzy search).
        
        Args:
            name: Symbol name to search for
            hint_file: Optional file path to prioritize matches
            
        Returns:
            List of matching SymbolInfo, sorted by relevance
        """
        matches = []
        
        for symbol_id, symbol in self._symbol_cache.items():
            # Exact name match
            if symbol.name == name:
                matches.append((2, symbol))
            # Qualified name match
            elif symbol_id.endswith(f"::{name}"):
                matches.append((2, symbol))
            # Partial name match
            elif name in symbol.name:
                matches.append((1, symbol))
        
        # Sort by score (descending) and then by file (prioritize hint_file)
        matches.sort(key=lambda x: (
            -x[0],  # Higher score first
            0 if hint_file and x[1].file == hint_file else 1,  # Hint file first
            x[1].file,  # Then alphabetically
            x[1].line_start
        ))
        
        return [symbol for _, symbol in matches]
    
    def symbols_in_file(self, file_path: str) -> List[SymbolInfo]:
        """Get all symbols in a file.
        
        Args:
            file_path: POSIX relative file path
            
        Returns:
            List of SymbolInfo in the file, sorted by line number
        """
        symbols = [
            symbol for symbol in self._symbol_cache.values()
            if symbol.file == file_path
        ]
        symbols.sort(key=lambda s: s.line_start)
        return symbols
    
    def get_source(
        self,
        symbol_id: str,
        with_line_numbers: bool = False
    ) -> str:
        """Get source code for a symbol.
        
        Reads from disk and verifies SHA1 hash against index.
        
        Args:
            symbol_id: Symbol ID
            with_line_numbers: Include line numbers in output
            
        Returns:
            Source code string
            
        Raises:
            StaleIndexError: If file has changed since indexing
            ValueError: If symbol not found
        """
        symbol = self.get_symbol(symbol_id)
        if not symbol:
            raise ValueError(f"Symbol not found: {symbol_id}")
        
        file_path = self.project_root / symbol.file
        
        # Verify file hash
        current_hash = sha1_file(file_path)
        file_info = self._file_cache.get(symbol.file)
        if file_info and file_info.sha1 != current_hash:
            raise StaleIndexError(
                f"File {symbol.file} has changed since indexing. "
                f"Expected SHA1: {file_info.sha1}, got: {current_hash}"
            )
        
        # Read source
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Extract symbol lines (1-indexed to 0-indexed)
        start = symbol.line_start - 1
        end = symbol.line_end
        symbol_lines = lines[start:end]
        
        if with_line_numbers:
            # Add line numbers
            numbered_lines = []
            for i, line in enumerate(symbol_lines, start=symbol.line_start):
                numbered_lines.append(f"{i:4d} | {line}")
            return ''.join(numbered_lines)
        else:
            return ''.join(symbol_lines)
    
    def get_callers(self, symbol_id: str) -> List[str]:
        """Get list of symbols that call this symbol.
        
        Args:
            symbol_id: Symbol ID
            
        Returns:
            List of caller symbol IDs
        """
        callers = self.data.call_graph.get('callers', {})
        return callers.get(symbol_id, [])
    
    def get_callees(self, symbol_id: str) -> List[str]:
        """Get list of symbols called by this symbol.
        
        Args:
            symbol_id: Symbol ID
            
        Returns:
            List of callee symbol IDs
        """
        callees = self.data.call_graph.get('callees', {})
        return callees.get(symbol_id, [])
    
    def tests_for(self, symbol_id: str) -> List[str]:
        """Get tests that call this symbol.
        
        Args:
            symbol_id: Symbol ID
            
        Returns:
            List of test symbol IDs
        """
        tests = []
        for test_id, source_ids in self.data.test_to_source.items():
            if symbol_id in source_ids:
                tests.append(test_id)
        return tests
    
    def resolve_module(self, dotted_name: str) -> Optional[str]:
        """Resolve a dotted module name to a file path.
        
        Args:
            dotted_name: Module name (e.g., "calculator")
            
        Returns:
            POSIX relative file path or None
        """
        for file_path, file_info in self._file_cache.items():
            if file_info.module == dotted_name:
                return file_path
        return None
    
    def file_skeleton(self, file_path: str) -> str:
        """Get a skeleton view of a file (signatures only, no bodies).
        
        Args:
            file_path: POSIX relative file path
            
        Returns:
            File skeleton as string
        """
        symbols = self.symbols_in_file(file_path)
        
        if not symbols:
            return f"# {file_path}\n# (no symbols found)\n"
        
        lines = [f"# {file_path}\n"]
        
        for symbol in symbols:
            if symbol.kind == "class":
                lines.append(f"\nclass {symbol.name}:")
                if symbol.docstring:
                    lines.append(f'    """{symbol.docstring}"""')
            elif symbol.kind == "function":
                async_prefix = "async " if "async" in symbol.signature else ""
                lines.append(f"\n{async_prefix}def {symbol.name}{symbol.signature}:")
                if symbol.docstring:
                    lines.append(f'    """{symbol.docstring}"""')
            elif symbol.kind == "method":
                async_prefix = "async " if "async" in symbol.signature else ""
                lines.append(f"    {async_prefix}def {symbol.name}{symbol.signature}:")
                if symbol.docstring:
                    lines.append(f'        """{symbol.docstring}"""')
        
        return '\n'.join(lines) + '\n'
    
    def file_tree(self, prefix: Optional[str] = None, depth: int = 2) -> str:
        """Get a tree view of files in the project.
        
        Args:
            prefix: Optional path prefix to filter by
            depth: Maximum depth to display
            
        Returns:
            Tree view as string
        """
        # Collect files
        files = []
        for file_path, file_info in self._file_cache.items():
            if prefix and not file_path.startswith(prefix):
                continue
            files.append((file_path, file_info))
        
        files.sort(key=lambda x: x[0])
        
        # Build tree
        lines = []
        current_dir = None
        
        for file_path, file_info in files:
            parts = file_path.split('/')
            
            # Check depth
            if len(parts) > depth + 1:
                continue
            
            # Show directory header if changed
            if len(parts) > 1:
                dir_path = '/'.join(parts[:-1])
                if dir_path != current_dir:
                    current_dir = dir_path
                    lines.append(f"\n{dir_path}/")
            
            # Show file
            filename = parts[-1]
            indent = "  " * (len(parts) - 1)
            kind_marker = "[T]" if file_info.kind == "test" else "[S]"
            
            # Add file info
            info_parts = []
            if file_info.module:
                info_parts.append(f"module: {file_info.module}")
            if file_info.docstring:
                info_parts.append(f'"{file_info.docstring}"')
            
            info_str = f" ({', '.join(info_parts)})" if info_parts else ""
            lines.append(f"{indent}{kind_marker} {filename}{info_str}")
        
        return '\n'.join(lines) + '\n'
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """Get file info by path.
        
        Args:
            file_path: POSIX relative file path
            
        Returns:
            FileInfo or None if not found
        """
        return self._file_cache.get(file_path)
    
    def get_symbols_by_kind(self, kind: str) -> List[SymbolInfo]:
        """Get all symbols of a specific kind.
        
        Args:
            kind: Symbol kind ("function", "method", "class")
            
        Returns:
            List of matching symbols
        """
        return [s for s in self._symbol_cache.values() if s.kind == kind]
    
    def get_test_symbols(self) -> List[SymbolInfo]:
        """Get all test symbols.
        
        Returns:
            List of test symbols
        """
        return [s for s in self._symbol_cache.values() if s.is_test]
