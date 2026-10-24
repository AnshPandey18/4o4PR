"""Repository indexer for static code analysis.

Implements comprehensive fixes for:
1. Task 1: Record unresolved calls with details (expr, name, line, reason)
2. Task 3: Fix import consistency (style, level, names, resolved_file)
3. Task 4: Fix run_id vs generated_at timezone using UTC
4. Task 5: Index constants, classes, methods, and references
5. Task 6: Improvements (test_to_source generation, transitive mapping, metrics)

Parses Python files using AST to extract symbols, imports, and call graphs.
Never imports or executes project code.
"""

import ast
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from common.paths import to_posix_rel, is_python_file, is_test_file, should_exclude
from common.pyresolve import ImportResolver, get_module_name
from common.hashing import content_hash, sha1_file
from common.io import write_json, read_json
from .models import IndexData, FileInfo, SymbolInfo, ParseError

logger = logging.getLogger(__name__)

# Schema version - single source of truth
SCHEMA_VERSION = "1.2"

# TASK 4: Complete set of builtins from dir(builtins)
# Used to classify calls correctly - exceptions, types, functions
PYTHON_BUILTINS = {
    'ArithmeticError', 'AssertionError', 'AttributeError', 'BaseException',
    'BaseExceptionGroup', 'BlockingIOError', 'BrokenPipeError', 'BufferError',
    'BytesWarning', 'ChildProcessError', 'ConnectionAbortedError', 'ConnectionError',
    'ConnectionRefusedError', 'ConnectionResetError', 'DeprecationWarning', 'EOFError',
    'Ellipsis', 'EncodingWarning', 'EnvironmentError', 'Exception', 'ExceptionGroup',
    'False', 'FileExistsError', 'FileNotFoundError', 'FloatingPointError',
    'FutureWarning', 'GeneratorExit', 'IOError', 'ImportError', 'ImportWarning',
    'IndentationError', 'IndexError', 'InterruptedError', 'IsADirectoryError',
    'KeyError', 'KeyboardInterrupt', 'LookupError', 'MemoryError', 'ModuleNotFoundError',
    'NameError', 'None', 'NotADirectoryError', 'NotImplemented', 'NotImplementedError',
    'OSError', 'OverflowError', 'PendingDeprecationWarning', 'PermissionError',
    'ProcessLookupError', 'PythonFinalizationError', 'RecursionError', 'ReferenceError',
    'ResourceWarning', 'RuntimeError', 'RuntimeWarning', 'StopAsyncIteration',
    'StopIteration', 'SyntaxError', 'SyntaxWarning', 'SystemError', 'SystemExit',
    'TabError', 'TimeoutError', 'True', 'TypeError', 'UnboundLocalError',
    'UnicodeDecodeError', 'UnicodeEncodeError', 'UnicodeError', 'UnicodeTranslateError',
    'UnicodeWarning', 'UserWarning', 'ValueError', 'Warning', 'WindowsError',
    'ZeroDivisionError', 'abs', 'aiter', 'all', 'anext', 'any', 'ascii', 'bin',
    'bool', 'breakpoint', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod',
    'compile', 'complex', 'copyright', 'credits', 'delattr', 'dict', 'dir', 'divmod',
    'enumerate', 'eval', 'exec', 'exit', 'filter', 'float', 'format', 'frozenset',
    'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int',
    'isinstance', 'issubclass', 'iter', 'len', 'license', 'list', 'locals', 'map',
    'max', 'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow',
    'print', 'property', 'quit', 'range', 'repr', 'reversed', 'round', 'set',
    'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple',
    'type', 'vars', 'zip'
}

# Backward compatibility
BUILTIN_FUNCTIONS = PYTHON_BUILTINS

BUILTIN_METHODS = {
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'index', 'count',
    'sort', 'reverse', 'copy', 'join', 'split', 'strip', 'replace', 'find',
    'format', 'upper', 'lower', 'startswith', 'endswith', 'isdigit',
    'isalpha', 'isalnum', 'get', 'keys', 'values', 'items', 'update',
    'add', 'discard', 'union', 'intersection', 'difference',
}


def make_run_id(now_utc: datetime) -> str:
    """Create a run_id from UTC datetime.
    
    Format: r_YYYYMMDD_HHMMSS (e.g., r_20261020_124056)
    
    TASK 4: Helper that generates run_id from UTC time.
    
    Args:
        now_utc: datetime object (should be UTC-aware or naive UTC)
        
    Returns:
        run_id string
    """
    # Ensure we're working with UTC
    if now_utc.tzinfo is None:
        # Assume naive datetime is UTC
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if timezone-aware
        now_utc = now_utc.astimezone(timezone.utc)
    
    return now_utc.strftime("r_%Y%m%d_%H%M%S")


class StaleIndexError(Exception):
    """Raised when attempting to use an index that doesn't match current file state."""
    pass


