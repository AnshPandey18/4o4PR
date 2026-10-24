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
    """
    symbol_id: str  # "file::qualified_name" or "file::ClassName.method"
    kind: str  # "function", "method", "class", "constant"
    name: str  # Simple name (last component)
    file: str  # POSIX relative path
    line_start: int  # First decorator's line if decorated (TASK 6)
    line_end: int
    signature: Optional[str]  # None for constants/classes without __init__
    decorators: List[str] = field(default_factory=list)
    decorator_targets: List[str] = field(default_factory=list)  # TASK 5: Resolved decorator symbol IDs
    docstring: Optional[str] = None
    parent_class: Optional[str] = None  # For methods
    is_test: bool = False
    
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
    """Information about a file that failed to parse."""
    file: str
    line: int
    message: str


@dataclass
class IndexData:
    """Complete repository index data.
    
    TASK 4: Uses UTC timezone for generated_at and run_id.
    TASK 6: Includes test_to_source_transitive.
    TASK 5: call_graph includes references and referenced_by.
    """
    schema_version: str
    run_id: str  # Generated from UTC time: r_YYYYMMDD_HHMMSS
    content_hash: str
    generated_at: str  # ISO format with Z suffix from UTC
    import_roots: List[str]
    files: Dict[str, FileInfo]
    symbols: Dict[str, SymbolInfo]
    call_graph: Dict[str, Any]
    # call_graph structure:
    # {
    #   "callees": {symbol_id: [callee_ids]},
    #   "callers": {symbol_id: [caller_ids]},
    #   "references": {symbol_id: [constant_ids]},  # TASK 5
    #   "referenced_by": {constant_id: [symbol_ids]}  # TASK 5
    # }
    test_to_source: Dict[str, List[str]]  # Direct mapping
    test_to_source_transitive: Dict[str, List[str]] = field(default_factory=dict)  # TASK 6
    parse_errors: List[ParseError] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'schema_version': self.schema_version,
            'run_id': self.run_id,
            'content_hash': self.content_hash,
            'generated_at': self.generated_at,
            'import_roots': self.import_roots,
            'files': {
                path: {
                    'kind': info.kind,
                    'module': info.module,
                    'lines': info.lines,
                    'sha1': info.sha1,
                    'parse_ok': info.parse_ok,
                    'docstring': info.docstring,
                    'imports': info.imports  # TASK 3: Complete import structure
                }
                for path, info in self.files.items()
            },
            'symbols': {
                sid: {
                    'kind': sym.kind,
                    'name': sym.name,
                    'file': sym.file,
                    'line_start': sym.line_start,  # TASK 6: First decorator if present
                    'line_end': sym.line_end,
                    'signature': sym.signature,
                    'decorators': sym.decorators,
                    'decorator_targets': sym.decorator_targets,  # TASK 5: Resolved decorators
                    'docstring': sym.docstring,
                    'parent_class': sym.parent_class,
                    'is_test': sym.is_test,
                    'unresolved_calls': sym.unresolved_calls,  # TASK 1: Count
                    'unresolved': sym.unresolved,  # TASK 1: Detailed list
                    'builtin_calls': sorted(sym.builtin_calls),  # TASK 1: Builtins
                    'line_count': sym.line_count,  # TASK 6: Metrics
                    'char_count': sym.char_count,
                    'approx_tokens': sym.approx_tokens,
                    'value_preview': sym.value_preview,  # TASK 5: Constants
                    'references': sym.references,  # TASK 5: Constant references
                    # Schema 1.2 class fields - always emit for shape consistency
                    # Empty for non-classes, populated for classes
                    'children': sym.children,
                    'bases': sym.bases,
                    'bases_unresolved': sym.bases_unresolved,
                    'attr_types': sym.attr_types
                }
                for sid, sym in self.symbols.items()
            },
            'call_graph': self.call_graph,  # TASK 5: Includes references/referenced_by
            'test_to_source': self.test_to_source,
            'test_to_source_transitive': self.test_to_source_transitive,  # TASK 6
            'parse_errors': [
                {'file': err.file, 'line': err.line, 'message': err.message}
                for err in self.parse_errors
            ]
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'IndexData':
        """Create from dictionary loaded from JSON."""
        files = {
            path: FileInfo(
                path=path,
                kind=info['kind'],
                module=info.get('module'),
                lines=info['lines'],
                sha1=info['sha1'],
                parse_ok=info['parse_ok'],
                docstring=info.get('docstring'),
                imports=info.get('imports', [])  # TASK 3: Preserves import structure
            )
            for path, info in data['files'].items()
        }
        
        symbols = {
            sid: SymbolInfo(
                symbol_id=sid,
                kind=sym['kind'],
                name=sym['name'],
                file=sym['file'],
                line_start=sym['line_start'],
                line_end=sym['line_end'],
                signature=sym.get('signature'),
                decorators=sym.get('decorators', []),
                decorator_targets=sym.get('decorator_targets', []),  # TASK 5: Resolved decorators
                docstring=sym.get('docstring'),
                parent_class=sym.get('parent_class'),
                is_test=sym.get('is_test', False),
                unresolved_calls=sym.get('unresolved_calls', 0),  # TASK 1
                unresolved=sym.get('unresolved', []),  # TASK 1
                builtin_calls=sym.get('builtin_calls', []),  # TASK 1
                line_count=sym.get('line_count', 0),  # TASK 6
                char_count=sym.get('char_count', 0),
                approx_tokens=sym.get('approx_tokens', 0),
                value_preview=sym.get('value_preview'),  # TASK 5
                references=sym.get('references', []),  # TASK 5
                children=sym.get('children', []),  # TASK 2: Class methods (Schema 1.2)
                bases=sym.get('bases', []),  # TASK 2: Resolved base classes (Schema 1.2)
                bases_unresolved=sym.get('bases_unresolved', []),  # TASK 2: Unresolved bases (Schema 1.2)
                attr_types=sym.get('attr_types', {})  # TASK 3: Class attribute types (Schema 1.2)
            )
            for sid, sym in data['symbols'].items()
        }
        
        parse_errors = [
            ParseError(file=err['file'], line=err['line'], message=err['message'])
            for err in data.get('parse_errors', [])
        ]
        
        return IndexData(
            schema_version=data['schema_version'],
            run_id=data['run_id'],
            content_hash=data['content_hash'],
            generated_at=data['generated_at'],
            import_roots=data['import_roots'],
            files=files,
            symbols=symbols,
            call_graph=data['call_graph'],
            test_to_source=data['test_to_source'],
            test_to_source_transitive=data.get('test_to_source_transitive', {}),  # TASK 6
            parse_errors=parse_errors
        )
