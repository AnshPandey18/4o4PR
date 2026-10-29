"""Bug grouper - TASK 4.8.

Groups candidates by proximity (file, symbol, line span).
"""

import logging
from typing import List, Dict, Any, Tuple

from common.io import write_json

logger = logging.getLogger(__name__)


class BugGrouper:
    """TASK 4.8: Groups bug candidates by proximity."""
    
    def __init__(self):
        """Initialize grouper."""
        self.groups = []
        self.group_id_counter = 1
    
    def group(self, candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """TASK 4.8: Group candidates by proximity.
        
        Args:
            candidates: List of candidate dicts (with verification results)
            
        Returns:
            Tuple of (bug_groups, bug_reports)
        """
        if not candidates:
            return [], []
        
        logger.info(f"Grouping {len(candidates)} candidates...")
        
        # TASK 4.8.1: Bucket by (file, symbol)
        buckets = self._bucket_candidates(candidates)
        
        logger.debug(f"Created {len(buckets)} buckets")
        
        # Process each bucket
        self.groups = []
        for bucket_key, bucket_candidates in buckets.items():
            # TASK 4.8.2: Sort by line span
            bucket_candidates.sort(key=lambda c: (c['line_start'], c['line_end']))
            
            # TASK 4.8.3-4.8.5: Merge by proximity
            self._merge_bucket(bucket_candidates)
        
        # TASK 4.8.6: Set group confidence
        for group in self.groups:
            self._set_confidence(group)
        
        # Build bug reports
        bug_reports = self._build_bug_reports()
        
        logger.info(f"Created {len(self.groups)} groups, {len(bug_reports)} bug reports")
        
        return self.groups, bug_reports
    
    def _bucket_candidates(self, candidates: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        """TASK 4.8.1: Bucket candidates by (file, symbol).
        
        Args:
            candidates: List of candidates
            
        Returns:
            Dict mapping (file, symbol) -> list of candidates
        """
        buckets = {}
        
        for candidate in candidates:
            file = candidate.get('file', '')
            symbol = candidate.get('symbol', '')
            key = (file, symbol)
            
            if key not in buckets:
                buckets[key] = []
            buckets[key].append(candidate)
        
        return buckets
    
    def _merge_bucket(self, bucket_candidates: List[Dict[str, Any]]) -> None:
        """TASK 4.8.3-4.8.5: Merge candidates in a bucket by proximity.
        
        Args:
            bucket_candidates: Sorted list of candidates in this bucket
        """
        if not bucket_candidates:
            return
        
        # Start first group with first candidate
        current_group = self._create_group(bucket_candidates[0])
        
        # Process remaining candidates
        for candidate in bucket_candidates[1:]:
            # TASK 4.8.3: Check if overlaps or within 3 lines
            if self._should_merge(current_group, candidate):
                # TASK 4.8.4: Merge into group
                self._merge_into_group(current_group, candidate)
            else:
                # TASK 4.8.5: Start new group
                self.groups.append(current_group)
                current_group = self._create_group(candidate)
        
        # Add final group
        self.groups.append(current_group)
    
    def _create_group(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new group from first candidate.
        
        Args:
            candidate: First candidate
            
        Returns:
            Group dict
        """
        group_id = f"B{self.group_id_counter:03d}"
        self.group_id_counter += 1
        
        return {
            'group_id': group_id,
            'file': candidate['file'],
            'symbol': candidate['symbol'],
            'line_start': candidate['line_start'],
            'line_end': candidate['line_end'],
            'sources': [candidate['source']],
            'categories': [candidate['category']],
            'members': [candidate],
            'evidence': candidate['evidence'].copy(),
            'test_ids': candidate['test_ids'].copy() if candidate.get('test_ids') else []
        }
    
    def _should_merge(self, group: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
        """TASK 4.8.3: Check if candidate should merge into group.
        
        Merges if candidate's line_start <= group's line_end + 3.
        
        Args:
            group: Current group
            candidate: Candidate to check
            
        Returns:
            True if should merge
        """
        return candidate['line_start'] <= group['line_end'] + 3
    
    def _merge_into_group(self, group: Dict[str, Any], candidate: Dict[str, Any]) -> None:
        """TASK 4.8.4: Merge candidate into group.
        
        Extends line span, adds source, adds evidence, adds member.
        
        Args:
            group: Group to merge into
            candidate: Candidate to merge
        """
        # Extend line span
        group['line_end'] = max(group['line_end'], candidate['line_end'])
        
        # Add source if not already present
        if candidate['source'] not in group['sources']:
            group['sources'].append(candidate['source'])
        
        # Add category if not already present
        if candidate['category'] not in group['categories']:
            group['categories'].append(candidate['category'])
        
        # Add evidence
        for evidence in candidate['evidence']:
            if evidence not in group['evidence']:
                group['evidence'].append(evidence)
        
        # Add test IDs
        if candidate.get('test_ids'):
            for test_id in candidate['test_ids']:
                if test_id not in group['test_ids']:
                    group['test_ids'].append(test_id)
        
        # Add member
        group['members'].append(candidate)
    
    def _set_confidence(self, group: Dict[str, Any]) -> None:
        """TASK 4.8.6: Set group confidence and verified status.
        
        Args:
            group: Group dict
        """
        # TASK 4.8.6: Check if any member is confirmed
        has_confirmed = any(
            member.get('verified') == 'confirmed'
            for member in group['members']
        )
        
        if has_confirmed:
            group['confidence'] = 'confirmed'
            group['verified'] = True
        elif len(group['sources']) >= 2:
            # At least 2 distinct sources
            group['confidence'] = 'multi-source'
            group['verified'] = False
        else:
            group['confidence'] = 'single-source'
            group['verified'] = False
    
    def _build_bug_reports(self) -> List[Dict[str, Any]]:
        """TASK 4.8.7: Build BugReport list from groups.
        
        Returns:
            List of BugReport dicts
        """
        reports = []
        
        for group in self.groups:
            report = {
                'bug_id': group['group_id'],
                'file': group['file'],
                'symbol': group['symbol'],
                'line_start': group['line_start'],
                'line_end': group['line_end'],
                'categories': group['categories'],
                'sources': group['sources'],
                'confidence': group['confidence'],
                'verified': group['verified'],
                'evidence': group['evidence'],
                'test_ids': group['test_ids']
            }
            reports.append(report)
        
        # ITEM 4: Sort by confirmed first, then source rank (pytest, llm, heuristic), then confidence, file, line
        source_rank = {'pytest': 0, 'llm': 1, 'heuristic': 2, 'ruff': 3}
        confidence_order = {'confirmed': 0, 'multi-source': 1, 'single-source': 2}
        
        def get_primary_source(sources):
            """Get the highest priority source from a list."""
            if not sources:
                return 99
            return min(source_rank.get(s, 99) for s in sources)
        
        reports.sort(key=lambda r: (
            not r['verified'],  # False (verified=True) sorts before True (verified=False) - confirmed first
            get_primary_source(r['sources']),  # pytest < llm < heuristic
            confidence_order.get(r['confidence'], 3),
            r['file'],
            r['line_start']
        ))
        
        return reports
    
    def save(self, bug_groups_path, bug_report_path):
        """Save groups and reports to JSON.
        
        Args:
            bug_groups_path: Path for bug_groups.json
            bug_report_path: Path for bug_report.json
        """
        # TASK 4.11.1: Write bug_groups.json
        write_json(bug_groups_path, {'groups': self.groups})
        
        # TASK 4.11.2: Write bug_report.json
        reports = self._build_bug_reports()
        write_json(bug_report_path, {'bugs': reports, 'count': len(reports)})
        
        logger.info(f"Saved {len(self.groups)} groups to {bug_groups_path}")
        logger.info(f"Saved {len(reports)} bug reports to {bug_report_path}")


def group_candidates(
    candidates: List[Dict[str, Any]],
    bug_groups_path,
    bug_report_path
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Group candidates and save outputs.
    
    Args:
        candidates: List of verified candidates
        bug_groups_path: Output path for groups
        bug_report_path: Output path for reports
        
    Returns:
        Tuple of (groups, reports)
    """
    # ITEM 3: Separate ruff findings into lint_report.json
    lint_findings = [c for c in candidates if c.get('source') == 'ruff']
    bug_candidates = [c for c in candidates if c.get('source') != 'ruff']
    
    # Save lint findings
    if lint_findings:
        lint_report_path = bug_report_path.parent / 'lint_report.json'
        write_json(lint_report_path, {
            'findings': lint_findings,
            'count': len(lint_findings)
        })
        logger.info(f"Saved {len(lint_findings)} lint findings to {lint_report_path}")
    
    # Group only bug candidates
    grouper = BugGrouper()
    groups, reports = grouper.group(bug_candidates)
    grouper.save(bug_groups_path, bug_report_path)
    return groups, reports
