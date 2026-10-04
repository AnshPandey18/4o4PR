"""Python import resolution and function extraction utilities.

Resolves import statements to actual file paths and extracts function/class
definitions from Python source code using AST parsing.
"""

import ast
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any


class ImportResolver:
    """Resolves Python imports to file paths."""
    
    def __init__(self, project_root: Path, import_roots: List[str]):
        """Initialize the import resolver.
        
        Args:
            project_root: Root directory of the project
            import_roots: List of directories where imports resolve from (e.g., ["src"])
        """
        self.project_root = Path(project_root)
        self.import_roots = [self.project_root / root for root in import_roots]
        # Always include project root itself
        if self.project_root not in self.import_roots:
            self.import_roots.append(self.project_root)
    
    def resolve_import(self, module_name: str, from_file: Optional[Path] = None) -> Optional[Path]:
        """Resolve an import statement to a file path.
        
        Args:
            module_name: Dotted module name (e.g., "calculator" or "utils.math")
            from_file: File containing the import (for relative imports)
            
        Returns:
            Resolved file path, or None if not found
        """
        # Check if it's a standard library module
        if self._is_stdlib(module_name):
            return None
        
        # Try to resolve in each import root
        for root in self.import_roots:
            resolved = self._try_resolve_in_root(module_name, root)
            if resolved and resolved.exists():
                return resolved
        
        return None
    
    def resolve_relative_import(
        self,
        module_name: str,
        level: int,
        from_file: Path
    ) -> Optional[Path]:
        """Resolve a relative import (from . import x or from .. import y).
        
        Args:
            module_name: Module name (can be empty for "from . import x")
            level: Number of dots (1 for ".", 2 for "..", etc.)
            from_file: File containing the import
            
        Returns:
            Resolved file path, or None if not found
        """
        # Get the package directory of from_file
        current_dir = from_file.parent
        
        # Go up 'level' directories
        for _ in range(level):
            current_dir = current_dir.parent
            if current_dir == self.project_root.parent:
                return None  # Went too far up
        
        if not module_name:
            # "from . import x" - the module is the current package
            init_file = current_dir / "__init__.py"
            return init_file if init_file.exists() else None
        
        # Resolve the module name relative to current_dir
        return self._try_resolve_in_root(module_name, current_dir)
    
    def _try_resolve_in_root(self, module_name: str, root: Path) -> Optional[Path]:
        """Try to resolve a module name in a specific root directory.
        
        Args:
            module_name: Dotted module name
            root: Root directory to search in
            
        Returns:
            Resolved file path, or None if not found
        """
        parts = module_name.split('.')
        
        # Try as a module file (e.g., calculator.py)
        module_file = root / Path(*parts[:-1]) / f"{parts[-1]}.py"
        if module_file.exists():
            return module_file
        
        # Try as a package (e.g., calculator/__init__.py)
        package_init = root / Path(*parts) / "__init__.py"
        if package_init.exists():
            return package_init
        
        return None
    
    def _is_stdlib(self, module_name: str) -> bool:
        """Check if a module is from the standard library.
        
        Args:
            module_name: Module name to check
            
        Returns:
            True if it's a standard library module
        """
        # Get the top-level module name
        top_level = module_name.split('.')[0]
        
        # List of common stdlib modules (not exhaustive but covers most cases)
        stdlib_modules = {
            'abc', 'ast', 'asyncio', 'collections', 'concurrent', 'contextlib',
            'copy', 'csv', 'dataclasses', 'datetime', 'decimal', 'enum', 'functools',
            'gc', 'glob', 'hashlib', 'heapq', 'html', 'http', 'importlib', 'inspect',
            'io', 'itertools', 'json', 'logging', 'math', 'multiprocessing', 'operator',
            'os', 'pathlib', 'pickle', 'queue', 're', 'shutil', 'socket', 'sqlite3',
            'statistics', 'string', 'subprocess', 'sys', 'tempfile', 'threading',
            'time', 'typing', 'unittest', 'urllib', 'uuid', 'warnings', 'weakref',
            'xml', 'zipfile'
        }
        
        return top_level in stdlib_modules or top_level in sys.builtin_module_names
    
    def extract_imports_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract all imports from a Python file.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of import dicts with keys: module, names, line, resolved_file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return []
        
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self.resolve_import(alias.name, file_path)
                    imports.append({
                        'module': alias.name,
                        'names': [{'name': alias.name, 'asname': alias.asname}],
                        'line': node.lineno,
                        'resolved_file': resolved.relative_to(self.project_root).as_posix() if resolved else None
                    })
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level > 0:
                    # Relative import
                    resolved = self.resolve_relative_import(module, node.level, file_path)
                else:
                    # Absolute import
                    resolved = self.resolve_import(module, file_path)
                
                names = [{'name': alias.name, 'asname': alias.asname} for alias in node.names]
                imports.append({
                    'module': module,
                    'names': names,
                    'line': node.lineno,
                    'resolved_file': resolved.relative_to(self.project_root).as_posix() if resolved else None,
                    'level': node.level if node.level > 0 else None
                })
        
        return imports


