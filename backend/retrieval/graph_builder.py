"""Graph builder for schema 13 index format.

TASK 2: Builds graph.json from index.json symbols and references lists.
Implements lookup tables, reference resolution, and unresolved tracking.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

from common.io import read_json, write_json

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds call graph from index.json (schema 13).
    
    TASK 2.1-2.10: Adapts to new index format, preserves existing walk function.
    """
    
    def __init__(self):
        """Initialize graph builder."""
        self.nodes: List[str] = []
        self.edges: List[Dict[str, str]] = []
        self.unresolved: List[Dict[str, Any]] = []
        self.lookup: Dict[str, List[str]] = {}  # name -> list of symbol_ids
        
    def build(self, index_path: Path) -> Dict[str, Any]:
        """Build graph from index.json.
        
        TASK 2.2: Receives symbols and references from index.json.
        
        Args:
            index_path: Path to index.json
            
        Returns:
            Dict with nodes, edges, unresolved
        """
        logger.info(f"Building graph from {index_path}")
        
        # Load index
        index_data = read_json(index_path)
        symbols = index_data.get('symbols', [])
        references = index_data.get('references', [])
        
        # TASK 2.3: Create one node per symbol
        self._create_nodes(symbols)
        
        # TASK 2.4: Build lookup table
        self._build_lookup(symbols)
        
        # TASK 2.5-2.9: Process references to create edges
        self._process_references(references)
        
        graph = {
            'nodes': sorted(self.nodes),  # Deterministic order
            'edges': self.edges,
            'unresolved': self.unresolved
        }
        
        logger.info(f"Built graph: {len(self.nodes)} nodes, {len(self.edges)} edges, "
                   f"{len(self.unresolved)} unresolved")
        
        return graph
    
    def _create_nodes(self, symbols: List[Dict[str, Any]]) -> None:
        """TASK 2.3: Create one node per symbol (including modules).
        
        Args:
            symbols: List of symbol records from index.json
        """
        for sym in symbols:
            symbol_id = sym.get('id', sym.get('symbol_id'))  # FIX 4: Support both old and new
            if symbol_id:
                self.nodes.append(symbol_id)
    
    def _build_lookup(self, symbols: List[Dict[str, Any]]) -> None:
        """TASK 2.4: Build lookup table mapping names to symbol IDs.
        
        Indexes both bare names and qualified names so lookups work for:
        - "_validate_user" -> finds the bare function
        - "UserService._validate_user" -> finds the qualified method
        
        Args:
            symbols: List of symbol records
        """
        for sym in symbols:
            symbol_id = sym.get('id', sym.get('symbol_id'))  # FIX 4: Support both old and new
            if not symbol_id:
                continue
            
            name = sym.get('name')
            qualified_name = sym.get('qualified_name')
            
            # Index by bare name
            if name:
                if name not in self.lookup:
                    self.lookup[name] = []
                self.lookup[name].append(symbol_id)
            
            # Index by qualified name (if different from bare name)
            if qualified_name and qualified_name != name:
                if qualified_name not in self.lookup:
                    self.lookup[qualified_name] = []
                self.lookup[qualified_name].append(symbol_id)
        
        logger.debug(f"Built lookup table with {len(self.lookup)} entries")
    
    def _process_references(self, references: List[Dict[str, Any]]) -> None:
        """TASK 2.5-2.8: Process all references to create edges.
        
        Args:
            references: List of reference records (calls, imports, base_class)
        """
        for ref in references:
            kind = ref.get('kind')
            
            if kind == 'call':
                self._process_call(ref)
            elif kind in ('import', 'import_from'):
                self._process_import(ref)
            elif kind == 'base_class':
                self._process_base_class(ref)
    
    def _process_call(self, ref: Dict[str, Any]) -> None:
        """TASK 2.5: Process call reference.
        
        TASK 2.5: A caller of "<module>" maps to that file's module symbol.
        FIX 1: Use resolved callee IDs directly from indexer.
        
        Args:
            ref: Call reference dict
        """
        caller = ref.get('caller', '')
        callee = ref.get('callee', '')
        
        if not caller or not callee:
            return
        
        # TASK 2.5: Handle <module> caller
        if caller == '<module>':
            file = ref.get('file', '')
            if file:
                # Map to module symbol: "file.py::<module>"
                caller = f"{file}::<module>"
        
        # FIX 1: Callee is already resolved by indexer in form "<file>::<qualified_name>"
        # Only use lookup as fallback for imports and base classes
        if '::' in callee:
            # Already a resolved ID, use directly
            if callee in self.nodes:
                if caller in self.nodes:
                    self.edges.append({
                        'from': caller,
                        'to': callee,
                        'kind': 'call'
                    })
                else:
                    # Caller not found
                    self.unresolved.append({
                        'reference': ref,
                        'kind': 'call',
                        'reason': 'caller not found'
                    })
            else:
                # Callee exists in index but not in nodes - external
                self.unresolved.append({
                    'reference': ref,
                    'kind': 'call',
                    'reason': 'external'
                })
        else:
            # Not a resolved ID, try lookup (fallback for old format)
            resolved_callee = self._resolve_name(callee)
            
            if resolved_callee:
                if caller in self.nodes:
                    self.edges.append({
                        'from': caller,
                        'to': resolved_callee,
                        'kind': 'call'
                    })
                else:
                    self.unresolved.append({
                        'reference': ref,
                        'kind': 'call',
                        'reason': 'caller not found'
                    })
            else:
                # No match for callee
                self.unresolved.append({
                    'reference': ref,
                    'kind': 'call',
                    'reason': 'no match'
                })
    
    def _process_import(self, ref: Dict[str, Any]) -> None:
        """TASK 2.6: Process import reference.
        
        Args:
            ref: Import reference dict
        """
        # Imports create edges if resolved_file is present
        resolved_file = ref.get('resolved_file')
        file = ref.get('file')
        names = ref.get('names', [])
        
        if not resolved_file or not file:
            return
        
        # Create edge from importing file's module to imported file's module
        from_module = f"{file}::<module>"
        to_module = f"{resolved_file}::<module>"
        
        if from_module in self.nodes and to_module in self.nodes:
            self.edges.append({
                'from': from_module,
                'to': to_module,
                'kind': 'import'
            })
        
        # For "from X import Y", also try to resolve specific imports
        if ref.get('kind') == 'import_from':
            for name_dict in names:
                imported_name = name_dict.get('name')
                if imported_name:
                    # Try to resolve imported symbol
                    target_id = f"{resolved_file}::{imported_name}"
                    if target_id in self.nodes and from_module in self.nodes:
                        self.edges.append({
                            'from': from_module,
                            'to': target_id,
                            'kind': 'import'
                        })
    
    def _process_base_class(self, ref: Dict[str, Any]) -> None:
        """TASK 2.7: Process base_class reference.
        
        Args:
            ref: Base class reference dict
        """
        caller = ref.get('caller', '')  # Class qualified name
        callee_text = ref.get('callee_text', '')  # Base class name
        
        if not caller or not callee_text:
            return
        
        # Look up base class name
        resolved_base = self._resolve_name(callee_text)
        
        if resolved_base:
            if caller in self.nodes:
                self.edges.append({
                    'from': caller,
                    'to': resolved_base,
                    'kind': 'base_class'
                })
            else:
                self.unresolved.append({
                    'reference': ref,
                    'kind': 'base_class',
                    'reason': 'caller not found'
                })
        else:
            matches = self.lookup.get(callee_text, [])
            reason = 'no match' if len(matches) == 0 else 'multiple matches'
            self.unresolved.append({
                'reference': ref,
                'kind': 'base_class',
                'reason': reason
            })
    
    def _resolve_name(self, name: str) -> Optional[str]:
        """TASK 2.7: Look up a name and return symbol ID if exactly one match.
        
        Args:
            name: Name or qualified name to resolve
            
        Returns:
            Symbol ID if exactly one match, None otherwise
        """
        matches = self.lookup.get(name, [])
        if len(matches) == 1:
            return matches[0]
        return None
    
    def save(self, output_path: Path) -> None:
        """TASK 2.9: Save graph to graph.json.
        
        Args:
            output_path: Path to graph.json
        """
        graph = {
            'nodes': sorted(self.nodes),
            'edges': self.edges,
            'unresolved': self.unresolved
        }
        write_json(output_path, graph)
        logger.info(f"Saved graph to {output_path}")


def build_graph(index_path: Path, output_path: Path) -> Dict[str, Any]:
    """Build and save graph from index.
    
    Args:
        index_path: Path to index.json
        output_path: Path to graph.json
        
    Returns:
        Graph dict
    """
    builder = GraphBuilder()
    graph = builder.build(index_path)
    builder.save(output_path)
    return graph
