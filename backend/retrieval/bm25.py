"""BM25 scoring and inverted index.

Implements Okapi BM25 ranking function with query term weighting.

Query Term Rule:
Each distinct query term contributes once to the score. If a term appears multiple
times in the query, its contribution is weighted by min(query_tf, QUERY_TERM_CAP).
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from retrieval.bm25_chunks import Chunk, StaleIndexError
from common.hashing import sha1_file


# Configuration
QUERY_TERM_CAP = 2  # Maximum query term weight


@dataclass
class SearchHit:
    """A search result with score breakdown."""
    symbol_id: str
    rank: int  # 1-indexed
    score: float
    breakdown: List[Dict[str, any]]  # Per-term contribution details
    
    def __post_init__(self):
        # Sort breakdown by term
        self.breakdown = sorted(self.breakdown, key=lambda x: x['term'])


@dataclass
class BM25Params:
    """BM25 parameters."""
    k1: float = 1.5
    b: float = 0.75


@dataclass
class BM25Index:
    """BM25 inverted index with search capability."""
    
    params: BM25Params
    N: int  # Number of searchable chunks
    avgdl: float  # Average document length
    chunks: List[Dict]  # Chunk metadata (sorted by id)
    postings: Dict[str, List[Tuple[int, int]]]  # term -> [(chunk_idx, tf)]
    index_content_hash: str  # From index.json
    file_sha1s: Dict[str, str]  # file -> sha1 for freshness check
    
    @classmethod
    def build(cls, chunks: List[Chunk], params: BM25Params, 
              index_content_hash: str, file_sha1s: Dict[str, str]) -> 'BM25Index':
        """Build BM25 index from chunks.
        
        Args:
            chunks: List of searchable chunks
            params: BM25 parameters
            index_content_hash: Content hash from index.json
            file_sha1s: File path -> SHA1 mapping for freshness
            
        Returns:
            BM25Index instance
        """
        N = len(chunks)
        if N == 0:
            raise ValueError("Cannot build index from zero chunks")
        
        # Compute average document length
        total_tokens = sum(c.token_count for c in chunks)
        avgdl = total_tokens / N
        
        # Build inverted index
        postings = {}
        
        for chunk_idx, chunk in enumerate(chunks):
            for term, tf in chunk.term_frequencies.items():
                if term not in postings:
                    postings[term] = []
                postings[term].append((chunk_idx, tf))
        
        # Sort postings by chunk_idx
        for term in postings:
            postings[term].sort(key=lambda x: x[0])
        
        # Create chunk metadata (without term_frequencies to save space)
        chunk_metadata = [
            {
                'id': c.id,
                'kind': c.kind,
                'file': c.file,
                'line_start': c.line_start,
                'line_end': c.line_end,
                'is_test': c.is_test,
                'token_count': c.token_count
            }
            for c in chunks
        ]
        
        # Sort by id
        chunk_metadata.sort(key=lambda x: x['id'])
        
        # Create id -> index mapping
        id_to_idx = {c.id: idx for idx, c in enumerate(chunks)}
        
        return cls(
            params=params,
            N=N,
            avgdl=avgdl,
            chunks=chunk_metadata,
            postings=dict(sorted(postings.items())),  # Sort by term
            index_content_hash=index_content_hash,
            file_sha1s=file_sha1s
        )
    
    def search(self, query_terms: List[str], k: int = 10) -> List[SearchHit]:
        """Search for chunks matching query terms.
        
        Args:
            query_terms: List of query terms (may contain duplicates)
            k: Maximum number of results to return
            
        Returns:
            List of SearchHit objects, sorted by (-score, symbol_id)
            
        Raises:
            ValueError: If query_terms is empty
        """
        if not query_terms:
            raise ValueError("Query cannot be empty")
        
        # Count query term frequencies
        query_tf = {}
        for term in query_terms:
            query_tf[term] = query_tf.get(term, 0) + 1
        
        # Get distinct terms with weights
        term_weights = {}
        for term, tf in query_tf.items():
            term_weights[term] = min(tf, QUERY_TERM_CAP)
        
        # Compute scores
        chunk_scores = {}  # chunk_idx -> (score, breakdown)
        
        for term, weight in term_weights.items():
            if term not in self.postings:
                continue
            
            # Compute IDF
            df = len(self.postings[term])
            idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
            
            # Process postings
            for chunk_idx, tf in self.postings[term]:
                chunk_len = self.chunks[chunk_idx]['token_count']
                
                # BM25 score contribution
                numerator = tf * (self.params.k1 + 1)
                denominator = tf + self.params.k1 * (
                    1 - self.params.b + self.params.b * chunk_len / self.avgdl
                )
                contribution = idf * (numerator / denominator) * weight
                
                if chunk_idx not in chunk_scores:
                    chunk_scores[chunk_idx] = (0.0, [])
                
                score, breakdown = chunk_scores[chunk_idx]
                chunk_scores[chunk_idx] = (
                    score + contribution,
                    breakdown + [{
                        'term': term,
                        'df': df,
                        'idf': round(idf, 6),
                        'tf': tf,
                        'weight': weight,
                        'contribution': round(contribution, 6)
                    }]
                )
        
        # Build results
        results = []
        for chunk_idx, (score, breakdown) in chunk_scores.items():
            if score > 0:  # Only return positive scores
                results.append((
                    score,
                    self.chunks[chunk_idx]['id'],
                    breakdown
                ))
        
        # Sort by (-score, symbol_id) for deterministic tie-breaking
        results.sort(key=lambda x: (-x[0], x[1]))
        
        # Limit to k results
        results = results[:k]
        
        # Create SearchHit objects
        hits = []
        for rank, (score, symbol_id, breakdown) in enumerate(results, 1):
            hits.append(SearchHit(
                symbol_id=symbol_id,
                rank=rank,
                score=round(score, 6),
                breakdown=breakdown
            ))
        
        return hits
    
    def save(self, path: Path) -> None:
        """Save index to JSON file.
        
        Args:
            path: Output path for bm25_index.json
        """
        data = {
            'schema_version': 'bm25-1.0',
            'index_content_hash': self.index_content_hash,
            'params': {
                'k1': self.params.k1,
                'b': self.params.b
            },
            'N': self.N,
            'avgdl': self.avgdl,
            'chunks': self.chunks,
            'postings': {
                term: postings_list
                for term, postings_list in self.postings.items()
            },
            'file_sha1s': self.file_sha1s
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True)
    
    @classmethod
    def load(cls, path: Path, index_json_path: Path, repo_root: Path) -> 'BM25Index':
        """Load index from JSON file with freshness validation.
        
        Args:
            path: Path to bm25_index.json
            index_json_path: Path to index.json
            repo_root: Repository root for freshness check
            
        Returns:
            BM25Index instance
            
        Raises:
            StaleIndexError: If content hash mismatches or files changed
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check index.json content hash
        with open(index_json_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        
        index_content_hash = index_data.get('content_hash')
        if index_content_hash != data['index_content_hash']:
            raise StaleIndexError(
                f"Index content hash mismatch: "
                f"expected {data['index_content_hash']}, "
                f"got {index_content_hash}"
            )
        
        # Check file freshness
        file_sha1s = data.get('file_sha1s', {})
        changed_files = []
        
        for file_path, expected_sha1 in file_sha1s.items():
            full_path = repo_root / file_path
            if not full_path.exists():
                changed_files.append(f"{file_path} (deleted)")
                continue
            
            actual_sha1 = sha1_file(full_path)
            if actual_sha1 != expected_sha1:
                changed_files.append(file_path)
        
        if changed_files:
            raise StaleIndexError(
                f"Source files changed: {', '.join(changed_files)}"
            )
        
        # Reconstruct index
        params = BM25Params(
            k1=data['params']['k1'],
            b=data['params']['b']
        )
        
        # Convert postings back to list of tuples
        postings = {
            term: [tuple(p) for p in postings_list]
            for term, postings_list in data['postings'].items()
        }
        
        return cls(
            params=params,
            N=data['N'],
            avgdl=data['avgdl'],
            chunks=data['chunks'],
            postings=postings,
            index_content_hash=data['index_content_hash'],
            file_sha1s=file_sha1s
        )
