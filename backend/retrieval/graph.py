"""Graph-based retrieval over the code index."""

import heapq
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from common.io import read_json
from common.hashing import sha1_file
from .config import RetrievalConfig

logger = logging.getLogger(__name__)


class StaleIndexError(Exception):
    """Raised when the index doesn't match the current file state."""
    pass


class Tier(str, Enum):
    """Tiering for code inclusion."""
    FULL = "FULL"           # Include full source code
    SIGNATURE = "SIGNATURE"  # Include signature only
    SKELETON = "SKELETON"    # Include class skeleton (for classes)
    DROP = "DROP"           # Do not include


@dataclass
class Hit:
    """A single retrieval hit from the graph walk."""
    symbol_id: str
    score: float
    hop: int
    tier: Tier
    path: List[Tuple[str, str]]  # List of (from_id, edge_type) tuples
    
    def __lt__(self, other):
        """For heap ordering: higher score first, then lower hop, then lexical."""
        return (-self.score, self.hop, self.symbol_id) < (-other.score, other.hop, other.symbol_id)


class Graph:
    """In-memory graph representation of the code index."""
    
    def __init__(self, index_data: Dict):
        """Initialize from loaded index.json data.
        
        Args:
            index_data: Parsed index.json dictionary
        """
        self.index_data = index_data
        self.symbols = index_data['symbols']
        
        # Build adjacency maps
        call_graph = index_data['call_graph']
        self.callees = call_graph.get('callees', {})
        self.callers = call_graph.get('callers', {})
        self.references = {}
        self.referenced_by = {}
        
        # Build references maps from symbol data
        for sym_id, sym_data in self.symbols.items():
            refs = sym_data.get('references', [])
            if refs:
                self.references[sym_id] = refs
                for ref_id in refs:
                    if ref_id not in self.referenced_by:
                        self.referenced_by[ref_id] = []
                    self.referenced_by[ref_id].append(sym_id)
        
        # Build parent-child relationships
        self._parent_to_children: Dict[str, List[str]] = {}
        for sym_id, sym_data in self.symbols.items():
            parent_class = sym_data.get('parent_class')
            if parent_class:
                # Find parent class symbol ID
                parent_id = self._find_class_id(sym_data['file'], parent_class)
                if parent_id:
                    if parent_id not in self._parent_to_children:
                        self._parent_to_children[parent_id] = []
                    self._parent_to_children[parent_id].append(sym_id)
    
    def _find_class_id(self, file: str, class_name: str) -> Optional[str]:
        """Find symbol ID for a class in a given file."""
        for sym_id, sym_data in self.symbols.items():
            if sym_data['file'] == file and sym_data['name'] == class_name and sym_data['kind'] == 'class':
                return sym_id
        return None
    
    @classmethod
    def load(cls, index_path: Path) -> 'Graph':
        """Load graph from index.json file.
        
        Args:
            index_path: Path to index.json
            
        Returns:
            Graph instance
        """
        index_data = read_json(index_path)
        return cls(index_data)
    
    def children(self, class_id: str) -> List[str]:
        """Get methods of a class.
        
        Args:
            class_id: Class symbol ID
            
        Returns:
            List of method symbol IDs
        """
        return self._parent_to_children.get(class_id, [])
    
    def symbol_at(self, file: str, line: int) -> Optional[str]:
        """Find the innermost symbol containing the given line.
        
        Args:
            file: POSIX relative file path
            line: Line number (1-indexed)
            
        Returns:
            Symbol ID or None
        """
        candidates = []
        
        for sym_id, sym_data in self.symbols.items():
            if sym_data['file'] != file:
                continue
            
            line_start = sym_data.get('line_start')
            line_end = sym_data.get('line_end')
            
            if line_start and line_end and line_start <= line <= line_end:
                # Calculate size (smaller = more specific)
                size = line_end - line_start
                candidates.append((size, sym_id))
        
        if not candidates:
            return None
        
        # Return the smallest (most specific) symbol
        candidates.sort()
        return candidates[0][1]
    
    def check_fresh(self, repo_root: Path) -> None:
        """Check if indexed files match disk state.
        
        Args:
            repo_root: Repository root directory
            
        Raises:
            StaleIndexError: If any indexed file has changed
        """
        changed = []
        files = self.index_data.get('files', {})
        
        for file_path, file_info in files.items():
            disk_path = repo_root / file_path
            
            if not disk_path.exists():
                changed.append(f"{file_path} (deleted)")
                continue
            
            expected_sha1 = file_info.get('sha1')
            if not expected_sha1:
                continue
            
            actual_sha1 = sha1_file(disk_path)
            if actual_sha1 != expected_sha1:
                changed.append(f"{file_path}")
        
        if changed:
            raise StaleIndexError(f"Files changed since indexing: {', '.join(changed)}")


