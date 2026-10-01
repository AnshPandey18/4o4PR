"""Data models for Context Builder."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ContextStatus(Enum):
    """Status of context building."""
    OK = "ok"
    OVERFLOW = "overflow"


class ContextTier(Enum):
    """Context tiers for prioritization."""
    T0 = "T0"  # Role and rules
    T1 = "T1"  # Failure evidence
    T2 = "T2"  # Test code
    T3 = "T3"  # Suspect functions
    T4 = "T4"  # Neighbors (callers/callees)
    T5 = "T5"  # Repo map
    T6 = "T6"  # Git history (optional)


class ItemForm(Enum):
    """Form in which an item is included."""
    VERBATIM = "verbatim"
    FULL = "full"
    SIGNATURE = "signature"
    COMPRESSED = "compressed"


@dataclass
class IncludedItem:
    """An item included in the context."""
    item: str  # Description or identifier
    tier: str  # T0-T6
    form: str  # verbatim, full, signature, compressed
    lines: Optional[str] = None  # e.g., "12-14"
    tokens: int = 0
    reason: str = ""


@dataclass
class DroppedItem:
    """An item that was dropped from context."""
    item: str
    tier: str
    reason: str  # over_budget | lower_priority | denylisted | not_found


@dataclass
class SanitizationSummary:
    """Summary of sanitization applied."""
    docstrings_removed: int = 0
    comments_removed: int = 0
    secrets_redacted: int = 0


@dataclass
class ContextManifest:
    """Manifest describing what's in the context."""
    stage: str  # analysis | fix
    run_id: str
    group_id: str
    bug_ids: List[str]
    attempt: int
    status: str  # ok | overflow
    prompt_version: str
    token_method: str
    budget: Dict[str, int]  # input, output_reserved, used
    retrieval: str  # evidence | lexical_fallback
    sanitization: SanitizationSummary
    included: List[IncludedItem]
    dropped: List[DroppedItem]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'stage': self.stage,
            'run_id': self.run_id,
            'group_id': self.group_id,
            'bug_ids': self.bug_ids,
            'attempt': self.attempt,
            'status': self.status,
            'prompt_version': self.prompt_version,
            'token_method': self.token_method,
            'budget': self.budget,
            'retrieval': self.retrieval,
            'sanitization': {
                'docstrings_removed': self.sanitization.docstrings_removed,
                'comments_removed': self.sanitization.comments_removed,
                'secrets_redacted': self.sanitization.secrets_redacted
            },
            'included': [
                {
                    'item': item.item,
                    'tier': item.tier,
                    'form': item.form,
                    'lines': item.lines,
                    'tokens': item.tokens,
                    'reason': item.reason
                }
                for item in self.included
            ],
            'dropped': [
                {
                    'item': item.item,
                    'tier': item.tier,
                    'reason': item.reason
                }
                for item in self.dropped
            ],
            'warnings': self.warnings
        }


@dataclass
class BuiltContext:
    """The result of building a context."""
    status: ContextStatus
    prompt_text: Optional[str]
    manifest: ContextManifest
    
    @property
    def is_ok(self) -> bool:
        """Check if context was built successfully."""
        return self.status == ContextStatus.OK
