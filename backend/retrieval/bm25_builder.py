"""BM25 index builder for schema 13 format.

TASK 3: Builds bm25_index.json from index.json symbols.
One chunk per symbol (including modules), excludes answer_keys.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any

from common.io import read_json, write_json
from retrieval.bm25 import BM25Index, BM25Params
from retrieval.bm25_chunks import build_chunks, get_searchable_chunks
from retrieval.tokenizer import tokenize

logger = logging.getLogger(__name__)


# TASK 3.5: Exclude answer keys
ANSWER_KEY_PATTERN = 'backend/tests/answer_keys'


class BM25Builder:
    """Builds BM25 index from schema 13 index.json.
    
    TASK 3.1-3.6: One chunk per symbol, excludes answer_keys, preserves query function.
    """
    
    def __init__(self):
        """Initialize BM25 builder."""
        self.params = BM25Params(k1=1.5, b=0.75)
    
    def build(self, index_path: Path, repo_root: Path) -> BM25Index:
        """Build BM25 index from index.json.
        
        TASK 3.2: Receives chunks of source, one per symbol (including modules).
        TASK 3.3: Tokenize → lowercase → stopwords → stem → TF → IDF.
        TASK 3.5: Exclude anything under backend/tests/answer_keys.
        
        Args:
            index_path: Path to index.json
            repo_root: Repository root path
            
        Returns:
            BM25Index instance
        """
        logger.info(f"Building BM25 index from {index_path}")
        
        # TASK 3.2: Build chunks from symbols (existing function handles schema 13)
        chunks = build_chunks(index_path, repo_root)
        
        # TASK 3.5: Filter out answer_keys
        filtered_chunks = []
        for chunk in chunks:
            file_path = chunk.file
            # Skip if file is under answer_keys
            if ANSWER_KEY_PATTERN in file_path.replace('\\', '/'):
                logger.debug(f"Excluding answer key file: {file_path}")
                continue
            filtered_chunks.append(chunk)
        
        logger.info(f"Built {len(filtered_chunks)} chunks (excluded {len(chunks) - len(filtered_chunks)} from answer_keys)")
        
        # ITEM 2.1: Build index with all chunks (tests included), filter at query time
        if not filtered_chunks:
            raise ValueError("No chunks found")
        
        # Load index for metadata
        index_data = read_json(index_path)
        index_content_hash = index_data.get('fingerprint', index_data.get('content_hash', ''))
        
        # Build file SHA1 map for freshness check
        file_sha1s = {}
        files = index_data.get('files', {})
        if isinstance(files, dict):
            for file_path, file_info in files.items():
                sha1 = file_info.get('sha1')
                if sha1:
                    file_sha1s[file_path] = sha1
        
        # TASK 3.3: Build BM25 index (existing function does tokenize→lowercase→stopwords→stem→TF→IDF)
        bm25_index = BM25Index.build(
            filtered_chunks,
            self.params,
            index_content_hash,
            file_sha1s
        )
        
        logger.info(f"BM25 index built: {bm25_index.N} chunks, avg length {bm25_index.avgdl:.1f} tokens")
        
        return bm25_index
    
    def save(self, bm25_index: BM25Index, output_path: Path) -> None:
        """TASK 3.4: Save BM25 index to bm25_index.json.
        
        Args:
            bm25_index: BM25Index instance
            output_path: Path to bm25_index.json
        """
        bm25_index.save(output_path)
        logger.info(f"Saved BM25 index to {output_path}")


def build_bm25_index(index_path: Path, repo_root: Path, output_path: Path) -> BM25Index:
    """Build and save BM25 index.
    
    Args:
        index_path: Path to index.json
        repo_root: Repository root path
        output_path: Path to bm25_index.json
        
    Returns:
        BM25Index instance
    """
    builder = BM25Builder()
    bm25_index = builder.build(index_path, repo_root)
    builder.save(bm25_index, output_path)
    return bm25_index