def walk(
    graph: Graph,
    seeds: Dict[str, float],
    cfg: Optional[RetrievalConfig] = None
) -> List[Hit]:
    """Perform best-first graph walk from seed symbols.
    
    Args:
        graph: Code graph
        seeds: Dict mapping symbol_id to initial score (typically 1.0)
        cfg: Retrieval configuration (uses defaults if None)
        
    Returns:
        List of Hit objects, sorted by score (descending), then hop, then symbol_id
    """
    if cfg is None:
        cfg = RetrievalConfig()
    
    # Priority queue: (-score, hop, symbol_id, path)
    heap: List[Tuple[float, int, str, List[Tuple[str, str]]]] = []
    
    # Track best score for each node
    best_scores: Dict[str, float] = {}
    
    # Track best path for each node
    best_paths: Dict[str, List[Tuple[str, str]]] = {}
    
    # Track visited count
    visited_count = 0
    
    # Initialize with seeds
    for sym_id, score in seeds.items():
        if sym_id not in graph.symbols:
            logger.warning(f"Seed symbol {sym_id} not in graph")
            continue
        
        heapq.heappush(heap, (-score, 0, sym_id, []))
        best_scores[sym_id] = score
        best_paths[sym_id] = []
    
    # Best-first search
    while heap and visited_count < cfg.MAX_VISITED:
        neg_score, hop, current_id, path = heapq.heappop(heap)
        score = -neg_score
        
        # Skip if we've found a better score for this node
        if score < best_scores.get(current_id, 0.0):
            continue
        
        visited_count += 1
        
        # Stop expanding at MAX_HOPS
        if hop >= cfg.MAX_HOPS:
            continue
        
        current_sym = graph.symbols.get(current_id)
        if not current_sym:
            continue
        
        is_test = current_sym.get('is_test', False)
        
        # Get neighbors with edge types
        neighbors = _get_neighbors(graph, current_id, current_sym, is_test, cfg)
        
        for neighbor_id, edge_type in neighbors:
            # Calculate neighbor score
            edge_weight = cfg.EDGE_WEIGHTS.get(edge_type, 0.5)
            neighbor_score = score * edge_weight * cfg.DECAY
            
            # Prune low scores
            if neighbor_score < cfg.MIN_SCORE:
                continue
            
            # Check if this is the best score for this neighbor
            if neighbor_score > best_scores.get(neighbor_id, 0.0):
                best_scores[neighbor_id] = neighbor_score
                new_path = path + [(current_id, edge_type)]
                best_paths[neighbor_id] = new_path
                heapq.heappush(heap, (-neighbor_score, hop + 1, neighbor_id, new_path))
    
    # Build hits with tiering
    hits = []
    
    for sym_id, score in best_scores.items():
        sym_data = graph.symbols.get(sym_id)
        if not sym_data:
            continue
        
        # Test nodes only appear as seeds
        is_test = sym_data.get('is_test', False)
        is_seed = sym_id in seeds
        
        if is_test and not is_seed:
            continue
        
        # Determine tier
        tier = _determine_tier(sym_data, score, cfg)
        
        if tier == Tier.DROP:
            continue
        
        hop_count = len(best_paths.get(sym_id, []))
        
        hits.append(Hit(
            symbol_id=sym_id,
            score=score,
            hop=hop_count,
            tier=tier,
            path=best_paths.get(sym_id, [])
        ))
    
    # Sort: -score, hop, symbol_id
    hits.sort(key=lambda h: (-h.score, h.hop, h.symbol_id))
    
    return hits