class RepoIndexer:
    """Indexes a Python repository for static analysis."""
    
    def __init__(
        self,
        project_root: Path,
        import_roots: List[str],
        test_dirs: List[str],
        exclude_patterns: List[str],
        schema_version: str = SCHEMA_VERSION  # Use constant as default
    ):
        """Initialize the indexer.
        
        Args:
            project_root: Root directory of the project
            import_roots: List of directories where imports resolve from
            test_dirs: List of test directory names
            exclude_patterns: Patterns to exclude from indexing
            schema_version: Index schema version (default: SCHEMA_VERSION constant)
        """
        self.project_root = Path(project_root)
        self.import_roots = import_roots
        self.test_dirs = test_dirs
        self.exclude_patterns = exclude_patterns
        self.schema_version = schema_version
        
        self.resolver = ImportResolver(self.project_root, import_roots)
        self.import_root_paths = [self.project_root / root for root in import_roots]
        
        # Cache for parsed ASTs to avoid re-parsing
        self._ast_cache: Dict[str, Tuple[ast.Module, str]] = {}
    
    def index(
        self,
        run_id: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        now_utc: Optional[datetime] = None
    ) -> IndexData:
        """Index the repository.
        
        TASK 4: Fixed to accept optional run_id and now_utc, generates run_id if not provided.
        
        Args:
            run_id: Optional unique run identifier. If None, generated from now_utc.
            cache_dir: Optional cache directory for reusing cached indexes
            now_utc: Optional UTC datetime. If None, uses datetime.now(timezone.utc).
            
        Returns:
            IndexData containing complete repository index
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        else:
            # Ensure it's UTC
            if now_utc.tzinfo is None:
                now_utc = now_utc.replace(tzinfo=timezone.utc)
            else:
                now_utc = now_utc.astimezone(timezone.utc)
        
        if run_id is None:
            run_id = make_run_id(now_utc)
        
        logger.info(f"Starting repository indexing (run_id: {run_id})")
        
        # Compute content hash
        chash = content_hash(
            self.project_root,
            self.import_roots,
            self.exclude_patterns,
            self.schema_version
        )
        logger.info(f"Content hash: {chash[:16]}...")
        
        # Check cache if available
        if cache_dir:
            cached = self._check_cache(cache_dir, chash)
            if cached:
                logger.info("Reusing cached index")
                # Update run_id and timestamp (both derived from same now_utc)
                cached.run_id = run_id
                # FIX C5: Use Z suffix OR +00:00 offset, not both
                cached.generated_at = now_utc.isoformat().replace('+00:00', 'Z')
                return cached
        
        # Collect all Python files
        py_files = self._collect_python_files()
        logger.info(f"Found {len(py_files)} Python files")
        
        # Parse files and extract symbols
        files: Dict[str, FileInfo] = {}
        symbols: Dict[str, SymbolInfo] = {}
        parse_errors: List[ParseError] = []
        
        for file_path in py_files:
            rel_path, _ = to_posix_rel(file_path, self.project_root)
            
            try:
                file_info, file_symbols = self._parse_file(file_path, rel_path)
                files[rel_path] = file_info
                symbols.update(file_symbols)
            except SyntaxError as e:
                logger.warning(f"Syntax error in {rel_path}: {e}")
                parse_errors.append(ParseError(
                    file=rel_path,
                    line=e.lineno or 0,
                    message=str(e)
                ))
                # Still record the file as unparseable (TASK 6)
                files[rel_path] = FileInfo(
                    path=rel_path,
                    kind="test" if is_test_file(rel_path, self.test_dirs) else "source",
                    module=None,
                    lines=0,
                    sha1=sha1_file(file_path),
                    parse_ok=False
                )
            except Exception as e:
                logger.error(f"Error parsing {rel_path}: {e}")
                parse_errors.append(ParseError(
                    file=rel_path,
                    line=0,
                    message=f"Unexpected error: {str(e)}"
                ))
        
        logger.info(f"Parsed {len(files)} files, found {len(symbols)} symbols")
        
        # TASK 2: Second pass - populate children and resolve cross-file bases
        self._populate_children_and_bases(symbols)
        
        # TASK 5: Resolve decorator targets
        self._resolve_decorators(symbols, files)
        
        # TASK 5: Build references mapping (FIX BUG 1: Pass files for import resolution)
        self._extract_references(symbols, files)
        
        # Build call graph
        call_graph = self._build_call_graph(files, symbols)
        logger.info(f"Built call graph with {len(call_graph['callees'])} entries")
        
        # TASK 6: Generate test_to_source mapping
        test_to_source = self._generate_test_to_source(call_graph, symbols)
        test_to_source_transitive = self._generate_test_to_source_transitive(
            call_graph, symbols
        )
        logger.info(f"Mapped {len(test_to_source)} tests to source functions")
        
        # Create index data
        index_data = IndexData(
            schema_version=self.schema_version,
            run_id=run_id,
            content_hash=chash,
            # FIX C5: Use Z suffix OR +00:00 offset, not both
            generated_at=now_utc.isoformat().replace('+00:00', 'Z'),
            import_roots=self.import_roots,
            files=files,
            symbols=symbols,
            call_graph=call_graph,
            test_to_source=test_to_source,
            test_to_source_transitive=test_to_source_transitive,
            parse_errors=parse_errors
        )
        
        # Write to cache if available
        if cache_dir:
            self._write_cache(cache_dir, chash, index_data)
        
        logger.info("Repository indexing complete")
        return index_data
    
    def _collect_python_files(self) -> List[Path]:
        """Collect all Python files in the project.
        
        Returns:
            List of Path objects for Python files
        """
        py_files = []
        
        for py_file in self.project_root.rglob("*.py"):
            if should_exclude(py_file.relative_to(self.project_root), self.exclude_patterns):
                continue
            py_files.append(py_file)
        
        return sorted(py_files)
    
    def _parse_file(self, file_path: Path, rel_path: str) -> Tuple[FileInfo, Dict[str, SymbolInfo]]:
        """Parse a single Python file.
        
        Args:
            file_path: Absolute path to file
            rel_path: POSIX relative path
            
        Returns:
            Tuple of (FileInfo, dict of SymbolInfo keyed by symbol_id)
        """
        # Read source
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Parse AST
        tree = ast.parse(source, filename=str(file_path))
        
        # Cache for later use
        self._ast_cache[rel_path] = (tree, source)
        
        # Determine file kind
        kind = "test" if is_test_file(rel_path, self.test_dirs) else "source"
        
        # Get module name
        module_name = get_module_name(file_path, self.import_root_paths, self.project_root)
        
        # Extract module docstring
        docstring = ast.get_docstring(tree)
        if docstring:
            # Keep only first line
            docstring = docstring.split('\n')[0].strip()
        
        # TASK 3: Extract imports with improved consistency
        imports = self._extract_imports_from_file(file_path, rel_path)
        
        # Extract symbols
        symbols = self._extract_symbols(tree, source, rel_path, kind)
        
        # Count lines
        line_count = len(source.splitlines())
        
        # Compute file hash
        file_hash = sha1_file(file_path)
        
        file_info = FileInfo(
            path=rel_path,
            kind=kind,
            module=module_name,
            lines=line_count,
            sha1=file_hash,
            parse_ok=True,
            docstring=docstring,
            imports=imports
        )
        
        return file_info, symbols
    
    def _extract_imports_from_file(self, file_path: Path, rel_path: str) -> List[Dict[str, Any]]:
        """Extract imports from file with all required fields.
        
        TASK 3: Every import has style, level, line, module, names, resolved_file.
        Handles: import x, from x import y, from . import z (relative).
        
        Args:
            file_path: Absolute file path
            rel_path: POSIX relative path
            
        Returns:
            List of import dicts
        """
        if rel_path not in self._ast_cache:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
            self._ast_cache[rel_path] = (tree, source)
        else:
            tree, _ = self._ast_cache[rel_path]
        
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # import x, import x as y, import x.y.z
                for alias in node.names:
                    resolved_file = self.resolver.resolve_import(
                        alias.name, file_path, is_relative=False, level=0
                    )
                    # Convert Path to string
                    resolved_file_str = None
                    if resolved_file:
                        try:
                            resolved_file_str = resolved_file.relative_to(self.project_root).as_posix()
                        except (ValueError, AttributeError):
                            resolved_file_str = str(resolved_file)
                    
                    imports.append({
                        'style': 'import',
                        'level': 0,
                        'line': node.lineno,
                        'module': alias.name,
                        'names': [{'name': alias.name, 'asname': alias.asname}],
                        'resolved_file': resolved_file_str
                    })
            
            elif isinstance(node, ast.ImportFrom):
                # from x import y, from .x import y, from ..x import y
                level = node.level or 0
                module_name = node.module or ''
                
                resolved_file = None
                if level > 0 or module_name:
                    resolved_file = self.resolver.resolve_import(
                        module_name, file_path, is_relative=(level > 0), level=level
                    )
                
                # Convert Path to string
                resolved_file_str = None
                if resolved_file:
                    try:
                        resolved_file_str = resolved_file.relative_to(self.project_root).as_posix()
                    except (ValueError, AttributeError):
                        resolved_file_str = str(resolved_file)
                
                names = [
                    {'name': alias.name, 'asname': alias.asname}
                    for alias in node.names
                ]
                
                imports.append({
                    'style': 'from',
                    'level': level,
                    'line': node.lineno,
                    'module': module_name,
                    'names': names,
                    'resolved_file': resolved_file_str
                })
        
        return imports
    
    def _extract_symbols(
        self,
        tree: ast.AST,
        source: str,
        file_path: str,
        kind: str
    ) -> Dict[str, SymbolInfo]:
        """Extract all symbols (functions, classes, constants, methods) from AST.
        
        TASK 5: Adds constants, classes, and methods with proper metadata.
        
        Args:
            tree: AST tree
            source: Source code
            file_path: POSIX relative file path
            kind: "source" or "test"
            
        Returns:
            Dict of SymbolInfo keyed by symbol_id
        """
        symbols = {}
        source_lines = source.splitlines()
        
        # TASK 5: Extract module-level constants
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                # Module-level constant assignment
                const_info = self._extract_constant_info(
                    node, source_lines, file_path, kind, source
                )
                if const_info:
                    symbols[const_info.symbol_id] = const_info
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract class
                class_info = self._extract_class_info(node, source_lines, file_path, kind, source)
                symbols[class_info.symbol_id] = class_info
                
                # Extract methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # FIX C1: Pass class symbol_id instead of name
                        method_info = self._extract_function_info(
                            item, source_lines, file_path, kind, 
                            parent_class=class_info.symbol_id, source=source
                        )
                        symbols[method_info.symbol_id] = method_info
            
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only extract top-level functions (not nested or methods)
                if self._is_top_level(node, tree):
                    func_info = self._extract_function_info(
                        node, source_lines, file_path, kind, source=source
                    )
                    symbols[func_info.symbol_id] = func_info
        
        return symbols
    
    def _extract_constant_info(
        self,
        node: ast.Assign | ast.AnnAssign,
        source_lines: List[str],
        file_path: str,
        kind: str,
        source: str
    ) -> Optional[SymbolInfo]:
        """Extract information about a module-level constant.
        
        TASK 5: Extracts constants with value_preview.
        
        Args:
            node: AST Assign or AnnAssign node
            source_lines: Source code lines
            file_path: POSIX relative file path
            kind: "source" or "test"
            source: Full source code
            
        Returns:
            SymbolInfo for the constant or None
        """
        try:
            # Get constant name
            if isinstance(node, ast.Assign):
                # Could be multiple targets, take first one
                if not node.targets:
                    return None
                target = node.targets[0]
            else:
                target = node.target
            
            # Only handle simple names
            if not isinstance(target, ast.Name):
                return None
            
            name = target.id
            line_num = node.lineno
            
            # Get source segment for value_preview (max 80 chars)
            try:
                line_start = line_num - 1
                line_end = node.end_lineno or line_num
                if 0 <= line_start < len(source_lines):
                    preview_lines = source_lines[line_start:line_end]
                    value_preview = ' '.join(preview_lines).strip()
                    if len(value_preview) > 80:
                        value_preview = value_preview[:77] + '...'
                else:
                    value_preview = None
            except:
                value_preview = None
            
            symbol_id = f"{file_path}::{name}"
            
            # TASK 6: Calculate metrics (FIX C4 & C5)
            line_count = (node.end_lineno or node.lineno) - node.lineno + 1
            const_source = '\n'.join(source_lines[node.lineno - 1:(node.end_lineno or node.lineno)])
            char_count = len(const_source)  # FIX C4: actual character count
            approx_tokens = max(1, char_count // 4)  # FIX C5: divide by 4 for token estimate
            
            return SymbolInfo(
                symbol_id=symbol_id,
                kind="constant",
                name=name,
                file=file_path,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                signature=None,
                docstring=None,
                parent_class=None,
                is_test=kind == "test",
                value_preview=value_preview,
                line_count=line_count,
                char_count=char_count,
                approx_tokens=approx_tokens
            )
        except Exception as e:
            logger.debug(f"Failed to extract constant: {e}")
            return None
    
    def _is_top_level(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if a node is at module level (not nested in a class or function).
        
        Args:
            node: AST node to check
            tree: Module AST tree
            
        Returns:
            True if node is at module level
        """
        # Check if node is directly in module body
        if isinstance(tree, ast.Module):
            return node in tree.body
        return False
    
    def _extract_class_info(
        self,
        node: ast.ClassDef,
        source_lines: List[str],
        file_path: str,
        kind: str,
        source: str
    ) -> SymbolInfo:
        """Extract information about a class definition.
        
        TASK 2: Extract base classes for schema 1.2.
        TASK 6: Added metrics (line_count, char_count, approx_tokens).
        
        Args:
            node: AST ClassDef node
            source_lines: Source code lines
            file_path: POSIX relative file path
            kind: "source" or "test"
            source: Full source code
            
        Returns:
            SymbolInfo for the class
        """
        # TASK 6: line_start must be first decorator's line if decorated
        line_start = node.lineno
        if node.decorator_list:
            line_start = min(dec.lineno for dec in node.decorator_list)
        
        line_end = node.end_lineno or node.lineno
        
        # Get decorators
        decorators = [ast.unparse(dec) for dec in node.decorator_list]
        
        # Get docstring
        docstring = ast.get_docstring(node)
        if docstring:
            docstring = docstring.split('\n')[0].strip()
        
        symbol_id = f"{file_path}::{node.name}"
        
        # TASK 6: Calculate metrics (FIX C4 & C5)
        line_count = line_end - line_start + 1
        class_source = '\n'.join(source_lines[line_start - 1:line_end])
        char_count = len(class_source)  # FIX C4: actual character count
        approx_tokens = max(1, char_count // 4)  # FIX C5: divide by 4 for token estimate
        
        # TASK 2: Extract base classes (first pass - only same-file resolution)
        bases = []
        bases_unresolved = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
                # Check if base is in same file (cross-file resolved in second pass)
                base_symbol_id = f"{file_path}::{base_name}"
                # We'll check if it exists in the second pass
                bases_unresolved.append(base_name)
            elif isinstance(base, ast.Attribute):
                # e.g., module.BaseClass
                base_name = ast.unparse(base)
                bases_unresolved.append(base_name)
            else:
                # Complex expression
                bases_unresolved.append(ast.unparse(base))
        
        return SymbolInfo(
            symbol_id=symbol_id,
            kind="class",
            name=node.name,
            file=file_path,
            line_start=line_start,
            line_end=line_end,
            signature=None,  # FIX C6: Classes have null signature, not empty string
            decorators=decorators,
            docstring=docstring,
            parent_class=None,
            is_test=kind == "test",
            line_count=line_count,
            char_count=char_count,
            approx_tokens=approx_tokens,
            bases=bases,
            bases_unresolved=bases_unresolved,
            children=[]  # Will be populated in second pass
        )
    
    def _extract_function_info(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: List[str],
        file_path: str,
        kind: str,
        source: str,
        parent_class: Optional[str] = None
    ) -> SymbolInfo:
        """Extract information about a function or method definition.
        
        TASK 6: Added metrics and proper decorator handling.
        
        Args:
            node: AST FunctionDef or AsyncFunctionDef node
            source_lines: Source code lines
            file_path: POSIX relative file path
            kind: "source" or "test"
            source: Full source code
            parent_class: Parent class name if this is a method
            
        Returns:
            SymbolInfo for the function/method
        """
        # TASK 6: line_start must be first decorator's line if decorated, not def line
        line_start = node.lineno
        if node.decorator_list:
            line_start = min(dec.lineno for dec in node.decorator_list)
        
        line_end = node.end_lineno or node.lineno
        
        # Get decorators
        decorators = [ast.unparse(dec) for dec in node.decorator_list]
        
        # Get signature
        signature = self._format_signature(node)
        
        # Get docstring
        docstring = ast.get_docstring(node)
        if docstring:
            docstring = docstring.split('\n')[0].strip()
        
        # Determine qualified name
        # FIX C1: parent_class is now a symbol_id, extract just the class name
        if parent_class:
            # parent_class is now "file.py::ClassName", extract just ClassName
            class_name = parent_class.split('::')[-1]
            qualified_name = f"{class_name}.{node.name}"
        else:
            qualified_name = node.name
        
        symbol_id = f"{file_path}::{qualified_name}"
        
        # Check if it's a test function
        is_test = kind == "test" and node.name.startswith("test_")
        
        # TASK 6: Calculate metrics (FIX C4 & C5)
        line_count = line_end - line_start + 1
        func_source = '\n'.join(source_lines[line_start - 1:line_end])
        char_count = len(func_source)  # FIX C4: actual character count
        approx_tokens = max(1, char_count // 4)  # FIX C5: divide by 4 for token estimate
        
        return SymbolInfo(
            symbol_id=symbol_id,
            kind="method" if parent_class else "function",
            name=node.name,
            file=file_path,
            line_start=line_start,
            line_end=line_end,
            signature=signature,
            decorators=decorators,
            docstring=docstring,
            parent_class=parent_class,
            is_test=is_test,
            line_count=line_count,
            char_count=char_count,
            approx_tokens=approx_tokens
        )
    
    def _format_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Format function signature as a string.
        
        TASK 6 (I7): Includes default values, *args, **kwargs, and return annotation.
        
        Args:
            node: Function AST node
            
        Returns:
            Signature string (e.g., "(a, b: int = 5) -> str")
        """
        args_parts = []
        
        # Regular arguments and keyword-only arguments
        # Get defaults (aligned from the right)
        regular_args = node.args.args
        defaults = node.args.defaults
        kw_defaults = node.args.kw_defaults
        
        # Calculate where defaults start for regular args
        num_args = len(regular_args)
        num_defaults = len(defaults)
        first_default_idx = num_args - num_defaults
        
        # Regular arguments
        for i, arg in enumerate(regular_args):
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except:
                    pass
            
            # Add default if present
            if i >= first_default_idx:
                default_idx = i - first_default_idx
                if default_idx < len(defaults):
                    try:
                        arg_str += f" = {ast.unparse(defaults[default_idx])}"
                    except:
                        pass
            
            args_parts.append(arg_str)
        
        # *args
        if node.args.vararg:
            vararg_str = f"*{node.args.vararg.arg}"
            if node.args.vararg.annotation:
                try:
                    vararg_str += f": {ast.unparse(node.args.vararg.annotation)}"
                except:
                    pass
            args_parts.append(vararg_str)
        elif node.args.kwonlyargs:
            # Bare * if there are keyword-only args but no *args
            args_parts.append("*")
        
        # Keyword-only arguments
        for i, arg in enumerate(node.args.kwonlyargs):
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except:
                    pass
            
            # Add default if present
            if i < len(kw_defaults) and kw_defaults[i] is not None:
                try:
                    arg_str += f" = {ast.unparse(kw_defaults[i])}"
                except:
                    pass
            
            args_parts.append(arg_str)
        
        # **kwargs
        if node.args.kwarg:
            kwarg_str = f"**{node.args.kwarg.arg}"
            if node.args.kwarg.annotation:
                try:
                    kwarg_str += f": {ast.unparse(node.args.kwarg.annotation)}"
                except:
                    pass
            args_parts.append(kwarg_str)
        
        signature = f"({', '.join(args_parts)})"
        
        # Return annotation
        if node.returns:
            try:
                signature += f" -> {ast.unparse(node.returns)}"
            except:
                pass
        
        return signature
    
    def _populate_children_and_bases(self, symbols: Dict[str, SymbolInfo]) -> None:
        """Populate children list for classes and resolve cross-file bases.
        
        TASK 2: Second pass after all symbols extracted.
        TASK 3: Extract attr_types from class methods.
        
        Args:
            symbols: Dict of all symbols
        """
        # Build map of class names to symbol IDs for base resolution
        class_name_to_ids: Dict[str, List[str]] = {}
        for sym_id, sym in symbols.items():
            if sym.kind == "class":
                class_name_to_ids.setdefault(sym.name, []).append(sym_id)
        
        # Populate children, resolve bases, and extract attr_types
        for sym_id, sym in symbols.items():
            if sym.kind == "class":
                # Find all methods with this class as parent
                children = []
                for method_id, method_sym in symbols.items():
                    if method_sym.kind == "method" and method_sym.parent_class == sym_id:
                        children.append(method_id)
                sym.children = sorted(children)  # Deterministic order
                
                # Resolve unresolved bases to repo classes if possible
                if sym.bases_unresolved:
                    for base_name in sym.bases_unresolved[:]:  # Copy to modify during iteration
                        # Simple name lookup
                        if base_name in class_name_to_ids:
                            candidates = class_name_to_ids[base_name]
                            if len(candidates) == 1:
                                # Unique match - resolve it
                                sym.bases.append(candidates[0])
                                sym.bases_unresolved.remove(base_name)
                            # Multiple matches or no match - leave unresolved
                
                # TASK 3: Extract attr_types from all methods of this class
                sym.attr_types = self._extract_attr_types(sym, symbols)
    
    def _resolve_decorators(self, symbols: Dict[str, SymbolInfo], files: Dict[str, FileInfo]) -> None:
        """Resolve decorator names to symbol IDs.
        
        TASK 5: For each symbol with decorators, resolve decorator names to symbol IDs.
        Uses the same resolution logic as function calls: check same file, then imports.
        
        Args:
            symbols: Dict of all symbols
            files: Dict of all files (for import resolution)
        """
        for sym_id, sym in symbols.items():
            if not sym.decorators:
                continue
            
            # Get file info for import resolution
            if sym.file not in files:
                continue
            
            file_info = files[sym.file]
            import_map = self._build_import_map(file_info.imports)
            
            decorator_targets = []
            for decorator_name in sym.decorators:
                # Try to resolve decorator (could be @decorator or @module.decorator)
                # For now, handle simple names and ignore complex decorators like @decorator(args)
                
                # Simple decorator: @authenticate
                if '(' not in decorator_name and '.' not in decorator_name:
                    # Check same file first
                    candidate_id = f"{sym.file}::{decorator_name}"
                    if candidate_id in symbols:
                        decorator_targets.append(candidate_id)
                        continue
                    
                    # Check imports
                    if decorator_name in import_map:
                        target_file_rel = import_map[decorator_name]
                        if target_file_rel:
                            # target_file_rel is like 'src/auth.py', need to find full path
                            # Search for a file that ends with this path
                            full_target_file = None
                            for file_path in files.keys():
                                if file_path.endswith(target_file_rel):
                                    full_target_file = file_path
                                    break
                            
                            if full_target_file:
                                candidate_id = f"{full_target_file}::{decorator_name}"
                                if candidate_id in symbols:
                                    decorator_targets.append(candidate_id)
                                    continue
                
                # Could not resolve - skip
                # Don't add to decorator_targets
            
            sym.decorator_targets = decorator_targets
    
    def _extract_attr_types(self, class_sym: SymbolInfo, symbols: Dict[str, SymbolInfo]) -> Dict[str, str]:
        """Extract attribute type assignments for a class.
        
        TASK 3: Analyze all methods to find:
        - self.x = ClassName(...) 
        - self.x = param where param: ClassName
        - self.x: ClassName = ...
        
        Args:
            class_sym: The class symbol
            symbols: All symbols
            
        Returns:
            Dict mapping attribute name to class symbol ID
        """
        attr_types: Dict[str, str] = {}
        
        # Get file and parse if not cached
        file_path = self.project_root / class_sym.file
        if class_sym.file not in self._ast_cache:
            return attr_types
        
        tree, source = self._ast_cache[class_sym.file]
        
        # Find the class node
        class_name = class_sym.name
        class_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                class_node = node
                break
        
        if not class_node:
            return attr_types
        
        # Analyze all methods in the class
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Scan method body for assignments
                for stmt in ast.walk(item):
                    # Pattern 1: self.x = ClassName(...)
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                if target.value.id == 'self':
                                    attr_name = target.attr
                                    # Check if RHS is a call to a class
                                    if isinstance(stmt.value, ast.Call):
                                        if isinstance(stmt.value.func, ast.Name):
                                            class_name_rhs = stmt.value.func.id
                                            # Try to resolve to repo class
                                            resolved = self._resolve_class_name(class_name_rhs, class_sym.file, symbols)
                                            if resolved:
                                                attr_types[attr_name] = resolved
                    
                    # Pattern 2: self.x: ClassName = ...
                    elif isinstance(stmt, ast.AnnAssign):
                        if isinstance(stmt.target, ast.Attribute) and isinstance(stmt.target.value, ast.Name):
                            if stmt.target.value.id == 'self':
                                attr_name = stmt.target.attr
                                # Extract type from annotation
                                if isinstance(stmt.annotation, ast.Name):
                                    class_name_ann = stmt.annotation.id
                                    resolved = self._resolve_class_name(class_name_ann, class_sym.file, symbols)
                                    if resolved:
                                        attr_types[attr_name] = resolved
                
                # Pattern 3: self.x = param where param has annotation
                # Scan function parameters
                for arg in item.args.args:
                    if arg.annotation and isinstance(arg.annotation, ast.Name):
                        param_type = arg.annotation.id
                        resolved = self._resolve_class_name(param_type, class_sym.file, symbols)
                        if resolved:
                            # Now look for self.x = param in body
                            for stmt in ast.walk(item):
                                if isinstance(stmt, ast.Assign):
                                    if isinstance(stmt.value, ast.Name) and stmt.value.id == arg.arg:
                                        for target in stmt.targets:
                                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                                                if target.value.id == 'self':
                                                    attr_types[target.attr] = resolved
        
        return attr_types
    
    def _find_inherited_method(self, class_sym: SymbolInfo, method_name: str, symbols: Dict[str, SymbolInfo]) -> Optional[str]:
        """Find a method in the class's inheritance chain.
        
        TASK 3: Search base classes for inherited method.
        
        Args:
            class_sym: The class to search
            method_name: Method name to find
            symbols: All symbols
            
        Returns:
            Method symbol ID or None
        """
        # Depth-first search through bases
        for base_id in class_sym.bases:
            if base_id not in symbols:
                continue
            base_sym = symbols[base_id]
            # Check if this base has the method
            method_id = f"{base_sym.file}::{base_sym.name}.{method_name}"
            if method_id in symbols:
                return method_id
            # Recursively check base's bases
            inherited = self._find_inherited_method(base_sym, method_name, symbols)
            if inherited:
                return inherited
        return None
    
    def _resolve_class_name(self, class_name: str, file_path: str, symbols: Dict[str, SymbolInfo]) -> Optional[str]:
        """Resolve a class name to a symbol ID.
        
        Args:
            class_name: Simple class name
            file_path: Current file path
            symbols: All symbols
            
        Returns:
            Symbol ID or None
        """
        # Try same file first
        same_file_id = f"{file_path}::{class_name}"
        if same_file_id in symbols and symbols[same_file_id].kind == "class":
            return same_file_id
        
        # Try imports (would need import map, skip for now - cross-file resolution done in populate_children_and_bases)
        # Look for any class with this name
        for sym_id, sym in symbols.items():
            if sym.kind == "class" and sym.name == class_name:
                return sym_id
        
        return None
    
    def _extract_references(self, symbols: Dict[str, SymbolInfo], files: Dict[str, FileInfo]) -> None:
        """TASK 5: Extract references between symbols (constants used in functions).
        
        Updates call_graph with:
        - references: symbol -> list of constant IDs it reads
        - referenced_by: mirror of references
        
        Detects references via ast.Name in Load context in function bodies.
        Skips names that are parameters or assigned locally (shadowing).
        
        FIX BUG 1: Now resolves cross-file imported constants via files dict.
        
        Args:
            symbols: Dict of all symbols
            files: Dict of FileInfo for import resolution
        """
        # Build a mapping of constant symbol IDs for quick lookup
        constants_by_name: Dict[str, str] = {}  # name -> symbol_id
        for sym_id, sym in symbols.items():
            if sym.kind == "constant":
                constants_by_name[sym.name] = sym_id
        
        # For each function, find constants it references
        for symbol_id, symbol in symbols.items():
            if symbol.kind in ("function", "method"):
                file_key = symbol.file
                if file_key not in self._ast_cache:
                    continue
                
                tree, _ = self._ast_cache[file_key]
                file_info = files.get(file_key)  # Get file info for imports
                func_node = self._find_function_node(tree, symbol)
                
                if func_node:
                    # Extract referenced constants
                    refs = self._find_constant_references(
                        func_node, constants_by_name, symbol.file, file_info
                    )
                    if refs:
                        symbol.references = sorted(set(refs))
    
    def _find_constant_references(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        constants_by_name: Dict[str, str],
        file_path: str,
        file_info: Optional[FileInfo] = None
    ) -> List[str]:
        """Find constants referenced in a function body.
        
        Detects ast.Name in Load context, skipping local assignments.
        Resolves imported constants via file_info.imports.
        
        FIX BUG 1: Now detects cross-file constant references via imports.
        
        Args:
            func_node: Function AST node
            constants_by_name: Mapping of constant names to symbol IDs
            file_path: File path for constant resolution
            file_info: FileInfo with imports (used to resolve imported constants)
            
        Returns:
            List of constant symbol IDs referenced
        """
        refs = []
        local_names: Set[str] = set()
        
        # Build import map for cross-file resolution
        imported_constants: Dict[str, str] = {}  # name -> file path
        if file_info and file_info.imports:
            for import_dict in file_info.imports:
                if import_dict.get('style') == 'from':
                    resolved_file = import_dict.get('resolved_file')
                    if resolved_file:
                        for name_dict in import_dict.get('names', []):
                            name = name_dict.get('name')
                            if name:
                                imported_constants[name] = resolved_file
        
        # Collect locally assigned names
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                local_names.add(node.id)
            elif isinstance(node, ast.arg):
                local_names.add(node.arg)
        
        # Find Name nodes in Load context
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                name = node.id
                if name not in local_names and name in constants_by_name:
                    const_id = constants_by_name[name]
                    # Check if it's from the same file or from an import
                    same_file = const_id.startswith(file_path)
                    imported = name in imported_constants
                    
                    if same_file or imported:
                        refs.append(const_id)
        
        return refs
    
    def _build_call_graph(
        self,
        files: Dict[str, FileInfo],
        symbols: Dict[str, SymbolInfo]
    ) -> Dict[str, Any]:
        """Build call graph for all functions.
        
        TASK 1: Records unresolved calls with details.
        
        Only includes resolved calls with high certainty.
        
        Args:
            files: Dict of FileInfo
            symbols: Dict of SymbolInfo
            
        Returns:
            Dict with callees, callers, references, referenced_by
        """
        callees: Dict[str, List[str]] = {}
        callers: Dict[str, List[str]] = {}
        references: Dict[str, List[str]] = {}  # TASK 5
        referenced_by: Dict[str, List[str]] = {}  # TASK 5
        
        # For each function, find its calls
        for symbol_id, symbol in symbols.items():
            if symbol.kind in ("function", "method"):
                file_path = self.project_root / symbol.file
                if symbol.file not in self._ast_cache:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            source = f.read()
                        tree = ast.parse(source)
                        self._ast_cache[symbol.file] = (tree, source)
                    except:
                        callees[symbol_id] = []
                        continue
                else:
                    tree, _ = self._ast_cache[symbol.file]
                
                try:
                    # Find the function node
                    func_node = self._find_function_node(tree, symbol)
                    if func_node:
                        # FIX BUG 2: Pass symbol.parent_class for method resolution
                        resolved, unresolved_list, builtin_list = self._extract_calls(
                            func_node, symbol.file, files[symbol.file], symbols, symbol.parent_class
                        )
                        callees[symbol_id] = resolved
                        symbol.unresolved_calls = len(unresolved_list)
                        symbol.unresolved = unresolved_list
                        symbol.builtin_calls = builtin_list
                        
                        # Update callers mapping
                        for callee_id in resolved:
                            if callee_id not in callers:
                                callers[callee_id] = []
                            if symbol_id not in callers[callee_id]:
                                callers[callee_id].append(symbol_id)
                    else:
                        callees[symbol_id] = []
                except Exception as e:
                    logger.debug(f"Error extracting calls from {symbol_id}: {e}")
                    callees[symbol_id] = []
        
        # TASK 5: Build references and referenced_by
        for symbol_id, symbol in symbols.items():
            if hasattr(symbol, 'references') and symbol.references:
                references[symbol_id] = symbol.references
                for ref_id in symbol.references:
                    if ref_id not in referenced_by:
                        referenced_by[ref_id] = []
                    if symbol_id not in referenced_by[ref_id]:
                        referenced_by[ref_id].append(symbol_id)
        
        # TASK 5: Build decorated_by and decorates
        decorated_by: Dict[str, List[str]] = {}  # symbol_id -> [decorator_ids]
        decorates: Dict[str, List[str]] = {}  # decorator_id -> [symbol_ids]
        
        for symbol_id, symbol in symbols.items():
            if symbol.decorator_targets:
                decorated_by[symbol_id] = symbol.decorator_targets
                for decorator_id in symbol.decorator_targets:
                    if decorator_id not in decorates:
                        decorates[decorator_id] = []
                    if symbol_id not in decorates[decorator_id]:
                        decorates[decorator_id].append(symbol_id)
        
        return {
            'callees': callees,
            'callers': callers,
            'references': references,
            'referenced_by': referenced_by,
            'decorated_by': decorated_by,
            'decorates': decorates
        }
    
    def _find_function_node(
        self,
        tree: ast.AST,
        symbol: SymbolInfo
    ) -> Optional[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Find the AST node for a function symbol.
        
        FIX C1: parent_class is now a symbol_id, extract class name from it.
        
        Args:
            tree: Module AST tree
            symbol: SymbolInfo to find
            
        Returns:
            Function node or None
        """
        if symbol.parent_class:
            # It's a method - find the class first
            # FIX C1: parent_class is now "file.py::ClassName", extract just ClassName
            class_name = symbol.parent_class.split('::')[-1]
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if item.name == symbol.name:
                                return item
        else:
            # It's a function - find top-level
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == symbol.name:
                        return node
        
        return None
    
    def _extract_calls(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        file_info: FileInfo,
        symbols: Dict[str, SymbolInfo],
        current_class: Optional[str] = None
    ) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
        """Extract function calls from a function body.
        
        TASK 1: Returns (resolved_call_ids, unresolved_list, builtin_calls).
        
        Only resolves calls with high certainty:
        - Same-file function calls
        - Imported function calls
        - Method calls on self (within same class)
        
        Classifies unresolved calls with reason codes:
        - "method_on_unknown_receiver": method call on object other than self/known type
        - "dynamic_call": call on variable or expression result
        - "external_module": call on external module attribute
        - "not_found": name not found in scope
        
        FIX BUG 2: Pass current_class to _resolve_call for self.method() resolution.
        FIX BUG 3: Build type inference map for instance variables.
        
        Args:
            func_node: Function AST node
            file_path: POSIX relative file path
            file_info: FileInfo for the containing file
            symbols: Dict of all symbols
            current_class: Current class name if this is a method
            
        Returns:
            Tuple of (resolved_call_ids, unresolved_details_list, builtin_names_list)
        """
        resolved_calls: Set[str] = set()
        unresolved_list: List[Dict[str, Any]] = []
        builtin_calls: Set[str] = set()
        
        # TASK 4: Build parameter set for parameter_call classification
        param_names: Set[str] = set()
        for arg in func_node.args.args:
            param_names.add(arg.arg)
        if func_node.args.vararg:
            param_names.add(func_node.args.vararg.arg)
        if func_node.args.kwarg:
            param_names.add(func_node.args.kwarg.arg)
        for arg in func_node.args.kwonlyargs:
            param_names.add(arg.arg)
        
        # FIX BUG 3: Build type inference map for instance assignments
        # Track patterns like: x = ClassName(...) -> x is of type ClassName
        type_map: Dict[str, str] = {}  # variable_name -> ClassName
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assign):
                # Pattern: x = ClassName(...)
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                    class_name = node.value.func.id
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            type_map[target.id] = class_name
        
        # Build import mapping for this file
        import_map = self._build_import_map(file_info.imports)
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                # Try to resolve the call (FIX BUG 2: Pass current_class)
                call_id, unresolved_dict, is_builtin = self._resolve_call(
                    node, file_path, import_map, symbols, current_class, type_map, param_names
                )
                if call_id:
                    resolved_calls.add(call_id)
                elif is_builtin:
                    # Extract builtin name
                    if isinstance(node.func, ast.Name):
                        builtin_calls.add(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        builtin_calls.add(node.func.attr)
                else:
                    if unresolved_dict:
                        unresolved_list.append(unresolved_dict)
        
        return list(sorted(resolved_calls)), unresolved_list, list(sorted(builtin_calls))
    
    def _build_import_map(self, imports: List[Dict]) -> Dict[str, str]:
        """Build a mapping from imported names to their resolved file paths.
        
        TASK 4: Also tracks external module imports (stdlib, third-party) with None as value.
        
        Args:
            imports: List of import dicts
            
        Returns:
            Dict mapping name to resolved file path (or None for external modules)
        """
        import_map = {}
        
        for imp in imports:
            resolved_file = imp.get('resolved_file')
            for name_info in imp.get('names', []):
                name = name_info.get('name', '')
                asname = name_info.get('asname')
                key = asname if asname else name
                if key:
                    # Use resolved_file if available, None for external modules
                    import_map[key] = resolved_file
        
        return import_map
    
    def _resolve_call(
        self,
        call_node: ast.Call,
        file_path: str,
        import_map: Dict[str, str],
        symbols: Dict[str, SymbolInfo],
        current_class: Optional[str] = None,
        type_map: Optional[Dict[str, str]] = None,
        param_names: Optional[Set[str]] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
        """Try to resolve a call to a symbol ID.
        
        TASK 1: Records unresolved calls with expr, name, line, reason.
        TASK 4: Improved classification - parameter_call, builtins from dir(builtins),
               external_module only for imported modules, method_on_unknown_receiver for locals.
        
        FIX BUG 2: Resolves self.method() calls to ClassName.method.
        FIX BUG 3: Uses type inference for instance.method() patterns.
        FIX BUG 4: Checks repo symbols before builtin methods.
        
        Args:
            call_node: AST Call node
            file_path: POSIX relative file path
            import_map: Import name to file mapping
            symbols: Dict of all symbols
            current_class: Current class context for self.method() resolution
            type_map: Type inference map (variable_name -> ClassName)
            param_names: Set of parameter names in current function
            
        Returns:
            Tuple of (symbol_id, unresolved_dict, is_builtin)
            - symbol_id: if resolved
            - unresolved_dict: if unresolved (with expr, name, line, reason)
            - is_builtin: True if it's a builtin call
        """
        if type_map is None:
            type_map = {}
        if param_names is None:
            param_names = set()
            
        func = call_node.func
        line_num = call_node.lineno
        
        # Simple name call: func()
        if isinstance(func, ast.Name):
            name = func.id
            expr = ast.unparse(func)
            
            # TASK 4: Check if it's a builtin (including exceptions from dir(builtins))
            if name in PYTHON_BUILTINS:
                return None, None, True
            
            # TASK 4: Check if calling a parameter
            if name in param_names:
                return None, {
                    'expr': expr,
                    'name': name,
                    'line': line_num,
                    'reason': 'parameter_call'
                }, False
            
            # Check if it's imported
            if name in import_map:
                target_file = import_map[name]
                if target_file:
                    symbol_id = f"{target_file}::{name}"
                    if symbol_id in symbols:
                        return symbol_id, None, False
                # Import found but not resolvable (external or not found in repo file)
                return None, {
                    'expr': expr,
                    'name': name,
                    'line': line_num,
                    'reason': 'external_module' if not target_file else 'not_found'
                }, False
            
            # Check if it's in the same file
            symbol_id = f"{file_path}::{name}"
            if symbol_id in symbols:
                return symbol_id, None, False
            
            # Unresolved: not in imports, not in current file
            return None, {
                'expr': expr,
                'name': name,
                'line': line_num,
                'reason': 'not_found'
            }, False
        
        # Attribute call: module.func(), obj.method(), self.method()
        elif isinstance(func, ast.Attribute):
            attr_name = func.attr
            expr = ast.unparse(func)
            
            # FIX BUG 4: Check repo symbols BEFORE checking builtins
            # This allows DataProcessor.sort to be resolved before checking builtin sort
            repo_symbol_id = None
            
            # TASK 3: Check for super().method() calls
            if isinstance(func.value, ast.Call):
                if isinstance(func.value.func, ast.Name) and func.value.func.id == 'super':
                    # This is super().method()
                    if current_class and current_class in symbols:
                        current_sym = symbols[current_class]
                        # Find method in first base class
                        inherited_method = self._find_inherited_method(current_sym, attr_name, symbols)
                        if inherited_method:
                            return inherited_method, None, False
                    # Could not resolve super() call
                    return None, {
                        'expr': expr,
                        'name': attr_name,
                        'line': line_num,
                        'reason': 'super_unresolved'
                    }, False
            
            # Check for self.method() calls - FIX BUG 2 + TASK 3 inheritance
            if isinstance(func.value, ast.Name) and func.value.id == 'self':
                if current_class:
                    # FIX C1: current_class is now a symbol_id, extract class name
                    class_name = current_class.split('::')[-1] if '::' in current_class else current_class
                    # Try to resolve as a method of the current class
                    repo_symbol_id = f"{file_path}::{class_name}.{attr_name}"
                    if repo_symbol_id in symbols:
                        return repo_symbol_id, None, False
                    
                    # TASK 3: Check inherited methods from base classes
                    if current_class in symbols:
                        current_sym = symbols[current_class]
                        inherited_method = self._find_inherited_method(current_sym, attr_name, symbols)
                        if inherited_method:
                            return inherited_method, None, False
                
                # Unresolved self.method (no class context or method not found)
                return None, {
                    'expr': expr,
                    'name': attr_name,
                    'line': line_num,
                    'reason': 'method_on_unknown_receiver'
                }, False
            
            # TASK 3: Check for self.attr.method() - attribute chain resolution
            elif isinstance(func.value, ast.Attribute):
                # e.g., self.session_manager.start_session() OR server.user_service.create_user()
                if isinstance(func.value.value, ast.Name):
                    receiver_var = func.value.value.id
                    attr_name_chain = func.value.attr
                    method_name = attr_name
                    
                    # Check if receiver is 'self' and we have current_class
                    if receiver_var == 'self' and current_class:
                        # Look up attr_types in current class
                        if current_class in symbols:
                            current_sym = symbols[current_class]
                            if attr_name_chain in current_sym.attr_types:
                                target_class_id = current_sym.attr_types[attr_name_chain]
                                if target_class_id in symbols:
                                    target_class = symbols[target_class_id]
                                    # Try direct method
                                    method_id = f"{target_class.file}::{target_class.name}.{method_name}"
                                    if method_id in symbols:
                                        return method_id, None, False
                                    # Try inherited
                                    inherited = self._find_inherited_method(target_class, method_name, symbols)
                                    if inherited:
                                        return inherited, None, False
                    
                    # Check if receiver is a typed local variable (e.g., server = APIServer())
                    elif receiver_var in type_map:
                        # Look up the class of receiver_var
                        receiver_class_name = type_map[receiver_var]
                        # Find the class symbol
                        receiver_class_id = None
                        for sym_id, sym in symbols.items():
                            if sym.kind == "class" and sym.name == receiver_class_name:
                                receiver_class_id = sym_id
                                break
                        
                        if receiver_class_id and receiver_class_id in symbols:
                            receiver_sym = symbols[receiver_class_id]
                            # Check if attr_name_chain is in attr_types
                            if attr_name_chain in receiver_sym.attr_types:
                                target_class_id = receiver_sym.attr_types[attr_name_chain]
                                if target_class_id in symbols:
                                    target_class = symbols[target_class_id]
                                    # Try direct method
                                    method_id = f"{target_class.file}::{target_class.name}.{method_name}"
                                    if method_id in symbols:
                                        return method_id, None, False
                                    # Try inherited
                                    inherited = self._find_inherited_method(target_class, method_name, symbols)
                                    if inherited:
                                        return inherited, None, False
                
                # General attribute chain - mark as attribute_type_unknown
                return None, {
                    'expr': expr,
                    'name': attr_name,
                    'line': line_num,
                    'reason': 'attribute_type_unknown'
                }, False
            
            # Check for module.function() calls or instance.method() calls
            elif isinstance(func.value, ast.Name):
                receiver_name = func.value.id
                
                # FIX BUG 3 / I1: Check type_map for inferred type (e.g., processor = DataProcessor(...))
                # MUST check this BEFORE import_map to handle variable name == module name collision
                if receiver_name in type_map:
                    inferred_class = type_map[receiver_name]
                    # Find the class symbol to get its file
                    class_symbol_id = None
                    for sym_id, sym in symbols.items():
                        if sym.kind == "class" and sym.name == inferred_class:
                            # Found the class, now try to find the method
                            method_id = f"{sym.file}::{inferred_class}.{attr_name}"
                            if method_id in symbols:
                                return method_id, None, False
                            # Class found but method not found - try first match
                            if class_symbol_id is None:
                                class_symbol_id = sym_id
                    
                    # If we found a class but no method, it might still be in the same file
                    if class_symbol_id:
                        # Try same file as class
                        class_file = symbols[class_symbol_id].file
                        method_id = f"{class_file}::{inferred_class}.{attr_name}"
                        if method_id in symbols:
                            return method_id, None, False
                
                # TASK 4: Check if receiver is an imported module (must check BEFORE param/local)
                if receiver_name in import_map:
                    target_file = import_map[receiver_name]
                    if target_file:
                        # Repo module - try to resolve
                        # Try as function first, then as class with method
                        symbol_id = f"{target_file}::{attr_name}"
                        if symbol_id in symbols:
                            return symbol_id, None, False
                        # Try as class method
                        symbol_id = f"{target_file}::{receiver_name}.{attr_name}"
                        if symbol_id in symbols:
                            return symbol_id, None, False
                    # Module import found (repo or external) but attribute not resolved
                    # This is external_module (stdlib, third-party, or unresolved repo)
                    return None, {
                        'expr': expr,
                        'name': attr_name,
                        'line': line_num,
                        'reason': 'external_module'
                    }, False
                
                # Try to find a class in the same file with this method
                for sym_id, sym in symbols.items():
                    if sym.kind == "class" and sym.file == file_path:
                        class_method_id = f"{file_path}::{sym.name}.{attr_name}"
                        if class_method_id in symbols:
                            return class_method_id, None, False
                
                # TASK 4: Not imported, not in repo - check if builtin method or unknown receiver
                # Examples: kwargs.get(), email.split(), data.append()
                if attr_name in BUILTIN_METHODS:
                    return None, None, True
                
                # Not a builtin method - classify as method_on_unknown_receiver
                return None, {
                    'expr': expr,
                    'name': attr_name,
                    'line': line_num,
                    'reason': 'method_on_unknown_receiver'
                }, False
            
            else:
                # Call on complex expression (e.g., obj.attr.method())
                return None, {
                    'expr': expr,
                    'name': attr_name,
                    'line': line_num,
                    'reason': 'dynamic_call'
                }, False
        
        # Other complex calls (subscripts, etc.)
        else:
            expr = ast.unparse(func)
            return None, {
                'expr': expr,
                'name': '?',
                'line': line_num,
                'reason': 'dynamic_call'
            }, False
    
    def _generate_test_to_source(
        self,
        call_graph: Dict[str, Any],
        symbols: Dict[str, SymbolInfo]
    ) -> Dict[str, List[str]]:
        """TASK 6: Generate test_to_source mapping from call_graph in one function.
        
        Maps test functions to source functions they call directly.
        
        Args:
            call_graph: Call graph with callees
            symbols: Dict of all symbols
            
        Returns:
            Dict mapping test symbol_id to list of source symbol_ids
        """
        test_to_source = {}
        callees = call_graph.get('callees', {})
        
        for symbol_id, symbol in symbols.items():
            if symbol.is_test:
                # Get direct callees that are source functions
                source_callees = []
                for callee_id in callees.get(symbol_id, []):
                    if callee_id in symbols:
                        callee = symbols[callee_id]
                        if not callee.is_test:
                            source_callees.append(callee_id)
                
                if source_callees:
                    test_to_source[symbol_id] = sorted(source_callees)
        
        return test_to_source
    
    def _generate_test_to_source_transitive(
        self,
        call_graph: Dict[str, Any],
        symbols: Dict[str, SymbolInfo],
        max_depth: int = 3
    ) -> Dict[str, List[str]]:
        """TASK 6: Generate transitive test-to-source mapping.
        
        Maps test functions to source functions reachable through callees up to depth.
        
        Args:
            call_graph: Call graph with callees
            symbols: Dict of all symbols
            max_depth: Maximum depth to traverse (default 3)
            
        Returns:
            Dict mapping test symbol_id to list of reachable source symbol_ids
        """
        test_to_source_transitive = {}
        callees = call_graph.get('callees', {})
        
        for symbol_id, symbol in symbols.items():
            if symbol.is_test:
                # Breadth-first search to find reachable source functions
                reachable = set()
                visited = set()
                queue = [(symbol_id, 0)]
                
                while queue:
                    current_id, depth = queue.pop(0)
                    if current_id in visited or depth > max_depth:
                        continue
                    visited.add(current_id)
                    
                    for callee_id in callees.get(current_id, []):
                        if callee_id in symbols:
                            callee = symbols[callee_id]
                            if not callee.is_test:
                                reachable.add(callee_id)
                            # Add to queue for further traversal
                            if depth < max_depth:
                                queue.append((callee_id, depth + 1))
                
                if reachable:
                    test_to_source_transitive[symbol_id] = sorted(reachable)
        
        return test_to_source_transitive
    
    def _check_cache(self, cache_dir: Path, content_hash: str) -> Optional[IndexData]:
        """Check if a cached index exists for the given content hash.
        
        Args:
            cache_dir: Cache directory
            content_hash: Content hash to look up
            
        Returns:
            Cached IndexData or None
        """
        cache_file = cache_dir / f"index_{content_hash[:16]}.json"
        if cache_file.exists():
            try:
                data = read_json(cache_file)
                return IndexData.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load cached index: {e}")
        
        return None
    
    def _write_cache(self, cache_dir: Path, content_hash: str, index_data: IndexData) -> None:
        """Write index to cache.
        
        Args:
            cache_dir: Cache directory
            content_hash: Content hash
            index_data: Index data to cache
        """
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"index_{content_hash[:16]}.json"
        
        try:
            write_json(cache_file, index_data.to_dict())
            logger.info(f"Wrote index to cache: {cache_file.name}")
        except Exception as e:
            logger.warning(f"Failed to write cache: {e}")
