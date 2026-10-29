"""LLM reviewer collector - TASK 4.5.

Reviews functions with branches/calls/returns for potential bugs.
"""

import ast
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from common.io import read_json, write_text
from detector.collectors import create_candidate

logger = logging.getLogger(__name__)


class LLMReviewerCollector:
    """TASK 4.5: Collector using LLM to review functions."""
    
    def __init__(self, repo_root: Path, index_data: Dict[str, Any], graph_data: Dict[str, Any]):
        """Initialize LLM reviewer collector.
        
        Args:
            repo_root: Repository root path
            index_data: Loaded index.json
            graph_data: Loaded graph.json
        """
        self.repo_root = repo_root
        self.index_data = index_data
        self.graph_data = graph_data
        
        # Build symbol lookup
        self.symbols = {}
        symbols_list = index_data.get('symbols', [])
        for sym in symbols_list:
            sym_id = sym.get('id', sym.get('symbol_id'))
            self.symbols[sym_id] = sym
        
        # Build graph lookup
        self.callees = {}
        self.callers = {}
        for edge in graph_data.get('edges', []):
            from_id = edge.get('from')
            to_id = edge.get('to')
            if edge.get('kind') == 'call':
                self.callees.setdefault(from_id, []).append(to_id)
                self.callers.setdefault(to_id, []).append(from_id)
    
    def collect(self, output_dir: Path) -> List[Dict[str, Any]]:
        """TASK 4.5: Run LLM reviewer and collect candidates.
        
        Returns:
            List of candidate dicts
        """
        # TASK 4.5.3: Respect LLM kill switch
        if os.getenv('LLM_DISABLED') == '1':
            logger.info("LLM disabled (LLM_DISABLED=1), skipping LLM reviewer")
            return []
        
        logger.info("Running LLM reviewer collector...")
        
        # TASK 4.5.1: Select functions with branches, calls, or returns
        target_functions = self._select_target_functions()
        
        if not target_functions:
            logger.info("No functions selected for LLM review")
            return []
        
        logger.info(f"Selected {len(target_functions)} functions for LLM review")
        
        candidates = []
        candidate_idx = 0
        
        # Process each function (in practice, would batch these)
        for symbol_id in target_functions[:10]:  # Limit to 10 for now
            candidate = self._review_function(symbol_id, candidate_idx, output_dir)
            if candidate:
                candidates.append(candidate)
                candidate_idx += 1
        
        logger.info(f"LLM reviewer produced {len(candidates)} candidates")
        return candidates
    
    def _select_target_functions(self) -> List[str]:
        """TASK 4.5.1: Select functions with branches, calls, or returns.
        
        Returns:
            List of symbol IDs
        """
        targets = []
        
        for symbol_id, symbol in self.symbols.items():
            kind = symbol.get('kind')
            if kind not in ('function', 'method'):
                continue
            
            # Check if function has branches, calls, or returns
            file_path = self.repo_root / symbol.get('file', '')
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                tree = ast.parse(source)
            except:
                continue
            
            func_node = self._find_function_node(tree, symbol)
            if not func_node:
                continue
            
            # Check for branches, calls, or returns
            has_branch = False
            has_call = False
            has_return = False
            
            for node in ast.walk(func_node):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Match)):
                    has_branch = True
                if isinstance(node, ast.Call):
                    has_call = True
                if isinstance(node, ast.Return):
                    has_return = True
            
            if has_branch or has_call or has_return:
                targets.append(symbol_id)
        
        return targets
    
    def _review_function(self, symbol_id: str, idx: int, output_dir: Path) -> Optional[Dict[str, Any]]:
        """Review a single function with LLM.
        
        Args:
            symbol_id: Symbol ID to review
            idx: Candidate index
            output_dir: Output directory
            
        Returns:
            Candidate dict or None
        """
        symbol = self.symbols.get(symbol_id)
        if not symbol:
            return None
        
        # TASK 4.5.2: Build prompt
        prompt = self._build_prompt(symbol_id)
        if not prompt:
            return None
        
        # Save prompt for debugging
        prompt_file = output_dir / f"llm_review_{idx}.txt"
        write_text(prompt_file, prompt)
        
        # TASK 4.5.3: In real implementation, would call LLM here
        # For now, return None (placeholder)
        # Real implementation would:
        # 1. Send prompt to LLM
        # 2. Parse JSON response
        # 3. Validate response
        # 4. Create candidate
        
        # TASK 4.5.4: Log rejected response if invalid JSON
        logger.debug(f"LLM review prompt saved to {prompt_file}")
        
        # Placeholder: Return None (no candidates from LLM in this implementation)
        return None
    
    def _build_prompt(self, symbol_id: str) -> Optional[str]:
        """TASK 4.5.2: Build review prompt.
        
        Args:
            symbol_id: Symbol ID
            
        Returns:
            Prompt text or None
        """
        symbol = self.symbols.get(symbol_id)
        if not symbol:
            return None
        
        # Get function source with line numbers
        file_path = self.repo_root / symbol.get('file', '')
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            line_start = symbol.get('line_start', 1)
            line_end = symbol.get('line_end', 1)
            
            source_lines = []
            for i in range(line_start - 1, min(line_end, len(lines))):
                source_lines.append(f"{i + 1:4d} | {lines[i].rstrip()}")
            
            source_with_lines = '\n'.join(source_lines)
        except:
            return None
        
        # Get signature and docstring
        signature = symbol.get('signature', '')
        docstring = symbol.get('docstring', '')
        
        # Get direct callers and callees
        direct_callees = self.callees.get(symbol_id, [])[:5]
        direct_callers = self.callers.get(symbol_id, [])[:5]
        
        callee_names = [self.symbols[c].get('qualified_name', c) for c in direct_callees if c in self.symbols]
        caller_names = [self.symbols[c].get('qualified_name', c) for c in direct_callers if c in self.symbols]
        
        # Build prompt
        prompt = f"""Review this function for potential bugs.

Function: {symbol.get('qualified_name', '')}
Signature: {signature}
{f'Docstring: {docstring}' if docstring else ''}

Source code with line numbers:
{source_with_lines}

Context:
- Calls: {', '.join(callee_names) if callee_names else 'none'}
- Called by: {', '.join(caller_names) if caller_names else 'none'}

Task: Analyze this function for potential bugs. Respond with JSON:
{{
  "category": "bug category",
  "line_start": <start line number>,
  "line_end": <end line number>,
  "reason": "explanation of potential bug"
}}

If no bugs found, respond with: {{"no_bugs": true}}
"""
        
        return prompt
    
    def _find_function_node(self, tree: ast.AST, symbol: Dict[str, Any]) -> Optional[ast.FunctionDef]:
        """Find AST node for function."""
        line_start = symbol.get('line_start', 0)
        name = symbol.get('name', '')
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name and abs(node.lineno - line_start) <= 10:
                    return node
        
        return None


def run_llm_reviewer_collector(
    repo_root: Path,
    index_path: Path,
    graph_path: Path,
    output_dir: Path
) -> List[Dict[str, Any]]:
    """Run LLM reviewer collector.
    
    Args:
        repo_root: Repository root
        index_path: Path to index.json
        graph_path: Path to graph.json
        output_dir: Output directory
        
    Returns:
        List of candidates
    """
    index_data = read_json(index_path)
    graph_data = read_json(graph_path)
    
    collector = LLMReviewerCollector(repo_root, index_data, graph_data)
    return collector.collect(output_dir)
