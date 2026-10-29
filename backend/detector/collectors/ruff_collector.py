"""Ruff collector - TASK 4.3.

Runs ruff static analysis and maps findings to symbols.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from common.io import read_json
from detector.collectors import create_candidate

logger = logging.getLogger(__name__)


class RuffCollector:
    """TASK 4.3: Collector for ruff static analysis findings."""
    
    def __init__(self, repo_root: Path, index_data: Dict[str, Any]):
        """Initialize ruff collector.
        
        Args:
            repo_root: Repository root path
            index_data: Loaded index.json
        """
        self.repo_root = repo_root
        self.index_data = index_data
        
        # Build symbol lookup by file and line
        self.symbols = {}
        symbols_list = index_data.get('symbols', [])
        for sym in symbols_list:
            sym_id = sym.get('id', sym.get('symbol_id'))
            self.symbols[sym_id] = sym
    
    def collect(self, output_dir: Path) -> List[Dict[str, Any]]:
        """TASK 4.3: Run ruff and collect finding candidates.
        
        Returns:
            List of candidate dicts
        """
        logger.info("Running ruff collector...")
        
        # TASK 4.3.1: Run ruff with JSON output
        findings = self._run_ruff()
        if findings is None:
            logger.warning("Ruff not available or failed")
            return []
        
        if not findings:
            logger.info("No ruff findings")
            return []
        
        logger.info(f"Found {len(findings)} ruff findings")
        
        # Process each finding
        candidates = []
        for idx, finding in enumerate(findings):
            candidate = self._process_finding(finding, idx)
            if candidate:
                candidates.append(candidate)
        
        logger.info(f"Ruff collector produced {len(candidates)} candidates")
        return candidates
    
    def _run_ruff(self) -> Optional[List[Dict[str, Any]]]:
        """TASK 4.3.1: Run ruff check with JSON output.
        
        Returns:
            List of finding dicts or None if ruff not available
        """
        try:
            cmd = ['ruff', 'check', '.', '--output-format', 'json']
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Ruff returns non-zero when it finds issues
            if result.stdout:
                findings = json.loads(result.stdout)
                return findings if isinstance(findings, list) else []
            else:
                return []
                
        except FileNotFoundError:
            logger.info("Ruff not installed, skipping")
            return None
        except subprocess.TimeoutExpired:
            logger.error("Ruff timed out")
            return None
        except Exception as e:
            logger.error(f"Error running ruff: {e}")
            return None
    
    def _process_finding(self, finding: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
        """Process a single ruff finding.
        
        TASK 4.3.2: Map finding line to enclosing symbol.
        
        Args:
            finding: Ruff finding dict
            idx: Finding index
            
        Returns:
            Candidate dict or None
        """
        filename = finding.get('filename', '')
        location = finding.get('location', {})
        line = location.get('row', 0)
        code = finding.get('code', '')
        message = finding.get('message', '')
        
        # Normalize file path
        try:
            file_path = Path(filename)
            if file_path.is_absolute():
                filename = str(file_path.relative_to(self.repo_root))
            filename = filename.replace('\\', '/')
        except:
            pass
        
        # TASK 4.3.2: Find enclosing symbol
        enclosing_symbol = self._find_enclosing_symbol(filename, line)
        
        if not enclosing_symbol:
            # Use module symbol as fallback
            module_id = f"{filename}::<module>"
            if module_id in self.symbols:
                enclosing_symbol = module_id
            else:
                logger.debug(f"Could not find symbol for ruff finding in {filename}:{line}")
                return None
        
        symbol_info = self.symbols[enclosing_symbol]
        
        # TASK 4.3.3: Create ruff candidate
        candidate = create_candidate(
            candidate_id=f"ruff_{idx}",
            source='ruff',
            file=symbol_info.get('file', filename),
            symbol=symbol_info.get('qualified_name', enclosing_symbol),
            line_start=symbol_info.get('line_start', line),
            line_end=symbol_info.get('line_end', line),
            category=f"ruff_{code}",
            description=f"Ruff {code}: {message}",
            evidence=[
                f"Rule: {code}",
                f"Line {line}: {message}"
            ],
            raw=finding
        )
        
        return candidate
    
    def _find_enclosing_symbol(self, file: str, line: int) -> Optional[str]:
        """Find symbol enclosing a given line.
        
        Args:
            file: File path
            line: Line number
            
        Returns:
            Symbol ID or None
        """
        best_match = None
        best_size = float('inf')
        
        for symbol_id, symbol in self.symbols.items():
            if symbol.get('file') != file:
                continue
            
            # Skip module symbols in first pass
            if symbol.get('kind') == 'module':
                continue
            
            line_start = symbol.get('line_start', 0)
            line_end = symbol.get('line_end', 0)
            
            if line_start <= line <= line_end:
                size = line_end - line_start
                if size < best_size:
                    best_match = symbol_id
                    best_size = size
        
        return best_match


def run_ruff_collector(
    repo_root: Path,
    index_path: Path,
    output_dir: Path
) -> List[Dict[str, Any]]:
    """Run ruff collector.
    
    Args:
        repo_root: Repository root
        index_path: Path to index.json
        output_dir: Output directory
        
    Returns:
        List of candidates
    """
    index_data = read_json(index_path)
    
    collector = RuffCollector(repo_root, index_data)
    return collector.collect(output_dir)
