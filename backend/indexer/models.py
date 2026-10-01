"""Data models for repository index."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FileInfo:
    """Information about a Python file."""
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
    """Information about a function, class, or method."""
    symbol_id: str  # "file::qualified_name"
    kind: str  # "function", "method", "class"
    name: str
    file: str  # POSIX relative path
    line_start: int
    line_end: int
    signature: str
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    parent_class: Optional[str] = None
    is_test: bool = False
    unresolved_calls: int = 0


@dataclass
class ParseError:
    """Information about a file that failed to parse."""
    file: str
    line: int
    message: str


@dataclass
class IndexData:
    """Complete repository index data."""
    schema_version: str
    run_id: str
    content_hash: str
    generated_at: str
    import_roots: List[str]
    files: Dict[str, FileInfo]
    symbols: Dict[str, SymbolInfo]
    call_graph: Dict[str, Any]  # {"callees": {}, "callers": {}}
    test_to_source: Dict[str, List[str]]
    parse_errors: List[ParseError]
    
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
                    'imports': info.imports
                }
                for path, info in self.files.items()
            },
            'symbols': {
                sid: {
                    'kind': sym.kind,
                    'name': sym.name,
                    'file': sym.file,
                    'line_start': sym.line_start,
                    'line_end': sym.line_end,
                    'signature': sym.signature,
                    'decorators': sym.decorators,
                    'docstring': sym.docstring,
                    'parent_class': sym.parent_class,
                    'is_test': sym.is_test,
                    'unresolved_calls': sym.unresolved_calls
                }
                for sid, sym in self.symbols.items()
            },
            'call_graph': self.call_graph,
            'test_to_source': self.test_to_source,
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
                imports=info.get('imports', [])
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
                signature=sym['signature'],
                decorators=sym.get('decorators', []),
                docstring=sym.get('docstring'),
                parent_class=sym.get('parent_class'),
                is_test=sym.get('is_test', False),
                unresolved_calls=sym.get('unresolved_calls', 0)
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
            parse_errors=parse_errors
        )
