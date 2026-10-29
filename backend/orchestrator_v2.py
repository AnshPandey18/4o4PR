"""Orchestrator V2 - TASK 6.

Wires all pipeline stages from indexer through context builder.
Implements cache checking, --stop-after, and status reporting.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add backend to path
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from config import load_settings, setup_logging
from common.io import read_json, write_json, ensure_dir
from indexer.index import load_cached_index, RepoIndexer, make_run_id, SCHEMA_VERSION
from retrieval.graph_builder import build_graph
from retrieval.bm25_builder import build_bm25_index
from detector.bug_detector import run_bug_detector
from context.context_builder_v2 import build_context_for_bug

logger = logging.getLogger(__name__)


# TASK 6: Stage registry
STAGE_REGISTRY = [
    ("indexer", False),
    ("graph", False),
    ("bm25", False),
    ("detector", False),
    ("context", False),
]


class PipelineOrchestrator:
    """TASK 6: Orchestrates complete pipeline."""
    
    def __init__(
        self,
        repo_root: Path,
        output_dir: Path,
        settings: Any,
        run_id: Optional[str] = None,
        stop_after: Optional[str] = None
    ):
        """Initialize orchestrator.
        
        Args:
            repo_root: Repository root path
            settings: Settings object
            output_dir: Output directory for run
            run_id: Optional run ID
            stop_after: Optional stage to stop after
        """
        self.repo_root = repo_root.resolve()
        self.output_dir = output_dir.resolve()
        self.settings = settings
        self.stop_after = stop_after
        
        # Generate run ID if not provided
        now_utc = datetime.now(timezone.utc)
        self.run_id = run_id or make_run_id(now_utc)
        self.now_utc = now_utc
        
        # TASK 6.2: Create run directory
        self.run_dir = output_dir / 'runs' / self.run_id
        ensure_dir(self.run_dir)
        
        # TASK 6.9: Set LLM kill switch if stop_after is set
        if stop_after:
            os.environ['LLM_DISABLED'] = '1'
            logger.info("LLM kill switch enabled (--stop-after flag)")
        
        # Paths
        self.index_path = self.run_dir / 'index.json'
        self.graph_path = self.run_dir / 'graph.json'
        self.bm25_path = self.run_dir / 'bm25_index.json'
        self.bug_groups_path = self.run_dir / 'bug_groups.json'
        self.bug_report_path = self.run_dir / 'bug_report.json'
        self.context_dir = self.run_dir / 'context'
        self.status_path = self.run_dir / 'status.json'
        
        # Statistics
        self.stats = {}
        self.completed_stages = []
        self.failed_collectors = []
    
    def run(self) -> int:
        """Run the complete pipeline.
        
        Returns:
            Exit code (0 = success)
        """
        logger.info("=" * 80)
        logger.info(f"4o4PR PIPELINE - RUN ID: {self.run_id}")
        logger.info("=" * 80)
        logger.info(f"Repository: {self.repo_root}")
        logger.info(f"Output: {self.run_dir}")
        logger.info(f"Schema version: {SCHEMA_VERSION}")
        if self.stop_after:
            logger.info(f"Stop after: {self.stop_after}")
        logger.info("")
        
        # TASK 6.2: Write run.json
        self._write_run_info()
        
        # TASK 6.3: Check index cache
        if self._should_run_stage("indexer"):
            if not self._run_indexer():
                return self._write_status_and_exit("indexer", failed=True)
            self.completed_stages.append("indexer")
            if self._should_stop_after("indexer"):
                return self._write_status_and_exit("indexer")
        
        # TASK 6.4: Run graph builder
        if self._should_run_stage("graph"):
            if not self._run_graph_builder():
                return self._write_status_and_exit("graph", failed=True)
            self.completed_stages.append("graph")
            if self._should_stop_after("graph"):
                return self._write_status_and_exit("graph")
        
        # TASK 6.5: Run BM25 builder
        if self._should_run_stage("bm25"):
            if not self._run_bm25_builder():
                return self._write_status_and_exit("bm25", failed=True)
            self.completed_stages.append("bm25")
            if self._should_stop_after("bm25"):
                return self._write_status_and_exit("bm25")
        
        # TASK 6.6: Run bug detector & grouper
        if self._should_run_stage("detector"):
            if not self._run_bug_detector():
                return self._write_status_and_exit("detector", failed=True)
            self.completed_stages.append("detector")
            if self._should_stop_after("detector"):
                return self._write_status_and_exit("detector")
        
        # TASK 6.7: Run context builder
        if self._should_run_stage("context"):
            if not self._run_context_builder():
                return self._write_status_and_exit("context", failed=True)
            self.completed_stages.append("context")
        
        # TASK 6.8: Write final status
        return self._write_status_and_exit("context")
    
    def _should_run_stage(self, stage: str) -> bool:
        """Check if stage should run based on stop_after."""
        if not self.stop_after:
            return True
        
        # Run all stages up to and including stop_after
        for name, _ in STAGE_REGISTRY:
            if name == self.stop_after:
                return True
            if name == stage:
                return True
        
        return False
    
    def _should_stop_after(self, stage: str) -> bool:
        """Check if should stop after this stage."""
        return self.stop_after == stage
    
    def _write_run_info(self):
        """TASK 6.2: Write run.json with basic info."""
        # Get git commit
        commit = None
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                commit = result.stdout.strip()
        except:
            pass
        
        run_info = {
            'run_id': self.run_id,
            'repo_path': str(self.repo_root),
            'commit': commit,
            'started_at': self.now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        run_file = self.run_dir / 'run.json'
        write_json(run_file, run_info)
        logger.info(f"Created run.json")
    
    def _run_indexer(self) -> bool:
        """TASK 6.3: Run indexer with cache check.
        
        Returns:
            True on success
        """
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 1: Repository Indexer")
        logger.info("=" * 80)
        
        # Check cache
        cache_dir = self.output_dir / 'cache'
        ensure_dir(cache_dir)
        
        logger.info("Checking cache...")
        cached_index = load_cached_index(
            self.repo_root,
            cache_dir,
            self.settings.import_roots,
            self.settings.exclude_dirs
        )
        
        if cached_index:
            logger.info("Using cached index")
            # Write to run directory
            write_json(self.index_path, cached_index.to_dict())
            index_data = cached_index
        else:
            logger.info("Building new index...")
            # Run indexer
            indexer = RepoIndexer(
                project_root=self.repo_root,
                import_roots=self.settings.import_roots,
                test_dirs=self.settings.test_dirs,
                exclude_patterns=self.settings.exclude_dirs
            )
            
            try:
                index_data = indexer.index(
                    run_id=self.run_id,
                    cache_dir=cache_dir,
                    now_utc=self.now_utc
                )
                
                # Write to run directory
                write_json(self.index_path, index_data.to_dict())
                
                logger.info(f"Index complete: {len(index_data.symbols)} symbols")
            except Exception as e:
                logger.error(f"Indexer failed: {e}", exc_info=True)
                return False
        
        # Record stats
        self.stats['files'] = len(index_data.files)
        self.stats['symbols'] = len(index_data.symbols)
        self.stats['references'] = len(index_data.references)
        self.stats['failures'] = len(index_data.failures)
        
        logger.info(f"  Files: {self.stats['files']}")
        logger.info(f"  Symbols: {self.stats['symbols']}")
        logger.info(f"  References: {self.stats['references']}")
        logger.info(f"  Failures: {self.stats['failures']}")
        
        return True
    
    def _run_graph_builder(self) -> bool:
        """TASK 6.4: Run graph builder.
        
        Returns:
            True on success
        """
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 2: Graph Builder")
        logger.info("=" * 80)
        
        try:
            graph = build_graph(self.index_path, self.graph_path)
            
            self.stats['graph_nodes'] = len(graph['nodes'])
            self.stats['graph_edges'] = len(graph['edges'])
            self.stats['unresolved_refs'] = len(graph['unresolved'])
            
            logger.info(f"  Nodes: {self.stats['graph_nodes']}")
            logger.info(f"  Edges: {self.stats['graph_edges']}")
            logger.info(f"  Unresolved: {self.stats['unresolved_refs']}")
            
            return True
        except Exception as e:
            logger.error(f"Graph builder failed: {e}", exc_info=True)
            return False
    
    def _run_bm25_builder(self) -> bool:
        """TASK 6.5: Run BM25 builder.
        
        Returns:
            True on success
        """
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 3: BM25 Index Builder")
        logger.info("=" * 80)
        
        try:
            bm25_index = build_bm25_index(
                self.index_path,
                self.repo_root,
                self.bm25_path
            )
            
            self.stats['bm25_chunks'] = bm25_index.N
            self.stats['bm25_avg_len'] = round(bm25_index.avgdl, 1)
            
            logger.info(f"  Chunks: {self.stats['bm25_chunks']}")
            logger.info(f"  Avg length: {self.stats['bm25_avg_len']} tokens")
            
            return True
        except Exception as e:
            logger.error(f"BM25 builder failed: {e}", exc_info=True)
            return False
    
    def _run_bug_detector(self) -> bool:
        """TASK 6.6: Run bug detector & grouper.
        
        Returns:
            True on success
        """
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 4: Bug Detector & Grouper")
        logger.info("=" * 80)
        
        try:
            groups, reports = run_bug_detector(
                self.repo_root,
                self.run_dir,
                self.index_path,
                self.graph_path
            )
            
            # Count by verification status
            verified_count = sum(1 for g in groups if g.get('verified'))
            unverified_count = len(groups) - verified_count
            
            self.stats['bug_groups'] = len(groups)
            self.stats['bugs'] = len(reports)
            self.stats['verified_bugs'] = verified_count
            self.stats['unverified_bugs'] = unverified_count
            
            # ITEM 3: Check for lint_report.json
            lint_report_path = self.run_dir / 'lint_report.json'
            if lint_report_path.exists():
                lint_data = read_json(lint_report_path)
                self.stats['lint_findings'] = lint_data.get('count', 0)
            else:
                self.stats['lint_findings'] = 0
            
            logger.info(f"  Groups: {self.stats['bug_groups']}")
            logger.info(f"  Bugs: {self.stats['bugs']}")
            logger.info(f"  Verified: {self.stats['verified_bugs']}")
            logger.info(f"  Unverified: {self.stats['unverified_bugs']}")
            
            return True
        except Exception as e:
            logger.error(f"Bug detector failed: {e}", exc_info=True)
            return False
    
    def _run_context_builder(self) -> bool:
        """TASK 6.7: Run context builder for all bugs.
        
        Returns:
            True on success
        """
        logger.info("\n" + "=" * 80)
        logger.info("STAGE 5: Context Builder")
        logger.info("=" * 80)
        
        # Load bug reports
        if not self.bug_report_path.exists():
            logger.warning("No bug report found, skipping context builder")
            return True
        
        try:
            bug_report_data = read_json(self.bug_report_path)
            bugs = bug_report_data.get('bugs', [])
            
            if not bugs:
                logger.info("No bugs to build context for")
                return True
            
            logger.info(f"Building context for {len(bugs)} bug(s)...")
            
            # Load config
            config = {'context': {
                'graph_depth': 2,
                'bm25_top_k': 10,
                'fuse_scores': False,
                'token_budget': 12000
            }}
            
            # Build context for each bug
            for i, bug in enumerate(bugs, 1):
                bug_id = bug.get('bug_id', f'bug_{i}')
                logger.info(f"  [{i}/{len(bugs)}] {bug_id}")
                
                try:
                    build_context_for_bug(
                        bug,
                        self.repo_root,
                        self.index_path,
                        self.graph_path,
                        self.bm25_path,
                        self.context_dir,
                        config=config,
                        attempt=1
                    )
                except Exception as e:
                    logger.error(f"    Failed to build context for {bug_id}: {e}")
                    continue
            
            self.stats['contexts_built'] = len(bugs)
            logger.info(f"Context building complete: {len(bugs)} contexts")
            
            return True
        except Exception as e:
            logger.error(f"Context builder failed: {e}", exc_info=True)
            return False
    
    def _write_status_and_exit(self, stage: str, failed: bool = False) -> int:
        """TASK 6.8: Write status.json and exit.
        
        Args:
            stage: Last completed stage
            failed: Whether the stage failed
            
        Returns:
            Exit code
        """
        status = {
            'run_id': self.run_id,
            'stage_completed': stage,
            'status': 'failed' if failed else 'completed',
            'completed_at': datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'stages_completed': self.completed_stages,
            'statistics': self.stats,
            'failed_collectors': self.failed_collectors
        }
        
        write_json(self.status_path, status)
        
        logger.info("\n" + "=" * 80)
        if failed:
            logger.error(f"PIPELINE FAILED AT STAGE: {stage}")
        else:
            logger.info(f"PIPELINE COMPLETED: {stage}")
        logger.info("=" * 80)
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"Output: {self.run_dir}")
        logger.info(f"Status: {self.status_path}")
        logger.info("")
        
        return 1 if failed else 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="4o4PR Pipeline Orchestrator V2")
    parser.add_argument('--root', type=Path, required=True, help="Repository root")
    parser.add_argument('--output', type=Path, default=Path('output'), help="Output directory")
    parser.add_argument('--run-id', help="Run ID (auto-generated if not provided)")
    parser.add_argument('--stop-after', choices=['indexer', 'graph', 'bm25', 'detector', 'context'],
                       help="Stop after this stage")
    parser.add_argument('--config', type=Path, help="Config file (uses default if not provided)")
    parser.add_argument('-v', '--verbose', action='store_true', help="Verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load settings
    if args.config and args.config.exists():
        settings = load_settings(args.config, args.root)
    else:
        # Load default settings.yaml with project root override
        settings = load_settings(project_root=args.root)
    
    # Run pipeline
    orchestrator = PipelineOrchestrator(
        repo_root=args.root,
        output_dir=args.output,
        settings=settings,
        run_id=args.run_id,
        stop_after=args.stop_after
    )
    
    return orchestrator.run()


if __name__ == '__main__':
    sys.exit(main())
