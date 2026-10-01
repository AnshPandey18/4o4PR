"""Code sanitization for Context Builder.

Strips docstrings, comments, and redacts secrets from code before sending to LLM.
"""

import ast
import re
import tokenize
from io import StringIO
from typing import List, Tuple
from .models import SanitizationSummary


def sanitize_test_code(source: str) -> Tuple[str, SanitizationSummary]:
    """Sanitize test code by removing docstrings and specific comments.
    
    Args:
        source: Test source code
        
    Returns:
        Tuple of (sanitized_source, summary)
    """
    summary = SanitizationSummary()
    
    # Remove docstrings
    try:
        source, docstrings_removed = _remove_docstrings(source)
        summary.docstrings_removed = docstrings_removed
    except:
        pass  # If AST parsing fails, leave source as-is
    
    # Remove "should fail/pass" comments
    try:
        source, comments_removed = _remove_should_comments(source)
        summary.comments_removed = comments_removed
    except:
        pass
    
    return source, summary


def sanitize_source_code(source: str, redact_patterns: List[str]) -> Tuple[str, SanitizationSummary]:
    """Sanitize source code by redacting secrets.
    
    Args:
        source: Source code
        redact_patterns: List of regex patterns for secrets
        
    Returns:
        Tuple of (sanitized_source, summary)
    """
    summary = SanitizationSummary()
    
    # Redact secrets
    source, secrets_redacted = _redact_secrets(source, redact_patterns)
    summary.secrets_redacted = secrets_redacted
    
    return source, summary


def _remove_docstrings(source: str) -> Tuple[str, int]:
    """Remove docstrings from source code.
    
    Args:
        source: Source code
        
    Returns:
        Tuple of (source without docstrings, count of docstrings removed)
    """
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    
    # Collect line ranges of docstrings
    docstring_ranges = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            docstring_node = None
            
            # Check for docstring
            if isinstance(node, ast.Module):
                if (node.body and 
                    isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                    docstring_node = node.body[0]
            else:
                if (node.body and 
                    isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                    docstring_node = node.body[0]
            
            if docstring_node:
                start_line = docstring_node.lineno - 1  # Convert to 0-indexed
                end_line = docstring_node.end_lineno if docstring_node.end_lineno else start_line + 1
                docstring_ranges.append((start_line, end_line))
    
    # Sort ranges by line number (reverse so we can remove from end)
    docstring_ranges.sort(reverse=True)
    
    # Remove docstring lines
    for start, end in docstring_ranges:
        # Replace lines with empty lines to preserve line numbers
        for i in range(start, end):
            if i < len(lines):
                lines[i] = '\n'
    
    return ''.join(lines), len(docstring_ranges)


def _remove_should_comments(source: str) -> Tuple[str, int]:
    """Remove comments matching 'should fail' or 'should pass'.
    
    Args:
        source: Source code
        
    Returns:
        Tuple of (source without matching comments, count removed)
    """
    # Pattern to match comments containing "should fail" or "should pass" (case insensitive)
    pattern = re.compile(r'(?i)\bshould\s+(fail|pass)\b')
    
    try:
        # Use tokenize to find comments
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        lines = source.splitlines(keepends=True)
        removed_count = 0
        
        for token in tokens:
            if token.type == tokenize.COMMENT:
                if pattern.search(token.string):
                    # Remove this comment
                    line_num = token.start[0] - 1  # Convert to 0-indexed
                    col_start = token.start[1]
                    col_end = token.end[1]
                    
                    if line_num < len(lines):
                        line = lines[line_num]
                        # Remove the comment part
                        lines[line_num] = line[:col_start] + line[col_end:]
                        removed_count += 1
        
        return ''.join(lines), removed_count
    
    except:
        # If tokenization fails, fall back to regex
        modified_lines = []
        removed_count = 0
        
        for line in source.splitlines(keepends=True):
            if '#' in line and pattern.search(line):
                # Remove the comment
                modified_line = line.split('#')[0] + '\n'
                modified_lines.append(modified_line)
                removed_count += 1
            else:
                modified_lines.append(line)
        
        return ''.join(modified_lines), removed_count


def _redact_secrets(source: str, patterns: List[str]) -> Tuple[str, int]:
    """Redact secrets matching patterns.
    
    Args:
        source: Source code
        patterns: List of regex patterns
        
    Returns:
        Tuple of (redacted source, count of redactions)
    """
    redacted = source
    redaction_count = 0
    
    for pattern_str in patterns:
        try:
            pattern = re.compile(pattern_str)
            matches = pattern.findall(redacted)
            if matches:
                redaction_count += len(matches)
                redacted = pattern.sub('[REDACTED]', redacted)
        except re.error:
            # Skip invalid patterns
            continue
    
    return redacted, redaction_count


def should_exclude_file(file_path: str, denylist: List[str]) -> bool:
    """Check if a file should be excluded from context.
    
    Args:
        file_path: File path to check
        denylist: List of patterns to exclude
        
    Returns:
        True if file should be excluded
    """
    file_path_lower = file_path.lower()
    
    for pattern in denylist:
        pattern_lower = pattern.lower()
        
        # Support wildcards
        if '*' in pattern_lower:
            import fnmatch
            if fnmatch.fnmatch(file_path_lower, pattern_lower):
                return True
        elif pattern_lower in file_path_lower:
            return True
    
    return False
