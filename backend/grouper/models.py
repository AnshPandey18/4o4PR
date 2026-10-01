"""Data models for Bug Grouper."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Suspect:
    """Information about suspect file/symbols."""
    file: str
    symbols: List[str]  # List of symbol IDs
    resolution: str  # resolved | unresolved


@dataclass
class Cluster:
    """A cluster of bugs targeting the same symbol."""
    symbol_id: Optional[str]
    bug_ids: List[str]


@dataclass
class BugGroup:
    """A group of related bugs."""
    group_id: str
    group_key: str  # Hash of sorted bug_ids
    kind: str  # source | collection | unresolved
    suspect: Suspect
    clusters: List[Cluster]
    bug_ids: List[str]
    estimated_tokens: int
    priority: int
    status: str = "pending"  # pending | in_progress | completed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'group_id': self.group_id,
            'group_key': self.group_key,
            'kind': self.kind,
            'suspect': {
                'file': self.suspect.file,
                'symbols': self.suspect.symbols,
                'resolution': self.suspect.resolution
            },
            'clusters': [
                {
                    'symbol_id': c.symbol_id,
                    'bug_ids': c.bug_ids
                }
                for c in self.clusters
            ],
            'bug_ids': self.bug_ids,
            'estimated_tokens': self.estimated_tokens,
            'priority': self.priority,
            'status': self.status
        }


@dataclass
class ExcludedBug:
    """A bug that was excluded from grouping."""
    bug_id: str
    reason: str


@dataclass
class Totals:
    """Summary totals."""
    bugs: int
    groups: int
    excluded: int


@dataclass
class BugGroupingResult:
    """Complete bug grouping result."""
    schema_version: str
    run_id: str
    totals: Totals
    groups: List[BugGroup]
    excluded: List[ExcludedBug]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'schema_version': self.schema_version,
            'run_id': self.run_id,
            'totals': {
                'bugs': self.totals.bugs,
                'groups': self.totals.groups,
                'excluded': self.totals.excluded
            },
            'groups': [g.to_dict() for g in self.groups],
            'excluded': [
                {'bug_id': e.bug_id, 'reason': e.reason}
                for e in self.excluded
            ]
        }