def _get_neighbors(
    graph: Graph,
    current_id: str,
    current_sym: Dict,
    is_test: bool,
    cfg: RetrievalConfig
) -> List[Tuple[str, str]]:
    """Get neighbors of a node with their edge types.
    
    Returns:
        List of (neighbor_id, edge_type) tuples
    """
    neighbors = []
    
    # Forward edges: callees
    callees = graph.callees.get(current_id, [])
    for callee_id in callees:
        callee_sym = graph.symbols.get(callee_id)
        if not callee_sym:
            continue
        
        callee_kind = callee_sym.get('kind')
        
        # Determine edge type
        if callee_kind == 'class':
            # Check if this is a class-only fallback (test with only class target)
            if is_test and len(callees) == 1:
                # Class-only fallback: use 'tests' edge
                neighbors.append((callee_id, 'tests'))
            else:
                # Normal instantiation
                neighbors.append((callee_id, 'instantiates'))
        else:
            # Function or method
            if is_test:
                neighbors.append((callee_id, 'tests'))
            else:
                neighbors.append((callee_id, 'calls'))
    
    # Forward edges: references (to constants)
    references = graph.references.get(current_id, [])
    for ref_id in references:
        neighbors.append((ref_id, 'references'))
    
    # Backward edges: callers (with hub detection)
    if not is_test:  # Never traverse called_by into tests
        callers = graph.callers.get(current_id, [])
        
        # Count non-test callers for hub detection
        non_test_callers = []
        for caller_id in callers:
            caller_sym = graph.symbols.get(caller_id)
            if caller_sym and not caller_sym.get('is_test', False):
                non_test_callers.append(caller_id)
        
        # Hub guard: skip if too many non-test callers
        if len(non_test_callers) <= cfg.HUB_FAN_IN:
            for caller_id in non_test_callers:
                neighbors.append((caller_id, 'called_by'))
    
    # Backward edges: referenced_by
    if not is_test:
        referenced_by = graph.referenced_by.get(current_id, [])
        for ref_by_id in referenced_by:
            ref_by_sym = graph.symbols.get(ref_by_id)
            if ref_by_sym and not ref_by_sym.get('is_test', False):
                neighbors.append((ref_by_id, 'referenced_by'))
    
    # Class expansion: if this is a class that was reached via 'tests' edge (class-only fallback),
    # expand to its methods via 'contains'
    if current_sym.get('kind') == 'class':
        # Check if we have children (methods)
        for method_id in graph.children(current_id):
            neighbors.append((method_id, 'contains'))
    
    return neighbors


def _determine_tier(sym_data: Dict, score: float, cfg: RetrievalConfig) -> Tier:
    """Determine inclusion tier for a symbol based on score.
    
    Args:
        sym_data: Symbol data dictionary
        score: Retrieval score
        cfg: Configuration
        
    Returns:
        Tier enum value
    """
    kind = sym_data.get('kind')
    
    # Classes: never FULL, only SKELETON
    if kind == 'class':
        if score >= cfg.SIGNATURE_THRESHOLD:
            return Tier.SKELETON
        return Tier.DROP
    
    # Constants: FULL if above signature threshold (they're small)
    if kind == 'constant':
        if score >= cfg.SIGNATURE_THRESHOLD:
            return Tier.FULL
        return Tier.DROP
    
    # Functions and methods: tier by score
    if score >= cfg.FULL_THRESHOLD:
        return Tier.FULL
    elif score >= cfg.SIGNATURE_THRESHOLD:
        return Tier.SIGNATURE
    else:
        return Tier.DROP


def explain(hit: Hit) -> str:
    """Generate human-readable path explanation for a hit.
    
    Args:
        hit: Hit object
        
    Returns:
        Path string like "test_x -tests-> filter -calls-> _validate"
    """
    if not hit.path:
        return hit.symbol_id
    
    parts = []
    for from_id, edge_type in hit.path:
        # Extract symbol name from ID
        from_name = from_id.split('::')[-1]
        parts.append(f"{from_name} -{edge_type}->")
    
    # Add final symbol
    to_name = hit.symbol_id.split('::')[-1]
    parts.append(to_name)
    
    return ' '.join(parts)
