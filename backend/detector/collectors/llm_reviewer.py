"""LLM reviewer collector - TASK 4.5.

Reviews functions with branches/calls/returns for potential bugs.
"""

import ast
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from common.io import read_json, write_json, write_text
from detector.collectors import create_candidate
from llm.omniroute import call_omniroute, OmnirouteError

logger = logging.getLogger(__name__)


class LLMReviewerCollector:
    """TASK 4.5: Collector using LLM to review functions."""
    
    def __init__(
        self,
        repo_root: Path,
        index_data: Dict[str, Any],
        graph_data: Dict[str, Any],
        llm_enabled: bool = True,
        cache_dir: Optional[Path] = None,
        include_tests: bool = False
    ):
        """Initialize LLM reviewer collector.
        
        Args:
            repo_root: Repository root path
            index_data: Loaded index.json
            graph_data: Loaded graph.json
            llm_enabled: Whether LLM is enabled (default True)
            cache_dir: Cache directory for LLM responses (optional)
            include_tests: Whether to include test code (default False)
        """
        self.repo_root = repo_root
        self.index_data = index_data
        self.graph_data = graph_data
        self.llm_enabled = llm_enabled
        self.cache_dir = cache_dir
        self.include_tests = include_tests
        
        # Get model from environment
        self.model = os.getenv("OMNIROUTE_MODEL", "auto/coding")
        
        # Status counters
        self.llm_functions_selected = 0
        self.llm_cache_hits = 0
        self.llm_calls_made = 0
        self.llm_call_errors = 0
        self.llm_responses_valid = 0
        self.llm_responses_rejected = 0
        self.llm_candidates = 0
        
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
        # Check if LLM is enabled
        if not self.llm_enabled:
            logger.info("LLM disabled via flag, skipping LLM reviewer")
            return []
        
        logger.info("Running LLM reviewer collector...")
        
        # TASK 4.5.1: Select functions with branches, calls, or returns
        target_functions = self._select_target_functions()
        self.llm_functions_selected = len(target_functions)
        
        if not target_functions:
            logger.info("No functions selected for LLM review")
            return []
        
        logger.info(f"Selected {self.llm_functions_selected} functions for LLM review")
        
        candidates = []
        
        # Process each function sequentially
        for idx, symbol_id in enumerate(target_functions):
            candidate = self._review_function(symbol_id, idx, output_dir)
            if candidate:
                candidates.append(candidate)
                self.llm_candidates += 1
        
        logger.info(f"LLM reviewer produced {self.llm_candidates} candidates")
        logger.info(f"  Calls made: {self.llm_calls_made}, Cache hits: {self.llm_cache_hits}")
        logger.info(f"  Valid responses: {self.llm_responses_valid}, Rejected: {self.llm_responses_rejected}, Errors: {self.llm_call_errors}")
        
        return candidates
    
    def get_status_counters(self) -> Dict[str, int]:
        """Get status counters for status.json.
        
        Returns:
            Dict of counter names to values
        """
        return {
            "llm_functions_selected": self.llm_functions_selected,
            "llm_cache_hits": self.llm_cache_hits,
            "llm_calls_made": self.llm_calls_made,
            "llm_call_errors": self.llm_call_errors,
            "llm_responses_valid": self.llm_responses_valid,
            "llm_responses_rejected": self.llm_responses_rejected,
            "llm_candidates": self.llm_candidates,
        }
    
    def _select_target_functions(self) -> List[str]:
        """TASK 4.5.1: Select functions with branches, calls, or returns.
        
        Excludes test files and test functions unless include_tests is True.
        
        Returns:
            List of symbol IDs
        """
        targets = []
        excluded_files = set()
        
        for symbol_id, symbol in self.symbols.items():
            kind = symbol.get('kind')
            if kind not in ('function', 'method'):
                continue
            
            # Exclude test code unless include_tests is True
            if not self.include_tests:
                file_path = symbol.get('file', '')
                symbol_name = symbol.get('name', '')
                qualified_name = symbol.get('qualified_name', '')
                
                # Skip if file is under tests/
                if 'tests/' in file_path.replace('\\', '/'):
                    excluded_files.add(file_path)
                    continue
                
                # Skip if function/method name starts with test_
                if symbol_name.startswith('test_'):
                    continue
                
                # Skip test helper classes (RaisesContext, assert_raises, etc.)
                if 'RaisesContext' in qualified_name or 'assert_raises' in qualified_name:
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
        
        if excluded_files and not self.include_tests:
            logger.debug(f"Excluded {len(excluded_files)} test files from LLM review")
        
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
        
        # Build prompt
        prompt = self._build_prompt(symbol_id)
        if not prompt:
            return None
        
        # Check cache
        cache_key = self._cache_key(prompt)
        cached_response = self._get_cached(cache_key)
        
        if cached_response is not None:
            self.llm_cache_hits += 1
            response = cached_response
            logger.debug(f"Cache hit for {symbol_id}")
        else:
            # Call LLM with retry
            response = self._call_llm_with_retry(prompt)
            if response is None:
                self.llm_call_errors += 1
                return None
            
            self.llm_calls_made += 1
            
            # Cache the response
            if self.cache_dir:
                self._save_cache(cache_key, response)
        
        # Save raw response
        response_file = output_dir / f"llm_review_{idx}.txt"
        write_text(response_file, f"=== PROMPT ===\n{prompt}\n\n=== RESPONSE ===\n{response}")
        
        # Parse and validate response
        candidate, is_valid = self._parse_and_validate(response, symbol, idx)
        
        if is_valid:
            self.llm_responses_valid += 1
            if candidate:
                # Valid response with a bug candidate
                pass
            # else: Valid response with no_bugs: true (no candidate)
        else:
            self.llm_responses_rejected += 1
        
        return candidate
    
    def _cache_key(self, prompt: str) -> str:
        """Generate cache key for prompt.
        
        Args:
            prompt: Prompt text
            
        Returns:
            SHA256 hex digest
        """
        key_input = f"{self.model}:{prompt}"
        return hashlib.sha256(key_input.encode('utf-8')).hexdigest()
    
    def _get_cached(self, cache_key: str) -> Optional[str]:
        """Get cached response if available.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached response or None
        """
        if not self.cache_dir:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        
        try:
            data = read_json(cache_file)
            return data.get("response")
        except Exception as e:
            logger.warning(f"Failed to read cache {cache_key}: {e}")
            return None
    
    def _save_cache(self, cache_key: str, response: str):
        """Save response to cache.
        
        Args:
            cache_key: Cache key
            response: Response text
        """
        if not self.cache_dir:
            return
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            write_json(cache_file, {
                "model": self.model,
                "response": response,
                "cached_at": time.time(),
            })
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_key}: {e}")
    
    def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """Call LLM with exponential backoff retry.
        
        Args:
            prompt: Prompt text
            max_retries: Maximum number of retries (default 2)
            
        Returns:
            Response text or None on failure
        """
        timeout = 30.0
        
        for attempt in range(max_retries + 1):
            try:
                response = call_omniroute(
                    prompt=prompt,
                    temperature=0.0,
                    timeout=timeout,
                )
                return response
            except OmnirouteError as e:
                error_msg = str(e)
                
                # Don't retry on 4xx errors or parse failures
                if "HTTP 4" in error_msg or "non-JSON" in error_msg or "empty content" in error_msg:
                    logger.error(f"LLM call failed (non-retryable): {error_msg}")
                    return None
                
                # Don't retry if LLM is disabled
                if "LLM is disabled" in error_msg:
                    logger.info(f"LLM disabled: {error_msg}")
                    return None
                
                # Retry on network or 5xx errors
                if attempt < max_retries:
                    backoff = 2 ** attempt
                    logger.warning(f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {backoff}s: {error_msg}")
                    time.sleep(backoff)
                else:
                    logger.error(f"LLM call failed after {max_retries + 1} attempts: {error_msg}")
                    return None
        
        return None
    
    def _parse_and_validate(self, response: str, symbol: Dict[str, Any], idx: int) -> tuple[Optional[Dict[str, Any]], bool]:
        """Parse and validate LLM response.
        
        Args:
            response: Response text
            symbol: Symbol dict
            idx: Candidate index
            
        Returns:
            Tuple of (candidate dict or None, is_valid boolean)
            - (None, True) for valid no_bugs response
            - (candidate, True) for valid bug response
            - (None, False) for invalid response
        """
        # Try to parse JSON
        try:
            data = json.loads(response.strip())
        except json.JSONDecodeError:
            # Try to extract first JSON object from text
            start = response.find('{')
            end = response.rfind('}')
            if start >= 0 and end > start:
                try:
                    data = json.loads(response[start:end+1])
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse JSON from response (idx {idx})")
                    return (None, False)
            else:
                logger.warning(f"No JSON object found in response (idx {idx})")
                return (None, False)
        
        # Check for no_bugs response - this is valid with no candidate
        if data.get("no_bugs") is True:
            logger.debug(f"Function {symbol.get('qualified_name')} - no bugs reported")
            return (None, True)
        
        # Validate required fields
        category = data.get("category")
        line_start = data.get("line_start")
        line_end = data.get("line_end")
        reason = data.get("reason")
        
        if not isinstance(category, str) or not category.strip():
            logger.warning(f"Invalid or missing category (idx {idx})")
            return (None, False)
        
        if not isinstance(line_start, int) or not isinstance(line_end, int):
            logger.warning(f"Invalid line numbers (idx {idx}): start={line_start}, end={line_end}")
            return (None, False)
        
        if not isinstance(reason, str) or not reason.strip():
            logger.warning(f"Invalid or missing reason (idx {idx})")
            return (None, False)
        
        # Validate line range
        symbol_line_start = symbol.get('line_start', 1)
        symbol_line_end = symbol.get('line_end', 1)
        
        if line_start > line_end:
            logger.warning(f"line_start > line_end (idx {idx}): {line_start} > {line_end}")
            return (None, False)
        
        if line_start < symbol_line_start or line_end > symbol_line_end:
            logger.warning(f"Line range outside function bounds (idx {idx}): [{line_start}, {line_end}] not in [{symbol_line_start}, {symbol_line_end}]")
            return (None, False)
        
        # Create candidate
        candidate = create_candidate(
            candidate_id=f"llm_{idx}",
            source="llm",
            symbol=symbol.get('qualified_name', symbol.get('id', 'unknown')),
            file=symbol.get('file', ''),
            line_start=line_start,
            line_end=line_end,
            category=category,
            description=reason,
            evidence=[f"LLM analysis: {reason}"],
        )
        
        # Add raw response
        candidate['raw'] = data
        
        return (candidate, True)
    
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

Task: Analyze this function for potential bugs that are visible in the code. Do not report style issues.

Respond with JSON in one of these formats:

If you find a bug:
{{
  "category": "brief bug category",
  "line_start": <start line number>,
  "line_end": <end line number>,
  "reason": "explanation of the potential bug"
}}

If no bugs found:
{{"no_bugs": true}}
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
