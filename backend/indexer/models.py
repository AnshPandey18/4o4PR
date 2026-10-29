"""Data models for repository index with comprehensive task fixes.

Implements all requirements:
- Task 1: Unresolved calls with details
- Task 3: Import consistency
- Task 4: UTC timezone handling
- Task 5: Constants, classes, references
- Task 6: Metrics and transitive mappings
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FileInfo:
    """Information about a Python file.
    
    TASK 3: Imports have consistent structure with style, level, module, names, resolved_file.
    """
    path: str  # POSIX relative path
    kind: str  # "source" or "test"
    module: Optional[str]  # Dotted module name
    lines: int
    sha1: str
    parse_ok: bool
    docstring: Optional[str] = None
    imports: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SymbolInfo:
    """Information about a function, class, method, or constant.
    
    TASK 5: Added support for constants, classes, methods with proper metadata.
    TASK 1: Includes unresolved_calls with detailed unresolved list and builtin_calls.
    TASK 6: Includes metrics: line_count, char_count, approx_tokens.
    S2-A: Added qualified_name field (D1).
    S2-C: Added is_async field (D3).
    """
    symbol_id: str  # "file::qualified_name" or "file::ClassName.method"
    kind: str  # "function", "method", "class", "constant", "module"
    name: str  # Simple name (last component)
    qualified_name: str  # Qualified name: "func", "Class.method", "Outer.Inner.method"
    file: str  # POSIX relative path
    line_start: int  # First decorator's line if decorated (TASK 6)
    line_end: int
    signature: Optional[str]  # None for constants/classes without __init__
    decorators: List[str] = field(default_factory=list)
    decorator_targets: List[str] = field(default_factory=list)  # TASK 5: Resolved decorator symbol IDs
    docstring: Optional[str] = None
    parent_class: Optional[str] = None  # For methods
    is_test: bool = False
    is_async: bool = False  # S2-C: True for async def (D3)
    
    # TASK 1: Unresolved calls with details
    unresolved_calls: int = 0  # Count of unresolved calls
    unresolved: List[Dict[str, Any]] = field(default_factory=list)
    # Each entry: {expr, name, line, reason}
    # reason: "method_on_unknown_receiver", "dynamic_call", "external_module", "not_found"
    
    # TASK 1: Builtin function/method calls
    builtin_calls: List[str] = field(default_factory=list)
    # List of builtin names: len, sum, print, str.upper, list.append, etc.
    
    # TASK 6: Metrics
    line_count: int = 0  # Number of lines in symbol
    char_count: int = 0  # Character count // 4
    approx_tokens: int = 0  # Approximate token count
    
    # TASK 5: Constant-specific
    value_preview: Optional[str] = None  # Source segment (max 80 chars)
    
    # TASK 5: References to constants (populated after extraction)
    references: List[str] = field(default_factory=list)  # List of constant IDs used
    
    # TASK 2: Class-specific fields (Schema 1.2)
    children: List[str] = field(default_factory=list)  # Method symbol IDs (for classes)
    bases: List[str] = field(default_factory=list)  # Resolved base class symbol IDs
    bases_unresolved: List[str] = field(default_factory=list)  # Unresolved base names
    
    # TASK 3: Class attribute types (Schema 1.2)
    attr_types: Dict[str, str] = field(default_factory=dict)  # attr_name -> class symbol ID


@dataclass
class ParseError:
    """Information about a file that failed to parse.
    
    S2-G: Added stage, column, reason fields (D4).
    """
    file: str
    stage: str  # "read" or "parse"
    line: int
    column: Optional[int] = None  # For parse errors only
    reason: str = ""  # "encoding or IO error" for read, exception type for parse
    message: str = ""  # Full error message (kept for compatibility)


@dataclass
class CallReference:
    """A function call reference.
    
    S2-B, S2-E: Call records with caller, callee, line (D2, D4).
    """
    kind: str = "call"  # Always "call"
    caller: str = ""  # symbol_id or "<module>"
    callee: str = ""  # Expression text or resolved symbol_id
    line: int = 0  # Line where call starts
    file: str = ""  # File containing the call


@dataclass
class ImportReference:
    """An import statement reference.
    
    S2-D: Import records (D4).
    """
    kind: str = "import"  # "import" or "import_from"
    file: str = ""
    line: int = 0
    module: str = ""
    names: List[Dict[str, Any]] = field(default_factory=list)
    level: int = 0  # For relative imports
    resolved_file: Optional[str] = None


@dataclass
class ModuleSymbol:
    """A module symbol record.
    
    S2-F: Module records (D4).
    """
    symbol_id: str
    kind: str = "module"
    name: str = ""
    qualified_name: str = ""
    file: str = ""
    line_start: int = 1
    line_end: int = 1
    docstring: Optional[str] = None


@dataclass
class IndexData:
    """Complete repository index data.
    
    TASK 4: Uses UTC timezone for generated_at and run_id.
    TASK 6: Includes test_to_source_transitive.
    TASK 5: call_graph includes references and referenced_by.
    S2-D: Separate symbols, references, failures lists (D4).
    
    Schema 13: New architecture format with fingerprint validation.
    """
    schema_version: str
    run_id: str  # Generated from UTC time: r_YYYYMMDD_HHMMSS
    content_hash: str  # Now called fingerprint in output
    generated_at: str  # ISO format with Z suffix from UTC
    import_roots: List[str]
    repo_path: str  # Added for schema 13
    indexer_version: str  # Added for schema 13
    commit: Optional[str] = None  # Git commit hash or null
    symbols: List[Dict[str, Any]] = field(default_factory=list)  # S2-D: List of symbol records
    references: List[Dict[str, Any]] = field(default_factory=list)  # S2-D: List of call/import records
    failures: List[Dict[str, Any]] = field(default_factory=list)  # S2-G: List of failure records
    # Legacy fields kept for compatibility with existing tools
    files: Dict[str, FileInfo] = field(default_factory=dict)
    call_graph: Dict[str, Any] = field(default_factory=dict)  # Kept internally
    test_to_source: Dict[str, List[str]] = field(default_factory=dict)
    test_to_source_transitive: Dict[str, List[str]] = field(default_factory=dict)
    parse_errors: List[ParseError] = field(default_factory=list)  # Legacy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.
        
        Schema 13 format: {schema_version, commit, fingerprint, indexer_version, 
                          repo_path, symbols, references, failures}
        Also keeps legacy fields for backward compatibility.
        """
        # Build backward-compatible symbols dict from list for legacy code
        symbols_dict = {}
        for sym in self.symbols:
            if sym['kind'] != 'module':  # Exclude modules from legacy dict
                symbols_dict[sym['id']] = sym
        
        return {
            # Schema 13 required fields
            'schema_version': self.schema_version,
            'commit': self.commit,
            'fingerprint': self.content_hash,  # Renamed from content_hash
            'indexer_version': self.indexer_version,
            'repo_path': self.repo_path,
            'symbols': self.symbols,  # New list structure
            'references': self.references,  # New list structure
            'failures': self.failures,  # New list structure
            
            # Legacy fields for compatibility
            'run_id': self.run_id,
            'content_hash': self.content_hash,
            'generated_at': self.generated_at,
            'import_roots': self.import_roots,
            'symbols_dict': symbols_dict,  # Legacy dict format
            'files': {
                path: {
                    'kind': info.kind,
                    'module': info.module,
                    'lines': info.lines,
                    'sha1': info.sha1,
                    'parse_ok': info.parse_ok,
                    'docstring': info.docstring,
                    'imports': info.imports
                }
                for path, info in self.files.items()
            },
            'call_graph': self.call_graph,
            'test_to_source': self.test_to_source,
            'test_to_source_transitive': self.test_to_source_transitive,
            'parse_errors': [
                {
                    'file': err.file,
                    'stage': err.stage,
                    'line': err.line,
                    'column': err.column,
                    'reason': err.reason,
                    'message': err.message
                }
                for err in self.parse_errors
            ]
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'IndexData':
        """Create from dictionary loaded from JSON.
        
        Handles both schema 13 and legacy formats.
        """
        # Handle legacy 'files' structure
        files = {}
        if 'files' in data:
            files = {
                path: FileInfo(
                    path=path,
                    kind=info['kind'],
                    module=info.get('module'),
                    lines=info['lines'],
                    sha1=info['sha1'],
                    parse_ok=info['parse_ok'],
                    docstring=info.get('docstring'),
                    imports=info.get('imports', [])
                )
                for path, info in data['files'].items()
            }
        
        # Handle legacy parse_errors or new failures
        parse_errors = []
        if 'failures' in data:
            parse_errors = [
                ParseError(
                    file=err['file'],
                    stage=err.get('stage', 'parse'),
                    line=err['line'],
                    column=err.get('column'),
                    reason=err.get('reason', ''),
                    message=err.get('message', '')
                )
                for err in data['failures']
            ]
        elif 'parse_errors' in data:
            parse_errors = [
                ParseError(
                    file=err['file'],
                    stage='parse',
                    line=err['line'],
                    column=None,
                    reason='',
                    message=err.get('message', '')
                )
                for err in data.get('parse_errors', [])
            ]
        
        # Get symbols list (schema 13 has it at top level, legacy has symbols_list)
        symbols_list = data.get('symbols', [])
        if not isinstance(symbols_list, list):
            # Legacy format - symbols is a dict, look for symbols_list
            symbols_list = data.get('symbols_list', [])
        
        return IndexData(
            schema_version=data['schema_version'],
            run_id=data.get('run_id', ''),
            content_hash=data.get('fingerprint', data.get('content_hash', '')),
            generated_at=data.get('generated_at', ''),
            import_roots=data.get('import_roots', []),
            repo_path=data.get('repo_path', ''),
            indexer_version=data.get('indexer_version', ''),
            commit=data.get('commit'),
            symbols=symbols_list,
            references=data.get('references', []),
            failures=[
                {
                    'file': err.file,
                    'stage': err.stage,
                    'line': err.line,
                    'column': err.column,
                    'reason': err.reason,
                    'message': err.message
                }
                for err in parse_errors
            ],
            files=files,
            call_graph=data.get('call_graph', {}),
            test_to_source=data.get('test_to_source', {}),
            test_to_source_transitive=data.get('test_to_source_transitive', {}),
            parse_errors=parse_errors
        )
