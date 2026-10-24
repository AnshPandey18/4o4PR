"""Retrieval package for RAG-based context enhancement.

Provides graph-based and lexical retrieval over the code index.
"""

from .config import RetrievalConfig
from .graph import Graph, Hit, walk, StaleIndexError
from .seeds import seeds_from_bug_group

__all__ = [
    'RetrievalConfig',
    'Graph',
    'Hit',
    'walk',
    'seeds_from_bug_group',
    'StaleIndexError'
]