def find_function(file_path: Path, name_or_qualname: str) -> Optional[Dict[str, Any]]:
    """Find a function or method in a file and return its metadata.
    
    Args:
        file_path: Path to Python file
        name_or_qualname: Function name or qualified name (e.g., "subtract" or "Calculator.add")
        
    Returns:
        Dict with keys: qualified_name, line_start, line_end, signature
        or None if not found
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return None
    
    # Split qualified name
    parts = name_or_qualname.split('.')
    
    if len(parts) == 1:
        # Simple function name
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == parts[0]:
                    return _extract_function_info(node, source, parts[0])
    else:
        # Qualified name (Class.method)
        class_name = parts[0]
        method_name = parts[1]
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == method_name:
                            qualname = f"{class_name}.{method_name}"
                            return _extract_function_info(item, source, qualname)
    
    return None


def _extract_function_info(node: ast.FunctionDef | ast.AsyncFunctionDef, source: str, qualname: str) -> Dict[str, Any]:
    """Extract information about a function node.
    
    Args:
        node: AST function node
        source: Complete source code
        qualname: Qualified name of the function
        
    Returns:
        Dict with function metadata
    """
    # Get line_start including decorators
    line_start = node.lineno
    if node.decorator_list:
        line_start = min(dec.lineno for dec in node.decorator_list)
    
    line_end = node.end_lineno or node.lineno
    
    # Extract signature
    args_str = _format_arguments(node.args)
    returns_str = ""
    if node.returns:
        try:
            returns_str = f" -> {ast.unparse(node.returns)}"
        except:
            returns_str = ""
    
    signature = f"({args_str}){returns_str}"
    
    return {
        'qualified_name': qualname,
        'line_start': line_start,
        'line_end': line_end,
        'signature': signature
    }


def _format_arguments(args: ast.arguments) -> str:
    """Format function arguments as a string.
    
    Args:
        args: AST arguments node
        
    Returns:
        Formatted arguments string
    """
    parts = []
    
    # Positional arguments
    for arg in args.args:
        arg_str = arg.arg
        if arg.annotation:
            try:
                arg_str += f": {ast.unparse(arg.annotation)}"
            except:
                pass
        parts.append(arg_str)
    
    # *args
    if args.vararg:
        vararg_str = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            try:
                vararg_str += f": {ast.unparse(args.vararg.annotation)}"
            except:
                pass
        parts.append(vararg_str)
    
    # **kwargs
    if args.kwarg:
        kwarg_str = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            try:
                kwarg_str += f": {ast.unparse(args.kwarg.annotation)}"
            except:
                pass
        parts.append(kwarg_str)
    
    return ", ".join(parts)


def get_module_name(file_path: Path, import_roots: List[Path], project_root: Path) -> Optional[str]:
    """Get the dotted module name for a file based on import roots.
    
    Args:
        file_path: Path to Python file
        import_roots: List of import root directories
        project_root: Project root directory
        
    Returns:
        Dotted module name (e.g., "calculator" or "utils.math") or None
    """
    # Try each import root
    for root in import_roots:
        try:
            rel_path = file_path.relative_to(root)
            # Convert path to module name
            parts = list(rel_path.parts)
            if parts[-1] == '__init__.py':
                parts = parts[:-1]
            elif parts[-1].endswith('.py'):
                parts[-1] = parts[-1][:-3]
            
            if parts:
                return '.'.join(parts)
        except ValueError:
            continue
    
    return None
