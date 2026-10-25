"""Seed generation from bug reports and groups."""

import logging
from typing import Dict, List

from .graph import Graph

logger = logging.getLogger(__name__)


def seeds_from_bug_group(
    bug_group: Dict,
    bugs: Dict[str, Dict],
    graph: Graph
) -> Dict[str, float]:
    """Generate seeds from a bug group for graph retrieval.
    
    Seeds are generated from:
    1. Failing test node IDs (score 1.0)
    2. Traceback frames in source code (score 1.0 - direct evidence)
    3. Traceback frames in test code (map to test symbol)
    
    Args:
        bug_group: BugGroup dictionary with bug_ids
        bugs: Dict mapping bug_id to BugReport dictionary
        graph: Code graph for symbol lookup
        
    Returns:
        Dict mapping symbol_id to initial score
    """
    seeds: Dict[str, float] = {}
    
    for bug_id in bug_group['bug_ids']:
        bug = bugs.get(bug_id)
        if not bug:
            logger.warning(f"Bug {bug_id} not found in bugs dict")
            continue
        
        # Seed 1: Failing test
        test_name = bug['test_name']
        # test_name format: "tests/test_file.py::test_function"
        # Need to find the test symbol ID
        test_sym_id = _find_test_symbol(test_name, graph)
        if test_sym_id:
            seeds[test_sym_id] = 1.0
        
        # Seed 2: Traceback frames
        frames = bug.get('frames', [])
        for frame in frames:
            file = frame['file']
            line = frame['line']
            
            # Map frame to symbol
            sym_id = graph.symbol_at(file, line)
            if sym_id:
                sym_data = graph.symbols.get(sym_id)
                if sym_data:
                    is_test = sym_data.get('is_test', False)
                    
                    if is_test:
                        # Test frame: map to test symbol (don't add as seed separately)
                        # The test itself is already a seed from above
                        pass
                    else:
                        # Source frame: direct evidence
                        seeds[sym_id] = 1.0
    
    return seeds


def _find_test_symbol(test_name: str, graph: Graph) -> str:
    """Find symbol ID for a test node name.
    
    Args:
        test_name: Test name in format "file/path.py::test_function"
        graph: Code graph
        
    Returns:
        Symbol ID or None
    """
    # Parse test_name
    if '::' not in test_name:
        return None
    
    file_part, func_part = test_name.split('::', 1)
    
    # Handle nested test names (class methods)
    if '::' in func_part:
        # e.g., "TestClass::test_method"
        class_name, method_name = func_part.split('::', 1)
        # Look for method symbol
        symbol_id = f"{file_part}::{class_name}.{method_name}"
    else:
        # Simple function test
        symbol_id = f"{file_part}::{func_part}"
    
    # Check if symbol exists
    if symbol_id in graph.symbols:
        return symbol_id
    
    # Try without full path prefix (just function name)
    # This handles cases where test_name format may differ
    for sym_id, sym_data in graph.symbols.items():
        if sym_data['file'] == file_part and sym_data['name'] == func_part:
            if sym_data.get('is_test', False):
                return sym_id
    
    return None
