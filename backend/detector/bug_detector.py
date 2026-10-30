"""Bug detector - TASK 4.

Orchestrates all collectors, verification, and grouping.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from common.io import read_json, write_json, ensure_dir
from detector.collectors.pytest_collector import run_pytest_collector
from detector.collectors.ruff_collector import run_ruff_collector
from detector.collectors.ast_heuristics import run_ast_heuristics_collector
from detector.collectors.llm_reviewer import LLMReviewerCollector
from detector.verifier import verify_candidates
from detector.grouper import group_candidates

logger = logging.getLogger(__name__)


class BugDetector:
    """TASK 4: Main bug detector orchestrating all stages."""
    
    def __init__(
        self,
        repo_root: Path,
        run_dir: Path,
        index_path: Path,
        graph_path: Path,
        llm_enabled: bool = True
    ):
        """Initialize bug detector.
        
        Args:
            repo_root: Repository root
            run_dir: Run directory for outputs
            index_path: Path to index.json
            graph_path: Path to graph.json
            llm_enabled: Whether LLM reviewer is enabled (default True)
        """
        self.repo_root = repo_root
        self.run_dir = run_dir
        self.index_path = index_path
        self.graph_path = graph_path
        self.llm_enabled = llm_enabled
        
        self.detector_dir = run_dir / 'detector'
        ensure_dir(self.detector_dir)
        
        # Cache directory for LLM responses (shared across runs for same repo)
        # Use parent of run_dir to share cache across runs
        cache_root = run_dir.parent / 'cache' / 'llm'
        self.llm_cache_dir = cache_root
        
        # Status counters
        self.status = {}
    
    def detect(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Run complete bug detection pipeline.
        
        Returns:
            Tuple of (bug_groups, bug_reports)
        """
        logger.info("="  * 60)
        logger.info("TASK 4: Bug Detection & Grouping")
        logger.info("=" * 60)
        
        # TASK 4.1: Start all collectors
        all_candidates = []
        collector_status = {}
        
        # Collector 1: Pytest
        try:
            logger.info("\nCollector 1: Pytest")
            pytest_candidates = run_pytest_collector(
                self.repo_root,
                self.index_path,
                self.graph_path,
                self.detector_dir
            )
            all_candidates.extend(pytest_candidates)
            collector_status['pytest'] = 'success'
            logger.info(f"  Pytest: {len(pytest_candidates)} candidates")
        except Exception as e:
            logger.error(f"  Pytest collector failed: {e}")
            collector_status['pytest'] = 'failed'
        
        # Collector 2: Ruff
        try:
            logger.info("\nCollector 2: Ruff")
            ruff_candidates = run_ruff_collector(
                self.repo_root,
                self.index_path,
                self.detector_dir
            )
            all_candidates.extend(ruff_candidates)
            collector_status['ruff'] = 'success' if ruff_candidates is not None else 'not_available'
            logger.info(f"  Ruff: {len(ruff_candidates) if ruff_candidates else 0} candidates")
        except Exception as e:
            logger.error(f"  Ruff collector failed: {e}")
            collector_status['ruff'] = 'failed'
        
        # Collector 3: AST Heuristics
        try:
            logger.info("\nCollector 3: AST Heuristics")
            heuristic_candidates = run_ast_heuristics_collector(
                self.repo_root,
                self.index_path,
                self.detector_dir
            )
            all_candidates.extend(heuristic_candidates)
            collector_status['ast_heuristics'] = 'success'
            logger.info(f"  AST Heuristics: {len(heuristic_candidates)} candidates")
        except Exception as e:
            logger.error(f"  AST heuristics collector failed: {e}")
            collector_status['ast_heuristics'] = 'failed'
        
        # Collector 4: LLM Reviewer
        try:
            logger.info("\nCollector 4: LLM Reviewer")
            
            # Load index and graph
            index_data = read_json(self.index_path)
            graph_data = read_json(self.graph_path)
            
            # Create collector
            llm_collector = LLMReviewerCollector(
                repo_root=self.repo_root,
                index_data=index_data,
                graph_data=graph_data,
                llm_enabled=self.llm_enabled,
                cache_dir=self.llm_cache_dir,
                include_tests=False  # Exclude test code by default
            )
            
            # Run collector
            llm_candidates = llm_collector.collect(self.detector_dir)
            all_candidates.extend(llm_candidates)
            
            # Get status counters
            self.status.update(llm_collector.get_status_counters())
            
            collector_status['llm_reviewer'] = 'success'
            logger.info(f"  LLM Reviewer: {len(llm_candidates)} candidates")
        except Exception as e:
            logger.error(f"  LLM reviewer collector failed: {e}", exc_info=True)
            collector_status['llm_reviewer'] = 'failed'
        
        # TASK 4.6: Candidate pool
        logger.info(f"\nTotal candidates from all collectors: {len(all_candidates)}")
        
        if not all_candidates:
            logger.info("No candidates found, skipping verification and grouping")
            return [], []
        
        # TASK 4.7: Verify candidates
        logger.info("\nVerifying candidates...")
        verified_candidates = verify_candidates(
            all_candidates,
            self.repo_root,
            self.run_dir
        )
        
        confirmed_count = sum(1 for c in verified_candidates if c.get('verified') == 'confirmed')
        unconfirmed_count = len(verified_candidates) - confirmed_count
        logger.info(f"  Confirmed: {confirmed_count}")
        logger.info(f"  Unconfirmed: {unconfirmed_count}")
        
        # TASK 4.8: Group candidates
        logger.info("\nGrouping candidates...")
        bug_groups_path = self.run_dir / 'bug_groups.json'
        bug_report_path = self.run_dir / 'bug_report.json'
        
        groups, reports = group_candidates(
            verified_candidates,
            bug_groups_path,
            bug_report_path
        )
        
        verified_groups = sum(1 for g in groups if g.get('verified'))
        unverified_groups = len(groups) - verified_groups
        logger.info(f"  Total groups: {len(groups)}")
        logger.info(f"  Verified groups: {verified_groups}")
        logger.info(f"  Unverified groups: {unverified_groups}")
        
        # Write status.json
        status_path = self.run_dir / 'status.json'
        write_json(status_path, self.status)
        logger.info(f"\nStatus written to {status_path}")
        
        logger.info("\nBug detection complete")
        logger.info("=" * 60)
        
        return groups, reports
    
    def review_single_function(self, qualified_name: str) -> Optional[Dict[str, Any]]:
        """Review a single function with LLM (for testing).
        
        Args:
            qualified_name: Qualified function name to review
            
        Returns:
            Candidate dict or None
        """
        logger.info(f"Reviewing single function: {qualified_name}")
        
        # Load index and graph
        index_data = read_json(self.index_path)
        graph_data = read_json(self.graph_path)
        
        # Find the symbol
        symbol_id = None
        for sym in index_data.get('symbols', []):
            if sym.get('qualified_name') == qualified_name:
                symbol_id = sym.get('id', sym.get('symbol_id'))
                break
        
        if not symbol_id:
            logger.error(f"Function not found: {qualified_name}")
            return None
        
        logger.info(f"Found symbol: {symbol_id}")
        
        # Create collector
        llm_collector = LLMReviewerCollector(
            repo_root=self.repo_root,
            index_data=index_data,
            graph_data=graph_data,
            llm_enabled=self.llm_enabled,
            cache_dir=self.llm_cache_dir
        )
        
        # Override function selection to single function
        llm_collector.llm_functions_selected = 1
        
        # Review the function
        candidate = llm_collector._review_function(symbol_id, 0, self.detector_dir)
        
        # Get status
        self.status.update(llm_collector.get_status_counters())
        
        # Write status
        status_path = self.run_dir / 'status.json'
        write_json(status_path, self.status)
        
        return candidate


def run_bug_detector(
    repo_root: Path,
    run_dir: Path,
    index_path: Path,
    graph_path: Path,
    llm_enabled: bool = True
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Run bug detector.
    
    Args:
        repo_root: Repository root
        run_dir: Run directory
        index_path: Path to index.json
        graph_path: Path to graph.json
        llm_enabled: Whether LLM reviewer is enabled (default True)
        
    Returns:
        Tuple of (bug_groups, bug_reports)
    """
    detector = BugDetector(repo_root, run_dir, index_path, graph_path, llm_enabled)
    return detector.detect()
