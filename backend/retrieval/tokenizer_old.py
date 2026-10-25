"""Tokenizer for BM25 lexical search.

Tokenizes source code identifiers with camelCase/PascalCase splitting,
stopword filtering, and light stemming.
"""

import re
from typing import List, Set

# Configuration
MIN_TOKEN_LEN = 2
STEM_ENABLED = True
INCLUDE_COMMENTS = True

# Stopwords (applied to split pieces AND full identifiers)
STOPWORDS: Set[str] = {
    'def', 'return', 'self', 'cls', 'if', 'else', 'elif',
    'for', 'in', 'is', 'not', 'and', 'or', 'import', 'from',
    'as', 'none', 'true', 'false', 'pass', 'try', 'except',
    'with', 'while', 'lambda', 'the', 'of', 'to', 'a', 'an'
}


def _split_identifier(identifier: str) -> List[str]:
    """Split an identifier into subwords.
    
    Handles camelCase, PascalCase, ACRONYMS, and letter/digit boundaries.
    
    Examples:
        count_vowels -> ['count', 'vowels', 'count_vowels']
        VOWELS -> ['vowels']
        isPalindrome -> ['is', 'palindrome', 'ispalindrome']
        HTTPResponse -> ['http', 'response', 'httpresponse']
        parseHTTPResponse2 -> ['parse', 'http', 'response', '2', 'parsehttpresponse2']
    
    Args:
        identifier: The identifier string to split
        
    Returns:
        List of lowercase tokens including split pieces and full identifier
    """
    if not identifier:
        return []
    
    pieces = []
    
    # Split on underscores and other non-alphanumeric
    parts = re.split(r'[^a-zA-Z0-9]+', identifier)
    
    # Track if we had multiple parts (underscore-separated)
    has_multiple_parts = len([p for p in parts if p]) > 1
    
    for part in parts:
        if not part:
            continue
        
        # Find camelCase/PascalCase boundaries
        # Pattern matches:
        # - Lowercase followed by uppercase (camelCase)
        # - Multiple uppercase followed by uppercase then lowercase (ACRONYM)
        # - Letter followed by digit or digit followed by letter
        subparts = re.sub(
            r'([a-z])([A-Z])|([A-Z]+)([A-Z][a-z])|([a-zA-Z])(\d)|(\d)([a-zA-Z])',
            r'\1\3\5\7 \2\4\6\8',
            part
        ).split()
        
        if len(subparts) > 1:
            # Part had camelCase splits, emit the pieces
            pieces.extend(subparts)
        else:
            # No camelCase split, just emit the part
            pieces.extend(subparts)
    
    # If we had multiple underscore-separated parts OR camelCase splits,
    # add the full identifier
    if has_multiple_parts or len(pieces) > 1:
        # Reconstruct from original, lowercased
        pieces.append(identifier.lower())
    
    return [p.lower() for p in pieces if p]


def _stem(word: str) -> str:
    """Apply light stemming rules.
    
    Rules (applied only when result >= 3 chars):
    - ies -> y
    - es removed only when remaining stem > 3 characters
    - s removed when word > 3 chars and doesn't end in ss
    - ed and ing removed when remaining stem >= 3 characters
    
    Examples:
        validates -> validate
        validate -> validate
        lengths -> length
        process -> process (no change, would be too short)
        class -> class (ends in ss)
        
    Args:
        word: Word to stem
        
    Returns:
        Stemmed word
    """
    if not STEM_ENABLED:
        return word
    
    # ies -> y
    if word.endswith('ies') and len(word) > 4:
        return word[:-3] + 'y'
    
    # ed removed when remaining stem >= 3 characters
    if word.endswith('ed') and len(word) > 5:
        stem = word[:-2]
        if len(stem) >= 3:
            return stem
    
    # ing removed when remaining stem >= 3 characters
    if word.endswith('ing') and len(word) > 6:
        stem = word[:-3]
        if len(stem) >= 3:
            return stem
    
    # es removed only when remaining stem > 3 characters  
    # BUT: check for 'ates' pattern first (validates -> validate not validat)
    if word.endswith('ates') and len(word) > 5:
        # Just remove the 's', not 'es'
        return word[:-1]
    
    if word.endswith('es') and len(word) > 5:
        stem = word[:-2]
        if len(stem) > 3:
            return stem
    
    # s removed when word > 3 chars and doesn't end in ss
    if word.endswith('s') and len(word) > 3 and not word.endswith('ss'):
        return word[:-1]
    
    return word


def tokenize(text: str) -> List[str]:
    """Tokenize text into a list of lowercase tokens.
    
    Process:
    1. Split on non-alphanumeric characters into raw identifiers
    2. For each raw identifier, call _split_identifier which:
       - Splits camelCase/PascalCase/underscore boundaries
       - Returns pieces + full identifier if it had splits
    3. Drop tokens shorter than MIN_TOKEN_LEN
    4. Filter stopwords (applies to split pieces AND full identifiers)
    5. Apply stemming to split pieces (NOT to full identifiers)
    6. Return tokens in order of first occurrence, preserving duplicates
    
    Args:
        text: Source text to tokenize
        
    Returns:
        List of tokens in order (duplicates preserved)
    """
    if not text:
        return []
    
    tokens = []
    
    # Find all alphanumeric sequences (including underscores)
    # We need to preserve underscores so _split_identifier can see them
    identifiers = re.findall(r'[a-zA-Z0-9_]+', text)
    
    for identifier in identifiers:
        if not identifier:
            continue
        
        # Split the identifier (handles underscores, camelCase, etc.)
        split_tokens = _split_identifier(identifier)
        
        if not split_tokens:
            continue
        
        # If split_identifier returned multiple tokens, the last one is the full identifier
        has_full_id = len(split_tokens) > 1 and split_tokens[-1] == identifier.lower()
        
        # Process split pieces
        for i, token in enumerate(split_tokens):
            # Check if this is the full identifier (last token when has_full_id)
            is_full_identifier = has_full_id and i == len(split_tokens) - 1
            
            # Skip tokens that are too short
            if len(token) < MIN_TOKEN_LEN:
                continue
            
            # Apply stopword filter
            if token in STOPWORDS:
                continue
            
            # Apply stemming (only to split pieces, not full identifiers)
            if not is_full_identifier:
                token = _stem(token)
                # Recheck length and stopwords after stemming
                if len(token) < MIN_TOKEN_LEN or token in STOPWORDS:
                    continue
            
            tokens.append(token)
    
    return tokens
