"""BM25 query builder from bug groups.

Builds search queries from bug group data with term source tracking.

Query Term Sources (in order):
1. Test name (with "test"/"tests" removed)
2. Error type and error message (pytest boilerplate stripped)
3. Test body identifiers (AST-based: Name and Attribute nodes only)
4. Traceback source frame identifiers (symbol_at mapping)
"""

from typing import List, Dict, Tuple, Optional
import ast
import re

from retrieval.tokenizer import tokenize


def build_query(
    bug_group: Dict, 
    bugs: Dict[str, Dict],
    graph: Optional[any] = None
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Build BM25 query from a bug group.
    
    Args:
        bug_group: Bug group dictionary (from bug_groups.json)
        bugs: Dictionary mapping bug_id -> bug dict (from bug_report.json)
        graph: Optional retrieval.graph.Graph instance for symbol_at lookups
        
    Returns:
        Tuple of (query_terms, sources) where:
        - query_terms: List of query terms (preserving duplicates for weighting)
        - sources: Dict mapping source name -> list of terms from that source
    """
    sources = {
        'test_names': [],
        'error_info': [],
        'test_body': [],
        'traceback': []
    }
    
    bug_ids = bug_group.get('bug_ids', [])
    
    for bug_id in bug_ids:
        if bug_id not in bugs:
            continue
        
        bug = bugs[bug_id]
        
        # Source 1: Test name
        test_name = bug.get('test_name', '')
        if test_name:
            name_terms = _extract_test_name_terms(test_name)
            sources['test_names'].extend(name_terms)
        
        # Source 2: Error type and message
        error_type = bug.get('error_type', '')
        error_message = bug.get('error_message', '')
        
        if error_type:
            type_terms = tokenize(error_type)
            sources['error_info'].extend(type_terms)
        
        if error_message:
            # Strip pytest boilerplate before tokenizing
            cleaned_message = _strip_pytest_boilerplate(error_message)
            message_terms = _extract_message_terms(cleaned_message)
            sources['error_info'].extend(message_terms)
        
        # Source 3: Test body identifiers (AST-based)
        test_code = bug.get('failing_function_code') or bug.get('code', '')
        if test_code:
            body_terms = _extract_ast_identifiers(test_code)
            sources['test_body'].extend(body_terms)
        
        # Source 4: Traceback source frames (use symbol_at if graph available)
        frames = bug.get('frames', [])
        for frame in frames:
            # Only include frames from source files (not test files, not external)
            if frame.get('external', False):
                continue
            
            file_path = frame.get('file', '')
            # Skip test files
            if 'test' in file_path.lower():
                continue
            
            if graph:
                # Use symbol_at to map (file, line) -> symbol
                line_no = frame.get('line', 0)
                if line_no and file_path:
                    symbol_id = graph.symbol_at(file_path, line_no)
                    if symbol_id:
                        # Extract symbol name and parent class
                        frame_terms = _extract_symbol_terms(symbol_id, graph)
                        sources['traceback'].extend(frame_terms)
            else:
                # Fallback: use function name only
                function_name = frame.get('function', '')
                if function_name:
                    func_terms = tokenize(function_name)
                    sources['traceback'].extend(func_terms)
    
    # Deduplicate within each source
    for source_name in sources:
        sources[source_name] = _deduplicate_preserve_order(sources[source_name])
    
    # Build final query (all terms, with duplicates for weighting)
    query_terms = []
    for source_name in ['test_names', 'error_info', 'test_body', 'traceback']:
        query_terms.extend(sources[source_name])
    
    # Filter out digit-only tokens
    query_terms = [t for t in query_terms if not t.isdigit()]
    for source_name in sources:
        sources[source_name] = [t for t in sources[source_name] if not t.isdigit()]
    
    return query_terms, sources


def _extract_test_name_terms(test_name: str) -> List[str]:
    """Extract terms from test name, removing "test"/"tests".
    
    Args:
        test_name: Test name like "tests/test_module.py::test_function_name"
        
    Returns:
        List of terms with "test" and "tests" removed
    """
    # Extract just the function/class name part
    if '::' in test_name:
        test_name = test_name.split('::')[-1]
    
    # Tokenize
    terms = tokenize(test_name)
    
    # Remove "test" and "tests" (these appear in every test name)
    filtered = [t for t in terms if t not in ('test', 'tests')]
    
    return filtered


def _strip_pytest_boilerplate(message: str) -> str:
    """Strip pytest-specific boilerplate from error messages.
    
    Args:
        message: Raw error message from pytest
        
    Returns:
        Cleaned message with boilerplate removed
    """
    # Remove "E   " continuation markers
    message = re.sub(r'^E\s+', '', message, flags=re.MULTILINE)
    
    # Remove lines containing pytest output hints
    lines = message.split('\n')
    cleaned_lines = []
    
    for line in lines:
        lower_line = line.lower()
        # Skip lines with pytest boilerplate
        if any(pattern in lower_line for pattern in [
            'full diff',
            'use -v',
            'use `-v',
            '-vv',
            'full output truncated',
            'truncating',
            '[truncated]',
            'lines hidden',
            'at index',  # "At index N diff:" lines
        ]):
            continue
        cleaned_lines.append(line)
    
    message = '\n'.join(cleaned_lines)
    
    # Clean up extra whitespace
    message = re.sub(r'\s+', ' ', message).strip()
    
    return message


def _extract_message_terms(message: str) -> List[str]:
    """Extract terms from error message, skipping pure literals.
    
    Args:
        message: Error message string
        
    Returns:
        List of identifier and word terms
    """
    # Skip common assertion literals
    skip_literals = {'true', 'false', 'none'}
    
    terms = tokenize(message)
    
    # Filter out literal-only terms
    filtered = [t for t in terms if t not in skip_literals]
    
    return filtered


def _extract_ast_identifiers(code: str) -> List[str]:
    """Extract identifiers from code using AST (Names and Attributes only).
    
    Parses the code with ast and collects:
    - ast.Name.id nodes
    - ast.Attribute.attr nodes
    
    Skips docstrings, comments, and string constants.
    
    Args:
        code: Python code string
        
    Returns:
        List of identifier terms
    """
    identifiers = []
    
    try:
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                # Collect variable/function names
                identifiers.append(node.id)
            elif isinstance(node, ast.Attribute):
                # Collect attribute accesses (e.g., obj.method -> "method")
                identifiers.append(node.attr)
    except SyntaxError:
        # If AST parsing fails, fall back to simple tokenization
        # Remove string literals first
        code_no_strings = re.sub(r'["\']([^"\']*)["\']', ' ', code)
        return tokenize(code_no_strings)
    
    # Tokenize collected identifiers (handles camelCase, snake_case, stemming)
    terms = []
    for ident in identifiers:
        terms.extend(tokenize(ident))
    
    return terms


def _extract_symbol_terms(symbol_id: str, graph: any) -> List[str]:
    """Extract terms from a symbol ID using the graph.
    
    Args:
        symbol_id: Symbol ID like "src/module.py::ClassName.method_name"
        graph: Graph instance
        
    Returns:
        List of terms (symbol name + parent class name if applicable)
    """
    terms = []
    
    # Get symbol data
    symbol_data = graph.symbols.get(symbol_id)
    if not symbol_data:
        return terms
    
    # Extract symbol name (last component after ::)
    if '::' in symbol_id:
        name = symbol_id.split('::')[-1]
        
        # If it has a dot (Class.method), extract both parts
        if '.' in name:
            parent_class, method_name = name.rsplit('.', 1)
            terms.extend(tokenize(parent_class))
            terms.extend(tokenize(method_name))
        else:
            terms.extend(tokenize(name))
    
    return terms


def _extract_identifiers(code: str) -> List[str]:
    """Extract identifiers from code, not string literals.
    
    Args:
        code: Python code string
        
    Returns:
        List of identifier terms
    """
    # Remove string literals first
    # Simple heuristic: remove content between quotes
    code_no_strings = re.sub(r'["\']([^"\']*)["\']', ' ', code)
    
    # Tokenize remaining code
    terms = tokenize(code_no_strings)
    
    return terms


def _deduplicate_preserve_order(items: List[str]) -> List[str]:
    """Remove duplicates while preserving first occurrence order.
    
    Args:
        items: List with possible duplicates
        
    Returns:
        List with duplicates removed, order preserved
    """
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def query_from_text(text: str) -> List[str]:
    """Build query from arbitrary text (for retrieve_more path).
    
    Args:
        text: Text to query
        
    Returns:
        List of query terms
    """
    return tokenize(text)
