"""Configuration for retrieval system."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RetrievalConfig:
    """Configuration for graph-based and lexical retrieval.
    
    All tunable parameters are centralized here with sensible defaults.
    """
    
    # Edge weights for different relationship types
    EDGE_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'tests': 1.0,           # Test calls source function
        'calls': 0.8,           # Function calls another function
        'references': 0.8,      # Function references a constant
        'called_by': 0.5,       # Reverse of calls
        'decorated_by': 0.5,    # TASK 5: Function decorated by decorator
        'referenced_by': 0.3,   # Reverse of references
        'instantiates': 0.3,    # Function instantiates a class
        'contains': 0.8         # Class contains methods
    })
    
    # Decay factor applied per hop
    DECAY: float = 0.9
    
    # Maximum number of hops in the walk
    MAX_HOPS: int = 3
    
    # Minimum score threshold (nodes below this are pruned)
    MIN_SCORE: float = 0.15
    
    # Score thresholds for tiering
    FULL_THRESHOLD: float = 0.60        # Include full source code
    SIGNATURE_THRESHOLD: float = 0.25   # Include signature only
    
    # Hub detection threshold
    HUB_FAN_IN: int = 8  # Skip called_by expansion for nodes with more callers
    
    # Maximum nodes to visit (prevents runaway searches)
    MAX_VISITED: int = 300
    
    # BM25 fusion weight (Phase 3)
    FUSION_BM25_WEIGHT: float = 0.5
    
    # Mention boost (Phase 4)
    MENTION_BOOST: float = 0.4
    
    # BM25 parameters (Phase 3)
    BM25_K1: float = 1.5
    BM25_B: float = 0.75
    
    # BM25 stoplist (Phase 3)
    BM25_STOPLIST: frozenset = field(default_factory=lambda: frozenset({
        'def', 'return', 'self', 'cls', 'if', 'else', 'elif',
        'for', 'in', 'is', 'not', 'and', 'or', 'import', 'from',
        'as', 'none', 'true', 'false'
    }))
