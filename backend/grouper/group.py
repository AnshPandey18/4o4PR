"""Bug Grouper - Clusters related bugs for efficient analysis.

Groups bugs by:
1. Excluding flaky bugs
2. Grouping collection/import errors separately
3. Clustering by suspect symbol
4. Merging by file and call graph relationships
5. Splitting oversized groups by token budget
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from common.hashing import short_hash
from common.tokens import TokenCounter, create_token_counter
from common.io import read_json
from indexer.query import RepoIndex
from .models import (
    BugGroup, BugGroupingResult, Cluster, ExcludedBug, Suspect, Totals
)

logger = logging.getLogger(__name__)


class BugGrouper:
    """Groups related bugs for batched analysis."""
    
    def __init__(
        self,
        max_bugs_per_group: int = 8,
        token_counter: Optional[TokenCounter] = None,
        analysis_budget: int = 10000
    ):
        """Initialize the bug grouper.
        
        Args:
            max_bugs_per_group: Maximum bugs per group before splitting
            token_counter: Token counter for budget estimation
            analysis_budget: Total token budget for analysis context
        """
        self.max_bugs_per_group = max_bugs_per_group
        self.token_counter = token_counter or create_token_counter("estimate")
        self.analysis_budget = analysis_budget
    
    def group(
        self,
        bug_report_path: Path,
        run_id: str,
        index: Optional[RepoIndex] = None,
        schema_version: str = "1.0"
    ) -> BugGroupingResult:
        """Group bugs from a bug report.
        
        Args:
            bug_report_path: Path to bug_report.json
            run_id: Run identifier
            index: Optional RepoIndex for call graph analysis
            schema_version: Schema version for output
            
        Returns:
            BugGroupingResult with all groups
        """
        logger.info(f"Starting bug grouping (run_id: {run_id})")
        
        # Load bug report
        bug_report = read_json(bug_report_path)
        bugs = bug_report.get('bugs', [])
        
        logger.info(f"Loaded {len(bugs)} bugs from report")
        
        # Phase 1: Exclude flaky bugs
        excluded, remaining_bugs = self._exclude_flaky(bugs)
        logger.info(f"Excluded {len(excluded)} flaky bugs")
        
        # Phase 2: Group by category
        collection_groups, unresolved_groups, source_bugs = self._categorize_bugs(remaining_bugs)
        logger.info(
            f"Categorized: {len(collection_groups)} collection groups, "
            f"{len(unresolved_groups)} unresolved groups, "
            f"{len(source_bugs)} source bugs"
        )
        
        # Phase 3: Cluster source bugs by symbol
        clusters_by_file = self._cluster_by_symbol(source_bugs)
        logger.info(f"Created {sum(len(c) for c in clusters_by_file.values())} clusters")
        
        # Phase 4: Group by file (and optionally merge by call graph)
        file_groups = self._group_by_file(clusters_by_file, index)
        logger.info(f"Created {len(file_groups)} file-based groups")
        
        # Phase 5: Split oversized groups
        final_groups = self._split_oversized_groups(file_groups, source_bugs)
        logger.info(f"Final {len(final_groups)} groups after splitting")
        
        # Combine all groups
        all_groups = collection_groups + unresolved_groups + final_groups
        
        # Assign group IDs and priorities
        all_groups = self._assign_ids_and_priorities(all_groups)
        
        # Verify invariant: every bug appears exactly once
        self._verify_invariant(bugs, all_groups, excluded)
        
        # Create result
        result = BugGroupingResult(
            schema_version=schema_version,
            run_id=run_id,
            totals=Totals(
                bugs=len(bugs),
                groups=len(all_groups),
                excluded=len(excluded)
            ),
            groups=all_groups,
            excluded=excluded
        )
        
        logger.info(f"Bug grouping complete: {len(all_groups)} groups, {len(excluded)} excluded")
        return result
    
    def _exclude_flaky(self, bugs: List[Dict]) -> Tuple[List[ExcludedBug], List[Dict]]:
        """Exclude flaky bugs.
        
        Args:
            bugs: List of bug dictionaries
            
        Returns:
            Tuple of (excluded bugs, remaining bugs)
        """
        excluded = []
        remaining = []
        
        for bug in bugs:
            if bug.get('flaky', False):
                excluded.append(ExcludedBug(
                    bug_id=bug['bug_id'],
                    reason='flaky'
                ))
            else:
                remaining.append(bug)
        
        return excluded, remaining
    
    def _categorize_bugs(
        self,
        bugs: List[Dict]
    ) -> Tuple[List[BugGroup], List[BugGroup], List[Dict]]:
        """Categorize bugs into collection errors, unresolved, and source bugs.
        
        Args:
            bugs: List of bug dictionaries
            
        Returns:
            Tuple of (collection_groups, unresolved_groups, source_bugs)
        """
        collection_groups = []
        unresolved_groups = []
        source_bugs = []
        
        # Group collection/import errors by module
        collection_by_module: Dict[str, List[str]] = {}
        
        # Group unresolved by test file
        unresolved_by_file: Dict[str, List[str]] = {}
        
        for bug in bugs:
            bug_id = bug['bug_id']
            failure_kind = bug.get('failure_kind', 'exception')
            
            if failure_kind in ('collection_error', 'import_error'):
                # Extract module from test_name
                test_name = bug['test_name']
                module = test_name.split('::')[0] if '::' in test_name else test_name
                
                if module not in collection_by_module:
                    collection_by_module[module] = []
                collection_by_module[module].append(bug_id)
            
            elif not bug.get('called_symbols') or all(
                s['resolution'] == 'unresolved' for s in bug.get('called_symbols', [])
            ):
                # Unresolved symbols
                test_name = bug['test_name']
                test_file = test_name.split('::')[0] if '::' in test_name else test_name
                
                if test_file not in unresolved_by_file:
                    unresolved_by_file[test_file] = []
                unresolved_by_file[test_file].append(bug_id)
            
            else:
                # Source bug with resolved symbols
                source_bugs.append(bug)
        
        # Create collection groups
        for module, bug_ids in collection_by_module.items():
            group = BugGroup(
                group_id="",  # Will be assigned later
                group_key=self._compute_group_key(bug_ids),
                kind="collection",
                suspect=Suspect(file=module, symbols=[], resolution="unresolved"),
                clusters=[Cluster(symbol_id=None, bug_ids=bug_ids)],
                bug_ids=bug_ids,
                estimated_tokens=0,
                priority=1
            )
            collection_groups.append(group)
        
        # Create unresolved groups
        for test_file, bug_ids in unresolved_by_file.items():
            group = BugGroup(
                group_id="",
                group_key=self._compute_group_key(bug_ids),
                kind="unresolved",
                suspect=Suspect(file=test_file, symbols=[], resolution="unresolved"),
                clusters=[Cluster(symbol_id=None, bug_ids=bug_ids)],
                bug_ids=bug_ids,
                estimated_tokens=0,
                priority=2
            )
            unresolved_groups.append(group)
        
        return collection_groups, unresolved_groups, source_bugs
    
    def _cluster_by_symbol(self, bugs: List[Dict]) -> Dict[str, List[Cluster]]:
        """Cluster bugs by their suspect symbols.
        
        Args:
            bugs: List of bug dictionaries
            
        Returns:
            Dict mapping file path to list of clusters
        """
        # Group bugs by (file, symbol)
        symbol_to_bugs: Dict[Tuple[str, str], List[str]] = {}
        
        for bug in bugs:
            bug_id = bug['bug_id']
            called_symbols = bug.get('called_symbols', [])
            
            # Get the primary suspect (first resolved symbol)
            primary_file = None
            primary_symbol = None
            
            for symbol in called_symbols:
                if symbol['resolution'] == 'resolved' and symbol.get('symbol_id'):
                    primary_file = symbol['file']
                    primary_symbol = symbol['symbol_id']
                    break
            
            if primary_file and primary_symbol:
                key = (primary_file, primary_symbol)
                if key not in symbol_to_bugs:
                    symbol_to_bugs[key] = []
                symbol_to_bugs[key].append(bug_id)
        
        # Group clusters by file
        clusters_by_file: Dict[str, List[Cluster]] = {}
        
        for (file, symbol_id), bug_ids in symbol_to_bugs.items():
            if file not in clusters_by_file:
                clusters_by_file[file] = []
            
            cluster = Cluster(symbol_id=symbol_id, bug_ids=sorted(bug_ids))
            clusters_by_file[file].append(cluster)
        
        return clusters_by_file
    
    def _group_by_file(
        self,
        clusters_by_file: Dict[str, List[Cluster]],
        index: Optional[RepoIndex]
    ) -> List[BugGroup]:
        """Group clusters by file (and optionally merge by call graph).
        
        Args:
            clusters_by_file: Clusters organized by file
            index: Optional RepoIndex for call graph
            
        Returns:
            List of BugGroup objects
        """
        groups = []
        
        for file, clusters in clusters_by_file.items():
            # Collect all symbols in this file
            all_symbols = []
            all_bug_ids = []
            
            for cluster in clusters:
                if cluster.symbol_id:
                    all_symbols.append(cluster.symbol_id)
                all_bug_ids.extend(cluster.bug_ids)
            
            # Remove duplicates and sort
            all_symbols = sorted(set(all_symbols))
            all_bug_ids = sorted(set(all_bug_ids))
            
            # Create group
            group = BugGroup(
                group_id="",
                group_key=self._compute_group_key(all_bug_ids),
                kind="source",
                suspect=Suspect(
                    file=file,
                    symbols=all_symbols,
                    resolution="resolved"
                ),
                clusters=clusters,
                bug_ids=all_bug_ids,
                estimated_tokens=0,
                priority=1
            )
            groups.append(group)
        
        # TODO: Optionally merge groups by call graph if index is provided
        # For now, we keep them separate by file
        
        return groups
    
    def _split_oversized_groups(
        self,
        groups: List[BugGroup],
        all_bugs: List[Dict]
    ) -> List[BugGroup]:
        """Split groups that exceed size or token limits.
        
        Args:
            groups: List of BugGroup objects
            all_bugs: All bug dictionaries for token estimation
            
        Returns:
            List of potentially split groups
        """
        # Build bug lookup
        bugs_by_id = {bug['bug_id']: bug for bug in all_bugs}
        
        result_groups = []
        
        for group in groups:
            # Estimate token cost
            token_estimate = self._estimate_group_tokens(group, bugs_by_id)
            group.estimated_tokens = token_estimate
            
            # Check if group needs splitting
            budget_threshold = int(self.analysis_budget * 0.7)  # 70% of budget
            
            if (len(group.bug_ids) > self.max_bugs_per_group or 
                token_estimate > budget_threshold):
                # Split the group
                split_groups = self._split_group(group, bugs_by_id, budget_threshold)
                result_groups.extend(split_groups)
            else:
                result_groups.append(group)
        
        return result_groups
    
    def _estimate_group_tokens(
        self,
        group: BugGroup,
        bugs_by_id: Dict[str, Dict]
    ) -> int:
        """Estimate token cost for a group.
        
        Args:
            group: BugGroup to estimate
            bugs_by_id: Lookup dict for bugs
            
        Returns:
            Estimated token count
        """
        total_tokens = 0
        
        # Estimate based on test code and suspect source
        for bug_id in group.bug_ids:
            bug = bugs_by_id.get(bug_id)
            if bug:
                # Test code
                test_code = bug.get('code', '')
                total_tokens += self.token_counter.count(test_code)
                
                # Error message
                error_msg = bug.get('error_message', '')
                total_tokens += self.token_counter.count(error_msg)
        
        # Add estimate for source symbols (rough estimate)
        # Assume ~100 tokens per symbol on average
        total_tokens += len(group.suspect.symbols) * 100
        
        return total_tokens
    
    def _split_group(
        self,
        group: BugGroup,
        bugs_by_id: Dict[str, Dict],
        budget_threshold: int
    ) -> List[BugGroup]:
        """Split an oversized group into smaller groups.
        
        Args:
            group: BugGroup to split
            bugs_by_id: Lookup dict for bugs
            budget_threshold: Token budget threshold
            
        Returns:
            List of split groups
        """
        # Split clusters in stable order (by symbol line number if available)
        sorted_clusters = sorted(
            group.clusters,
            key=lambda c: c.symbol_id or ""
        )
        
        split_groups = []
        current_clusters = []
        current_bug_ids = []
        current_symbols = []
        current_tokens = 0
        
        for cluster in sorted_clusters:
            # Estimate tokens for this cluster
            cluster_tokens = 0
            for bug_id in cluster.bug_ids:
                bug = bugs_by_id.get(bug_id)
                if bug:
                    cluster_tokens += self.token_counter.count(bug.get('code', ''))
                    cluster_tokens += self.token_counter.count(bug.get('error_message', ''))
            
            cluster_tokens += 100  # Estimate for source
            
            # Check if adding this cluster would exceed limits
            would_exceed_bugs = len(current_bug_ids) + len(cluster.bug_ids) > self.max_bugs_per_group
            would_exceed_tokens = current_tokens + cluster_tokens > budget_threshold
            
            if current_clusters and (would_exceed_bugs or would_exceed_tokens):
                # Create a group from current clusters
                split_group = BugGroup(
                    group_id="",
                    group_key=self._compute_group_key(current_bug_ids),
                    kind=group.kind,
                    suspect=Suspect(
                        file=group.suspect.file,
                        symbols=current_symbols,
                        resolution=group.suspect.resolution
                    ),
                    clusters=current_clusters,
                    bug_ids=current_bug_ids,
                    estimated_tokens=current_tokens,
                    priority=group.priority
                )
                split_groups.append(split_group)
                
                # Reset for next group
                current_clusters = []
                current_bug_ids = []
                current_symbols = []
                current_tokens = 0
            
            # Add cluster to current group
            current_clusters.append(cluster)
            current_bug_ids.extend(cluster.bug_ids)
            if cluster.symbol_id:
                current_symbols.append(cluster.symbol_id)
            current_tokens += cluster_tokens
        
        # Add remaining clusters as final group
        if current_clusters:
            split_group = BugGroup(
                group_id="",
                group_key=self._compute_group_key(current_bug_ids),
                kind=group.kind,
                suspect=Suspect(
                    file=group.suspect.file,
                    symbols=current_symbols,
                    resolution=group.suspect.resolution
                ),
                clusters=current_clusters,
                bug_ids=sorted(set(current_bug_ids)),
                estimated_tokens=current_tokens,
                priority=group.priority
            )
            split_groups.append(split_group)
        
        return split_groups
    
    def _assign_ids_and_priorities(self, groups: List[BugGroup]) -> List[BugGroup]:
        """Assign group IDs and sort by priority.
        
        Args:
            groups: List of BugGroup objects
            
        Returns:
            Sorted groups with assigned IDs
        """
        # Sort by: priority (asc), file (asc), first symbol line (asc)
        sorted_groups = sorted(
            groups,
            key=lambda g: (
                g.priority,
                g.suspect.file,
                min((s.split('::')[-1] for s in g.suspect.symbols), default="")
            )
        )
        
        # Assign IDs
        for i, group in enumerate(sorted_groups, 1):
            group.group_id = f"G{i}"
        
        return sorted_groups
    
    def _compute_group_key(self, bug_ids: List[str]) -> str:
        """Compute a stable group key from bug IDs.
        
        Args:
            bug_ids: List of bug IDs
            
        Returns:
            Group key (hash of sorted bug IDs)
        """
        sorted_ids = sorted(bug_ids)
        combined = '|'.join(sorted_ids)
        return short_hash(combined, length=16)
    
    def _verify_invariant(
        self,
        all_bugs: List[Dict],
        groups: List[BugGroup],
        excluded: List[ExcludedBug]
    ) -> None:
        """Verify that every bug appears exactly once.
        
        Args:
            all_bugs: All bugs from report
            groups: All groups
            excluded: Excluded bugs
            
        Raises:
            RuntimeError: If invariant is violated
        """
        all_bug_ids = {bug['bug_id'] for bug in all_bugs}
        
        # Collect bug IDs from groups
        grouped_ids = set()
        for group in groups:
            for bug_id in group.bug_ids:
                if bug_id in grouped_ids:
                    raise RuntimeError(f"Bug {bug_id} appears in multiple groups")
                grouped_ids.add(bug_id)
        
        # Collect excluded IDs
        excluded_ids = {e.bug_id for e in excluded}
        
        # Check for duplicates between grouped and excluded
        overlap = grouped_ids & excluded_ids
        if overlap:
            raise RuntimeError(f"Bugs appear in both groups and excluded: {overlap}")
        
        # Check that all bugs are accounted for
        accounted = grouped_ids | excluded_ids
        missing = all_bug_ids - accounted
        if missing:
            raise RuntimeError(f"Bugs not accounted for: {missing}")
        
        extra = accounted - all_bug_ids
        if extra:
            raise RuntimeError(f"Unknown bugs in groups/excluded: {extra}")
        
        logger.info("✓ Invariant verified: all bugs accounted for exactly once")
