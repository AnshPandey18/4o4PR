"""Bug detection collectors.

TASK 4: Four collectors that identify potential bugs from different sources.
"""

from typing import List, Dict, Any

# Shared candidate record structure
def create_candidate(
    candidate_id: str,
    source: str,
    file: str,
    symbol: str,
    line_start: int,
    line_end: int,
    category: str,
    description: str,
    evidence: List[str],
    test_ids: List[str] = None,
    raw: Any = None
) -> Dict[str, Any]:
    """Create a standard candidate record.
    
    Args:
        candidate_id: Unique identifier
        source: pytest, ruff, heuristic, llm
        file: File path
        symbol: Qualified symbol name
        line_start: Start line
        line_end: End line
        category: Bug category
        description: Description
        evidence: List of evidence strings
        test_ids: List of test IDs (for pytest)
        raw: Original tool output
        
    Returns:
        Candidate dict
    """
    return {
        'candidate_id': candidate_id,
        'source': source,
        'file': file,
        'symbol': symbol,
        'line_start': line_start,
        'line_end': line_end,
        'category': category,
        'description': description,
        'evidence': evidence if evidence else [],
        'test_ids': test_ids if test_ids else [],
        'raw': raw
    }
