"""Repository indexer for static code analysis.

Parses Python files using AST to extract symbols, imports, and call graphs.
Never imports or executes project code.
"""

import ast
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from common.paths import to_posix_rel, is_python_file, is_test_file, should_exclude
from common.pyresolve import ImportResolver, get_module_name
from common.hashing import content_hash, sha1_file
from common.io import write_json, read_json
from .models import IndexData, FileInfo, SymbolInfo, ParseError

logger = logging.getLogger(__name__)


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
        schema_version: str = "1.0"
    ):
        """Initialize the indexer.
        
        Args:
            project_root: Root directory of the project
            import_roots: List of directories where imports resolve from
            test_dirs: List of test directory names
            exclude_patterns: Patterns to exclude from indexing
            schema_version: Index schema version
        """
        self.project_root = Path(project_root)
        self.import_roots = import_roots
        self.test_dirs = test_dirs
        self.exclude_patterns = exclude_patterns
        self.schema_version = schema_version
        
        self.resolver = ImportResolver(self.project_root, import_roots)
        self.import_root_paths = [self.project_root / root for root in import_roots]
    
    def index(self, run_id: str, cache_dir: Optional[Path] = None) -> IndexData:
        """Index the repository.
        
        Args:
            run_id: Unique run identifier
            cache_dir: Optional cache directory for reusing cached indexes
            
        Returns:
            IndexData containing complete repository index
        """
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
                # Update run_id and timestamp
                cached.run_id = run_id
                cached.generated_at = datetime.utcnow().isoformat() + 'Z'
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
                # Still record the file as unparseable
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
        
        # Build call graph
        call_graph = self._build_call_graph(files, symbols)
        logger.info(f"Built call graph with {len(call_graph['callees'])} entries")
        
        # Build test-to-source mapping
        test_to_source = self._build_test_to_source_map(symbols, call_graph)
        logger.info(f"Mapped {len(test_to_source)} tests to source functions")
        
        # Create index data
        index_data = IndexData(
            schema_version=self.schema_version,
            run_id=run_id,
            content_hash=chash,
            generated_at=datetime.utcnow().isoformat() + 'Z',
            import_roots=self.import_roots,
            files=files,
            symbols=symbols,
            call_graph=call_graph,
            test_to_source=test_to_source,
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
        
        # Determine file kind
        kind = "test" if is_test_file(rel_path, self.test_dirs) else "source"
        
        # Get module name
        module_name = get_module_name(file_path, self.import_root_paths, self.project_root)
        
        # Extract module docstring
        docstring = ast.get_docstring(tree)
        if docstring:
            # Keep only first line
            docstring = docstring.split('\n')[0].strip()
        
        # Extract imports
        imports = self.resolver.extract_imports_from_file(file_path)
        
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
    
    def _extract_symbols(
        self,
        tree: ast.AST,
        source: str,
        file_path: str,
        kind: str
    ) -> Dict[str, SymbolInfo]:
        """Extract all symbols (functions, classes, methods) from AST.
        
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
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract class
                class_info = self._extract_class_info(node, source_lines, file_path, kind)
                symbols[class_info.symbol_id] = class_info
                
                # Extract methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_info = self._extract_function_info(
                            item, source_lines, file_path, kind, parent_class=node.name
                        )
                        symbols[method_info.symbol_id] = method_info
            
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only extract top-level functions (not nested or methods)
                if self._is_top_level(node, tree):
                    func_info = self._extract_function_info(node, source_lines, file_path, kind)
                    symbols[func_info.symbol_id] = func_info
        
        return symbols
    
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
        kind: str
    ) -> SymbolInfo:
        """Extract information about a class definition.
        
        Args:
            node: AST ClassDef node
            source_lines: Source code lines
            file_path: POSIX relative file path
            kind: "source" or "test"
            
        Returns:
            SymbolInfo for the class
        """
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
        
        return SymbolInfo(
            symbol_id=symbol_id,
            kind="class",
            name=node.name,
            file=file_path,
            line_start=line_start,
            line_end=line_end,
            signature="",  # Classes don't have a signature like functions
            decorators=decorators,
            docstring=docstring,
            parent_class=None,
            is_test=kind == "test"
        )
    
    def _extract_function_info(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: List[str],
        file_path: str,
        kind: str,
        parent_class: Optional[str] = None
    ) -> SymbolInfo:
        """Extract information about a function or method definition.
        
        Args:
            node: AST FunctionDef or AsyncFunctionDef node
            source_lines: Source code lines
            file_path: POSIX relative file path
            kind: "source" or "test"
            parent_class: Parent class name if this is a method
            
        Returns:
            SymbolInfo for the function/method
        """
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
        if parent_class:
            qualified_name = f"{parent_class}.{node.name}"
        else:
            qualified_name = node.name
        
        symbol_id = f"{file_path}::{qualified_name}"
        
        # Check if it's a test function
        is_test = kind == "test" and node.name.startswith("test_")
        
        # Count unresolved calls (will be populated during call graph building)
        unresolved_calls = 0
        
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
            unresolved_calls=unresolved_calls
        )
    
    def _format_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Format function signature as a string.
        
        Args:
            node: Function AST node
            
        Returns:
            Signature string (e.g., "(a, b: int) -> str")
        """
        args_parts = []
        
        # Regular arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
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
    
    def _build_call_graph(
        self,
        files: Dict[str, FileInfo],
        symbols: Dict[str, SymbolInfo]
    ) -> Dict[str, Dict[str, List[str]]]:
        """Build call graph for all functions.
        
        Only includes calls that can be resolved with certainty.
        
        Args:
            files: Dict of FileInfo
            symbols: Dict of SymbolInfo
            
        Returns:
            Dict with "callees" and "callers" mappings
        """
        callees: Dict[str, List[str]] = {}
        callers: Dict[str, List[str]] = {}
        
        # For each function, find its calls
        for symbol_id, symbol in symbols.items():
            if symbol.kind in ("function", "method"):
                # Parse the file to analyze calls
                file_path = self.project_root / symbol.file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        source = f.read()
                    tree = ast.parse(source)
                    
                    # Find the function node
                    func_node = self._find_function_node(tree, symbol)
                    if func_node:
                        resolved, unresolved = self._extract_calls(
                            func_node, symbol.file, files[symbol.file], symbols
                        )
                        callees[symbol_id] = resolved
                        symbol.unresolved_calls = unresolved
                        
                        # Update callers mapping
                        for callee_id in resolved:
                            if callee_id not in callers:
                                callers[callee_id] = []
                            if symbol_id not in callers[callee_id]:
                                callers[callee_id].append(symbol_id)
                
                except:
                    # If we can't analyze calls, leave empty
                    callees[symbol_id] = []
        
        return {'callees': callees, 'callers': callers}
    
    def _find_function_node(
        self,
        tree: ast.AST,
        symbol: SymbolInfo
    ) -> Optional[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Find the AST node for a function symbol.
        
        Args:
            tree: Module AST tree
            symbol: SymbolInfo to find
            
        Returns:
            Function node or None
        """
        if symbol.parent_class:
            # It's a method - find the class first
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == symbol.parent_class:
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if item.name == symbol.name:
                                return item
        else:
            # It's a function
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == symbol.name and self._is_top_level(node, tree):
                        return node
        
        return None
    
    def _extract_calls(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        file_info: FileInfo,
        symbols: Dict[str, SymbolInfo]
    ) -> Tuple[List[str], int]:
        """Extract function calls from a function body.
        
        Only resolves calls with high certainty:
        - Same-file function calls
        - Imported function calls
        - Method calls on self (within same class)
        
        Args:
            func_node: Function AST node
            file_path: POSIX relative file path
            file_info: FileInfo for the containing file
            symbols: Dict of all symbols
            
        Returns:
            Tuple of (resolved_call_ids, unresolved_count)
        """
        resolved_calls: Set[str] = set()
        unresolved_count = 0
        
        # Build import mapping for this file
        import_map = self._build_import_map(file_info.imports)
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                # Try to resolve the call
                call_id = self._resolve_call(node, file_path, import_map, symbols)
                if call_id:
                    resolved_calls.add(call_id)
                else:
                    unresolved_count += 1
        
        return list(sorted(resolved_calls)), unresolved_count
    
    def _build_import_map(self, imports: List[Dict]) -> Dict[str, str]:
        """Build a mapping from imported names to their symbol IDs.
        
        Args:
            imports: List of import dicts
            
        Returns:
            Dict mapping name to file path (not full symbol_id, just file)
        """
        import_map = {}
        
        for imp in imports:
            resolved_file = imp.get('resolved_file')
            if resolved_file:
                for name_info in imp.get('names', []):
                    name = name_info.get('name', '')
                    asname = name_info.get('asname')
                    key = asname if asname else name
                    if key:
                        import_map[key] = resolved_file
        
        return import_map
    
    def _resolve_call(
        self,
        call_node: ast.Call,
        file_path: str,
        import_map: Dict[str, str],
        symbols: Dict[str, SymbolInfo]
    ) -> Optional[str]:
        """Try to resolve a call to a symbol ID.
        
        Args:
            call_node: AST Call node
            file_path: POSIX relative file path
            import_map: Import name to file mapping
            symbols: Dict of all symbols
            
        Returns:
            Symbol ID or None if unresolvable
        """
        func = call_node.func
        
        # Simple name call: func()
        if isinstance(func, ast.Name):
            name = func.id
            
            # Check if it's imported
            if name in import_map:
                target_file = import_map[name]
                symbol_id = f"{target_file}::{name}"
                if symbol_id in symbols:
                    return symbol_id
            
            # Check if it's in the same file
            symbol_id = f"{file_path}::{name}"
            if symbol_id in symbols:
                return symbol_id
        
        # Attribute call: module.func() or self.method()
        elif isinstance(func, ast.Attribute):
            attr_name = func.attr
            
            # Check for self.method() calls
            if isinstance(func.value, ast.Name) and func.value.id == 'self':
                # Find the class this method belongs to
                for symbol in symbols.values():
                    if symbol.file == file_path and symbol.kind == "method":
                        qualified_name = symbol.qualified_name if hasattr(symbol, 'qualified_name') else f"{symbol.parent_class}.{symbol.name}"
                        if symbol.name == attr_name:
                            return symbol.symbol_id
            
            # Check for module.function() calls
            elif isinstance(func.value, ast.Name):
                module_name = func.value.id
                if module_name in import_map:
                    target_file = import_map[module_name]
                    symbol_id = f"{target_file}::{attr_name}"
                    if symbol_id in symbols:
                        return symbol_id
        
        return None
    
    def _build_test_to_source_map(
        self,
        symbols: Dict[str, SymbolInfo],
        call_graph: Dict[str, Dict[str, List[str]]]
    ) -> Dict[str, List[str]]:
        """Build mapping from test functions to source functions they call.
        
        Args:
            symbols: Dict of all symbols
            call_graph: Call graph with callees
            
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
