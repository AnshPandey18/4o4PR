"""AST heuristics collector - TASK 4.4.

Implements pattern matching heuristics on AST.
"""

import ast
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from common.io import read_json
from detector.collectors import create_candidate

logger = logging.getLogger(__name__)


class ASTHeuristicsCollector:
    """TASK 4.4: Collector for AST-based heuristic patterns."""
    
    def __init__(self, repo_root: Path, index_data: Dict[str, Any]):
        """Initialize AST heuristics collector.
        
        Args:
            repo_root: Repository root path
            index_data: Loaded index.json
        """
        self.repo_root = repo_root
        self.index_data = index_data
        
        # Build symbol lookup
        self.symbols = {}
        symbols_list = index_data.get('symbols', [])
        for sym in symbols_list:
            sym_id = sym.get('id', sym.get('symbol_id'))
            self.symbols[sym_id] = sym
        
        # TASK 4.4.1: Register heuristics
        self.heuristics = [
            self._check_constant_return,
            self._check_identical_branch
        ]
    
    def collect(self, output_dir: Path) -> List[Dict[str, Any]]:
        """TASK 4.4: Run AST heuristics and collect candidates.
        
        Returns:
            List of candidate dicts
        """
        logger.info("Running AST heuristics collector...")
        
        candidates = []
        candidate_idx = 0
        
        # Iterate over all functions and methods
        for symbol_id, symbol in self.symbols.items():
            kind = symbol.get('kind')
            if kind not in ('function', 'method'):
                continue
            
            # Run heuristics on this symbol
            for heuristic in self.heuristics:
                match = heuristic(symbol)
                if match:
                    # TASK 4.4.2: Create heuristic candidate
                    candidate = create_candidate(
                        candidate_id=f"heuristic_{candidate_idx}",
                        source='heuristic',
                        file=symbol.get('file', ''),
                        symbol=symbol.get('qualified_name', ''),
                        line_start=match['line_start'],
                        line_end=match['line_end'],
                        category=match['heuristic'],
                        description=match['description'],
                        evidence=[match['evidence']],
                        raw={'heuristic': match['heuristic'], 'symbol_id': symbol_id}
                    )
                    candidates.append(candidate)
                    candidate_idx += 1
        
        logger.info(f"AST heuristics collector produced {len(candidates)} candidates")
        return candidates
    
    def _check_constant_return(self, symbol: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """TASK 4.4.1: Check for constant-return pattern.
        
        A function with branches where every return returns the same constant.
        
        Args:
            symbol: Symbol dict
            
        Returns:
            Match dict or None
        """
        file_path = self.repo_root / symbol.get('file', '')
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
        except:
            return None
        
        # Find function node
        func_node = self._find_function_node(tree, symbol)
        if not func_node:
            return None
        
        # Check if function has branches
        has_branches = any(
            isinstance(node, (ast.If, ast.For, ast.While, ast.Match))
            for node in ast.walk(func_node)
        )
        
        if not has_branches:
            return None
        
        # Collect all return values
        return_values = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value:
                # Try to evaluate as constant
                try:
                    value_str = ast.unparse(node.value)
                    # Check if it's a simple constant (number, string, True, False, None)
                    if isinstance(node.value, (ast.Constant, ast.NameConstant)):
                        return_values.append((node.value, value_str))
                except:
                    pass
        
        # Need at least 2 returns to check
        if len(return_values) < 2:
            return None
        
        # Check if all returns are the same constant
        first_value = ast.unparse(return_values[0][0])
        if all(ast.unparse(val[0]) == first_value for val in return_values):
            return {
                'heuristic': 'constant-return',
                'line_start': symbol.get('line_start', 0),
                'line_end': symbol.get('line_end', 0),
                'description': f"Function always returns constant {first_value}",
                'evidence': f"Found {len(return_values)} return statements, all returning {first_value}"
            }
        
        return None
    
    def _check_identical_branch(self, symbol: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """TASK 4.4.1: Check for identical-branch pattern.
        
        An if/elif/else where two or more branches have identical bodies.
        
        Args:
            symbol: Symbol dict
            
        Returns:
            Match dict or None
        """
        file_path = self.repo_root / symbol.get('file', '')
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
        except:
            return None
        
        # Find function node
        func_node = self._find_function_node(tree, symbol)
        if not func_node:
            return None
        
        # Find all If nodes
        for node in ast.walk(func_node):
            if isinstance(node, ast.If):
                # Get branches: body, orelse chains, final else
                branches = []
                
                # Main body
                branches.append(('if', node.body))
                
                # elif/else chain
                current = node
                while current.orelse:
                    if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                        # elif
                        current = current.orelse[0]
                        branches.append(('elif', current.body))
                    else:
                        # else
                        branches.append(('else', current.orelse))
                        break
                
                # Need at least 2 branches
                if len(branches) < 2:
                    continue
                
                # Compare branch bodies
                for i in range(len(branches)):
                    for j in range(i + 1, len(branches)):
                        body_i = ast.unparse(branches[i][1]) if branches[i][1] else ''
                        body_j = ast.unparse(branches[j][1]) if branches[j][1] else ''
                        
                        if body_i and body_i == body_j:
                            return {
                                'heuristic': 'identical-branch',
                                'line_start': node.lineno,
                                'line_end': node.end_lineno or node.lineno,
                                'description': f"Identical code in {branches[i][0]} and {branches[j][0]} branches",
                                'evidence': f"Both branches execute: {body_i[:100]}"
                            }
        
        return None
    
    def _find_function_node(self, tree: ast.AST, symbol: Dict[str, Any]) -> Optional[ast.FunctionDef]:
        """Find the AST node for a function symbol.
        
        Args:
            tree: AST tree
            symbol: Symbol dict
            
        Returns:
            FunctionDef node or None
        """
        line_start = symbol.get('line_start', 0)
        name = symbol.get('name', '')
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Match by name and approximate line
                if node.name == name:
                    # Allow some flexibility for decorators
                    if abs(node.lineno - line_start) <= 10:
                        return node
        
        return None


def run_ast_heuristics_collector(
    repo_root: Path,
    index_path: Path,
    output_dir: Path
) -> List[Dict[str, Any]]:
    """Run AST heuristics collector.
    
    Args:
        repo_root: Repository root
        index_path: Path to index.json
        output_dir: Output directory
        
    Returns:
        List of candidates
    """
    index_data = read_json(index_path)
    
    collector = ASTHeuristicsCollector(repo_root, index_data)
    return collector.collect(output_dir)
