"""Pytest collector - TASK 4.2.

Runs pytest with JSON report, extracts failures, maps to suspect symbols.
Uses LLM-assisted symbol resolution when heuristics fail.
"""

import ast
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from common.io import read_json, write_json
from common.pyresolve import ImportResolver, find_function
from detector.collectors import create_candidate

logger = logging.getLogger(__name__)


class PytestCollector:
    """TASK 4.2: Collector for pytest failures with LLM-assisted symbol resolution."""
    
    def __init__(self, repo_root: Path, index_data: Dict[str, Any], graph_data: Dict[str, Any]):
        """Initialize pytest collector.
        
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
            sym_id = sym.get('id', sym.get('symbol_id'))  # FIX 4: Support both
            if sym_id:
                self.symbols[sym_id] = sym
        
        # Build file to symbols index
        self.file_to_symbols = {}
        for symbol_id, symbol in self.symbols.items():
            file = symbol.get('file', '')
            if file not in self.file_to_symbols:
                self.file_to_symbols[file] = []
            self.file_to_symbols[file].append(symbol_id)
        
        # Initialize import resolver
        import_roots = index_data.get('import_roots', [])
        self.import_resolver = ImportResolver(repo_root, import_roots)
        
        # LLM client config (using omniroute pattern)
        self.llm_enabled = os.getenv('LLM_DISABLED') != '1'
        self.omniroute_base_url = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1").rstrip("/")
        self.omniroute_api_key = os.getenv("OMNIROUTE_API_KEY")
        self.omniroute_model = os.getenv("OMNIROUTE_MODEL", "auto/coding")
    
    def collect(self, output_dir: Path) -> List[Dict[str, Any]]:
        """TASK 4.2: Run pytest and collect failure candidates.
        
        Returns:
            List of candidate dicts
        """
        logger.info("Running pytest collector...")
        
        # TASK 4.2.1: Run pytest with JSON report
        pytest_output = self._run_pytest(output_dir)
        if not pytest_output:
            logger.warning("Pytest run failed or no output")
            return []
        
        # TASK 4.2.2: Check for failures
        tests = pytest_output.get('tests', [])
        failures = [t for t in tests if t.get('outcome') == 'failed']
        
        if not failures:
            logger.info("No test failures found")
            return []
        
        logger.info(f"Found {len(failures)} failed tests")
        
        # Process each failure
        candidates = []
        for idx, failure in enumerate(failures):
            candidate = self._process_failure(failure, idx)
            if candidate:
                candidates.append(candidate)
        
        logger.info(f"Pytest collector produced {len(candidates)} candidates")
        return candidates
    
    def _run_pytest(self, output_dir: Path) -> Optional[Dict[str, Any]]:
        """TASK 4.2.1: Run pytest with JSON report.
        
        Args:
            output_dir: Directory for output files
            
        Returns:
            Parsed JSON report or None
        """
        json_report = output_dir / 'pytest_report.json'
        
        try:
            cmd = [
                'pytest',
                '--json-report',
                f'--json-report-file={str(json_report.absolute())}',
                '--tb=long',
                '-v'
            ]
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )
            
            # Log output for debugging
            if result.stderr:
                logger.debug(f"Pytest stderr: {result.stderr[:500]}")
            if result.stdout:
                logger.debug(f"Pytest stdout: {result.stdout[:500]}")
            
            # Pytest returns non-zero on failures, which is expected
            if json_report.exists():
                return read_json(json_report)
            else:
                logger.warning("Pytest JSON report not found")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Pytest timed out")
            return None
        except Exception as e:
            logger.error(f"Error running pytest: {e}")
            return None
    
    def _process_failure(self, failure: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
        """Process a single test failure.
        
        Args:
            failure: Test failure dict from pytest JSON
            idx: Failure index
            
        Returns:
            Candidate dict or None
        """
        nodeid = failure.get('nodeid', '')
        test_file = failure.get('file', '')
        test_name = failure.get('name', '')
        
        # Parse nodeid to extract file if needed
        if not test_file and '::' in nodeid:
            test_file = nodeid.split('::')[0]
        
        # Parse nodeid to extract test name if needed
        if not test_name and '::' in nodeid:
            test_name = nodeid.split('::')[-1]
        
        if not test_file or not test_name:
            logger.debug(f"Could not extract test file/name from {nodeid}")
            return None
        
        logger.debug(f"Processing failure: {test_file}::{test_name}")
        
        # TASK 4.2.3: Extract traceback, test file, failing line
        call_info = failure.get('call', {})
        traceback = call_info.get('traceback', [])
        longrepr = call_info.get('longrepr', '')
        
        if not traceback:
            return None
        
        # Get last frame (actual failure point)
        last_frame = traceback[-1] if traceback else {}
        failing_file = last_frame.get('path', '')
        failing_line = last_frame.get('lineno', 0)
        
        # TASK 4.2.4: Find calls in test body
        suspect_symbol = self._find_suspect_symbol(test_file, test_name, traceback, failing_file, failing_line)
        
        if not suspect_symbol:
            logger.debug(f"Could not find suspect symbol for {nodeid}")
            return None
        
        # Skip if suspect symbol is the test itself
        symbol_info = self.symbols.get(suspect_symbol, {})
        if 'test' in symbol_info.get('file', '').lower():
            logger.debug(f"Skipping test symbol: {suspect_symbol}")
            return None
        
        # TASK 4.2.6: Create pytest candidate
        candidate = create_candidate(
            candidate_id=f"pytest_{idx}",
            source='pytest',
            file=symbol_info.get('file', failing_file),
            symbol=symbol_info.get('qualified_name', suspect_symbol),
            line_start=symbol_info.get('line_start', failing_line),
            line_end=symbol_info.get('line_end', failing_line),
            category='test_failure',
            description=f"Test {test_name} failed",
            evidence=[
                f"Test: {nodeid}",
                f"Failure message: {longrepr[:200]}" if longrepr else ""
            ],
            test_ids=[nodeid],
            raw=failure
        )
        
        return candidate
    
    def _find_suspect_symbol(
        self, 
        test_file: str, 
        test_name: str, 
        traceback: List[Dict], 
        failing_file: str, 
        failing_line: int
    ) -> Optional[str]:
        """TASK 4.2.4-4.2.5: Find suspect symbol from test calls and traceback.
        
        Uses multiple strategies:
        1. Heuristic: Find symbol at traceback locations (non-test files)
        2. Heuristic: Parse test calls and match with imports
        3. LLM: Analyze full traceback and test code
        
        Args:
            test_file: Test file path
            test_name: Test function name
            traceback: Traceback frames
            failing_file: File where failure occurred
            failing_line: Line where failure occurred
            
        Returns:
            Symbol ID or None
        """
        # Strategy 1: Check traceback frames for indexed symbols (non-test files)
        for frame in reversed(traceback):
            frame_file = frame.get('path', '')
            frame_line = frame.get('lineno', 0)
            
            # Skip test files
            if 'test' in str(frame_file).lower():
                continue
            
            # Try to find symbol at this location
            symbol_id = self._find_symbol_at_location(frame_file, frame_line)
            if symbol_id:
                logger.info(f"Found suspect symbol via traceback: {symbol_id}")
                return symbol_id
        
        logger.debug(f"Strategy 1 failed: no symbols in traceback")
        
        # Strategy 2: Parse test file and extract function calls
        symbol_id = self._find_symbol_from_test_calls(test_file, test_name, traceback)
        if symbol_id:
            logger.info(f"Found suspect symbol via test calls: {symbol_id}")
            return symbol_id
        
        logger.debug(f"Strategy 2 failed: could not resolve test calls")
        
        # Strategy 3: Use LLM to analyze traceback
        if self.llm_enabled and self.omniroute_api_key:
            symbol_id = self._find_symbol_via_llm(
                test_file, test_name, traceback, failing_file, failing_line
            )
            if symbol_id:
                logger.info(f"Found suspect symbol via LLM: {symbol_id}")
                return symbol_id
        
        logger.debug(f"Strategy 3 failed or disabled")
        
        # Fallback: Symbol at failing line
        symbol_id = self._find_symbol_at_location(failing_file, failing_line)
        if symbol_id:
            logger.debug(f"Using fallback symbol at failing line: {symbol_id}")
        return symbol_id
    
    def _find_symbol_from_test_calls(
        self,
        test_file: str,
        test_name: str,
        traceback: List[Dict]
    ) -> Optional[str]:
        """Extract function calls from test and match with imports.
        
        Args:
            test_file: Test file path
            test_name: Test function name
            traceback: Traceback frames
            
        Returns:
            Symbol ID or None
        """
        test_path = self.repo_root / test_file
        logger.debug(f"Analyzing test: {test_file}/{test_name}")
        logger.debug(f"Test path: {test_path}, exists: {test_path.exists()}")
        
        if not test_path.exists():
            logger.debug(f"Test file not found: {test_path}")
            return None
        
        try:
            with open(test_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
            logger.debug(f"Successfully parsed test file")
        except Exception as e:
            logger.debug(f"Failed to parse test file: {e}")
            return None
        
        # Extract imports
        imports = self.import_resolver.extract_imports_from_file(test_path)
        logger.debug(f"Extracted {len(imports)} imports from test file")
        
        # Build import map: name -> resolved file
        import_map = {}
        for imp in imports:
            resolved_file = imp.get('resolved_file')
            module = imp.get('module', '')
            names = imp.get('names', [])
            logger.debug(f"Import: module={module}, resolved={resolved_file}, names={names}")
            
            # If not resolved, try manual resolution with import roots
            if not resolved_file and module:
                import_roots = self.index_data.get('import_roots', [])
                logger.debug(f"Trying manual resolution for {module}, import_roots={import_roots}")
                for root in import_roots:
                    # Try module as a file
                    candidate = f"{root}/{module}.py"
                    candidate_path = self.repo_root / candidate
                    logger.debug(f"Trying {candidate_path}, exists: {candidate_path.exists()}")
                    if candidate_path.exists():
                        resolved_file = candidate.replace('\\', '/')
                        logger.debug(f"Manually resolved {module} to {resolved_file}")
                        break
            
            if resolved_file:
                for name_info in names:
                    name = name_info.get('asname') or name_info.get('name')
                    if name and name != '*':
                        import_map[name] = resolved_file
        
        logger.debug(f"Import map: {import_map}")
        
        # Find test function and extract calls
        test_func_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == test_name:
                    test_func_node = node
                    break
        
        if not test_func_node:
            logger.debug(f"Could not find test function {test_name}")
            return None
        
        logger.debug(f"Found test function {test_name}, analyzing calls...")
        
        # Analyze calls in test to find which methods are being tested
        # Priority: Look for service/class instantiation followed by method calls
        class_instances = {}  # var_name -> class_name
        method_calls = []  # (class_name, method_name, line)
        
        for node in ast.walk(test_func_node):
            # Track variable assignments to class instantiations
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                        if isinstance(node.value.func, ast.Name):
                            class_instances[target.id] = node.value.func.id
            
            # Track method calls on instances
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        obj_name = node.func.value.id
                        method_name = node.func.attr
                        
                        # Check if this is a known instance
                        if obj_name in class_instances:
                            class_name = class_instances[obj_name]
                            method_calls.append((class_name, method_name, node.lineno))
        
        logger.debug(f"Found {len(class_instances)} class instances: {list(class_instances.keys())}")
        logger.debug(f"Found {len(method_calls)} method calls: {method_calls}")
        
        # Try to resolve method calls to symbols
        for class_name, method_name, line in method_calls:
            # Find file for this class
            class_file = import_map.get(class_name)
            if not class_file:
                logger.debug(f"Could not find import for class {class_name}")
                continue
            
            logger.debug(f"Analyzing {class_name}.{method_name} in {class_file}")
            
            # Look for method in this file
            qualified_name = f"{class_name}.{method_name}"
            symbol_id = f"{class_file}::{qualified_name}"
            
            if symbol_id in self.symbols:
                logger.info(f"Found direct match: {symbol_id}")
                
                # Try to narrow down to internal method using LLM
                if self.llm_enabled and self.omniroute_api_key:
                    internal_symbol = self._find_internal_method_via_llm(
                        class_file, class_name, method_name, test_file, test_name, traceback
                    )
                    if internal_symbol:
                        logger.info(f"Refined to internal method via LLM: {internal_symbol}")
                        return internal_symbol
                
                # Fallback: Also check for internal methods via AST
                internal_symbol = self._find_internal_method_calls(class_file, class_name, method_name)
                if internal_symbol:
                    logger.info(f"Found internal method via AST: {internal_symbol}")
                    return internal_symbol
                
                # Return the direct match if no internal method found
                return symbol_id
        
        # Fallback: Try generic call resolution
        for call_node in ast.walk(test_func_node):
            if isinstance(call_node, ast.Call):
                symbol_id = self._resolve_call_to_symbol(call_node, import_map, traceback)
                if symbol_id:
                    return symbol_id
        
        return None
    
    def _find_internal_method_via_llm(
        self,
        file: str,
        class_name: str,
        method_name: str,
        test_file: str,
        test_name: str,
        traceback: List[Dict]
    ) -> Optional[str]:
        """Use LLM to identify which internal method is likely buggy.
        
        Args:
            file: Source file path
            class_name: Class name
            method_name: Method name that test calls directly
            test_file: Test file path
            test_name: Test function name
            traceback: Traceback frames
            
        Returns:
            Symbol ID of internal method or None
        """
        try:
            # Read the method source code
            file_path = self.repo_root / file
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            # Parse to find the method
            tree = ast.parse(source)
            method_source = None
            method_start = None
            method_end = None
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if item.name == method_name:
                                method_start = item.lineno
                                method_end = item.end_lineno
                                # Extract source lines
                                lines = source.split('\n')
                                method_source = '\n'.join(lines[method_start-1:method_end])
                                break
                    break
            
            if not method_source:
                return None
            
            # Read the test source
            test_path = self.repo_root / test_file
            test_source = None
            if test_path.exists():
                with open(test_path, 'r', encoding='utf-8') as f:
                    test_source_full = f.read()
                test_tree = ast.parse(test_source_full)
                for node in ast.walk(test_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == test_name:
                            test_start = node.lineno
                            test_end = node.end_lineno
                            lines = test_source_full.split('\n')
                            test_source = '\n'.join(lines[test_start-1:test_end])
                            break
            
            # Build prompt
            prompt = self._build_internal_method_prompt(
                class_name, method_name, method_source, test_name, test_source, file
            )
            
            # Call LLM
            response = self._call_omniroute(prompt)
            
            # Parse response - expect JSON with internal_method field
            result = json.loads(response.strip())
            internal_method = result.get('internal_method')
            
            if internal_method and internal_method != method_name:
                # Build symbol ID
                internal_qual = f"{class_name}.{internal_method}"
                internal_symbol_id = f"{file}::{internal_qual}"
                
                if internal_symbol_id in self.symbols:
                    return internal_symbol_id
            
        except Exception as e:
            logger.debug(f"LLM internal method detection failed: {e}")
        
        return None
    
    def _build_internal_method_prompt(
        self,
        class_name: str,
        method_name: str,
        method_source: str,
        test_name: str,
        test_source: Optional[str],
        file: str
    ) -> str:
        """Build prompt for LLM to identify buggy internal method.
        
        Args:
            class_name: Class name
            method_name: Method name
            method_source: Source code of the method
            test_name: Test function name
            test_source: Source code of the test
            file: Source file path
            
        Returns:
            Prompt string
        """
        lines = [
            "# Internal Method Bug Detection",
            "",
            "A test is failing. The test directly calls a method, but the bug might be in an internal method (helper/validation method) that it calls.",
            "",
            "## Test Information",
            f"Test: {test_name}",
        ]
        
        if test_source:
            lines.extend([
                "",
                "```python",
                test_source,
                "```",
            ])
        
        lines.extend([
            "",
            f"## Method Being Tested: {class_name}.{method_name}",
            f"File: {file}",
            "",
            "```python",
            method_source,
            "```",
            "",
            "## Available Internal Methods",
            ""
        ])
        
        # List all methods in this class
        if file in self.file_to_symbols:
            for symbol_id in self.file_to_symbols[file]:
                symbol = self.symbols[symbol_id]
                qual_name = symbol.get('qualified_name', '')
                if qual_name.startswith(f"{class_name}."):
                    method_part = qual_name[len(class_name)+1:]
                    lines.append(f"- {method_part}: lines {symbol.get('line_start')}-{symbol.get('line_end')}")
        
        lines.extend([
            "",
            "## Task",
            f"Based on the test and the method body, identify which internal method (if any) is most likely to contain the bug.",
            f"If the bug is likely in {method_name} itself (not in an internal method), return null.",
            "",
            "Return JSON with:",
            '{"internal_method": "method_name"}  // or null if bug is in the tested method itself',
            "",
            "Return ONLY the JSON, no explanation.",
            ""
        ])
        
        return '\n'.join(lines)
    
    def _find_internal_method_calls(
        self,
        file: str,
        class_name: str,
        method_name: str
    ) -> Optional[str]:
        """Find internal methods called by a given method.
        
        For example, if create_user calls _validate_user, find _validate_user.
        
        Args:
            file: File path
            class_name: Class name
            method_name: Method name
            
        Returns:
            Symbol ID of internal method or None
        """
        file_path = self.repo_root / file
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
        except:
            return None
        
        # Find the class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Find the method
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == method_name:
                            # Look for calls to self._* methods
                            for call_node in ast.walk(item):
                                if isinstance(call_node, ast.Call):
                                    if isinstance(call_node.func, ast.Attribute):
                                        if isinstance(call_node.func.value, ast.Name):
                                            if call_node.func.value.id == 'self':
                                                internal_method = call_node.func.attr
                                                # Check if this internal method exists as a symbol
                                                internal_qual = f"{class_name}.{internal_method}"
                                                internal_symbol_id = f"{file}::{internal_qual}"
                                                
                                                if internal_symbol_id in self.symbols:
                                                    logger.debug(f"Found internal method: {internal_symbol_id}")
                                                    return internal_symbol_id
        
        return None
    
    def _resolve_call_to_symbol(
        self,
        call_node: ast.Call,
        import_map: Dict[str, str],
        traceback: List[Dict]
    ) -> Optional[str]:
        """Resolve a function call AST node to a symbol ID.
        
        Args:
            call_node: AST Call node
            import_map: Map of imported names to files
            traceback: Traceback frames
            
        Returns:
            Symbol ID or None
        """
        # Extract function name and object
        func_name = None
        obj_name = None
        
        if isinstance(call_node.func, ast.Name):
            # Simple call: func()
            func_name = call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            # Method call: obj.method()
            func_name = call_node.func.attr
            if isinstance(call_node.func.value, ast.Name):
                obj_name = call_node.func.value.id
        
        if not func_name:
            return None
        
        # Try to find which file this call corresponds to
        target_file = None
        
        # If we have an object name, check imports
        if obj_name and obj_name in import_map:
            target_file = import_map[obj_name]
        elif func_name in import_map:
            target_file = import_map[func_name]
        
        # Check if target file appears in traceback
        if target_file:
            for frame in traceback:
                frame_file = frame.get('path', '')
                try:
                    frame_path = Path(frame_file)
                    if frame_path.is_absolute():
                        frame_file = str(frame_path.relative_to(self.repo_root))
                    frame_file = frame_file.replace('\\', '/')
                except:
                    pass
                
                if frame_file == target_file:
                    # Found matching file in traceback
                    # Try to find symbol with this name
                    if target_file in self.file_to_symbols:
                        for symbol_id in self.file_to_symbols[target_file]:
                            symbol = self.symbols[symbol_id]
                            qual_name = symbol.get('qualified_name', '')
                            
                            # Match on function name
                            if func_name in qual_name:
                                return symbol_id
        
        return None
    
    def _find_symbol_via_llm(
        self,
        test_file: str,
        test_name: str,
        traceback: List[Dict],
        failing_file: str,
        failing_line: int
    ) -> Optional[str]:
        """Use LLM to identify suspect symbol from traceback.
        
        Args:
            test_file: Test file path
            test_name: Test function name
            traceback: Traceback frames
            failing_file: File where failure occurred
            failing_line: Line where failure occurred
            
        Returns:
            Symbol ID or None
        """
        try:
            # Build prompt with traceback and available symbols
            prompt = self._build_symbol_resolution_prompt(
                test_file, test_name, traceback, failing_file, failing_line
            )
            
            # Call omniroute
            response = self._call_omniroute(prompt)
            
            # Parse response
            result = json.loads(response.strip())
            symbol_id = result.get('symbol_id')
            
            if symbol_id and symbol_id in self.symbols:
                return symbol_id
                
        except Exception as e:
            logger.debug(f"LLM symbol resolution failed: {e}")
        
        return None
    
    def _build_symbol_resolution_prompt(
        self,
        test_file: str,
        test_name: str,
        traceback: List[Dict],
        failing_file: str,
        failing_line: int
    ) -> str:
        """Build prompt for LLM symbol resolution.
        
        Args:
            test_file: Test file path
            test_name: Test function name
            traceback: Traceback frames
            failing_file: File where failure occurred
            failing_line: Line where failure occurred
            
        Returns:
            Prompt string
        """
        lines = [
            "# Symbol Resolution Task",
            "",
            "Identify the suspect symbol (function/method) that likely contains the bug.",
            "",
            "## Test Information",
            f"Test file: {test_file}",
            f"Test function: {test_name}",
            "",
            "## Traceback",
        ]
        
        for i, frame in enumerate(traceback):
            frame_file = frame.get('path', 'unknown')
            frame_line = frame.get('lineno', 0)
            frame_message = frame.get('message', '')
            
            lines.append(f"\nFrame {i}:")
            lines.append(f"  File: {frame_file}")
            lines.append(f"  Line: {frame_line}")
            if frame_message:
                lines.append(f"  Message: {frame_message}")
        
        lines.extend([
            "",
            "## Available Symbols (indexed)",
            ""
        ])
        
        # Add symbols from failing file and related files
        relevant_files = {failing_file}
        for frame in traceback:
            frame_file = frame.get('path', '')
            if frame_file and 'test' not in frame_file.lower():
                relevant_files.add(frame_file)
        
        for file in relevant_files:
            # Normalize file path
            try:
                file_path = Path(file)
                if file_path.is_absolute():
                    file = str(file_path.relative_to(self.repo_root))
                file = file.replace('\\', '/')
            except:
                pass
            
            if file in self.file_to_symbols:
                lines.append(f"\n### {file}")
                for symbol_id in self.file_to_symbols[file]:
                    symbol = self.symbols[symbol_id]
                    lines.append(f"- {symbol_id}: {symbol.get('qualified_name')} (lines {symbol.get('line_start')}-{symbol.get('line_end')})")
        
        lines.extend([
            "",
            "## Task",
            "Return JSON with the symbol_id of the most likely buggy function.",
            "Return only the JSON, no explanation.",
            "",
            "Format:",
            '{"symbol_id": "path/to/file.py::qualified_name"}',
            ""
        ])
        
        return '\n'.join(lines)
    
    def _call_omniroute(self, prompt: str, timeout: float = 30.0) -> str:
        """Call omniroute API.
        
        Args:
            prompt: Prompt string
            timeout: Request timeout in seconds
            
        Returns:
            Response content string
        """
        payload = {
            "model": self.omniroute_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }
        
        request = Request(
            f"{self.omniroute_base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.omniroute_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        
        content = body["choices"][0]["message"]["content"]
        
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        
        return content
    
    def _find_symbol_at_location(self, file: str, line: int) -> Optional[str]:
        """Find symbol at a given file and line.
        
        Args:
            file: File path (may be absolute or relative)
            line: Line number
            
        Returns:
            Symbol ID or None
        """
        # Normalize file path
        try:
            file_path = Path(file)
            if file_path.is_absolute():
                file = str(file_path.relative_to(self.repo_root))
            file = file.replace('\\', '/')
        except Exception as e:
            logger.debug(f"Could not normalize path {file}: {e}")
            # Try as-is if normalization fails
            pass
        
        # Find symbol containing this line
        best_match = None
        best_size = float('inf')
        
        for symbol_id, symbol in self.symbols.items():
            sym_file = symbol.get('file', '')
            
            # Try both normalized and original file
            if sym_file != file:
                continue
            
            line_start = symbol.get('line_start', 0)
            line_end = symbol.get('line_end', 0)
            
            if line_start <= line <= line_end:
                # Prefer smaller (more specific) symbols
                size = line_end - line_start
                if size < best_size:
                    best_match = symbol_id
                    best_size = size
        
        # If no match, also try matching by qualified name parts
        if not best_match and line > 0:
            # Extract potential function name from traceback context
            # This helps when file paths don't match perfectly
            for symbol_id, symbol in self.symbols.items():
                sym_file = symbol.get('file', '')
                # Check if filenames match (ignoring directory differences)
                if Path(sym_file).name == Path(file).name:
                    line_start = symbol.get('line_start', 0)
                    line_end = symbol.get('line_end', 0)
                    
                    if line_start <= line <= line_end:
                        size = line_end - line_start
                        if size < best_size:
                            best_match = symbol_id
                            best_size = size
        
        return best_match


def run_pytest_collector(
    repo_root: Path,
    index_path: Path,
    graph_path: Path,
    output_dir: Path
) -> List[Dict[str, Any]]:
    """Run pytest collector.
    
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
    
    collector = PytestCollector(repo_root, index_data, graph_data)
    return collector.collect(output_dir)
