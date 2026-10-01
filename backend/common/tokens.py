"""Token counting utilities for LLM context budgeting.

Provides both estimate-based and tiktoken-based token counting.
"""

import math
from abc import ABC, abstractmethod
from typing import Optional


class TokenCounter(ABC):
    """Abstract base class for token counters."""
    
    @abstractmethod
    def count(self, text: str) -> int:
        """Count tokens in text.
        
        Args:
            text: Text to count tokens in
            
        Returns:
            Number of tokens
        """
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Get the name of this counter method.
        
        Returns:
            Counter method name (e.g., "estimate", "tiktoken")
        """
        pass


class EstimateTokenCounter(TokenCounter):
    """Simple estimate-based token counter.
    
    Uses the heuristic: tokens ≈ len(text) / 3.5 * 1.15
    The 1.15 factor provides a 15% safety margin.
    """
    
    def count(self, text: str) -> int:
        """Count tokens using character-based estimate.
        
        Args:
            text: Text to count tokens in
            
        Returns:
            Estimated number of tokens
        """
        if not text:
            return 0
        
        # tokens ≈ characters / 3.5 with 15% safety margin
        return math.ceil(len(text) / 3.5 * 1.15)
    
    def name(self) -> str:
        """Get counter method name."""
        return "estimate"


class TiktokenCounter(TokenCounter):
    """Tiktoken-based token counter (requires tiktoken package).
    
    More accurate but requires optional dependency.
    """
    
    def __init__(self, model: str = "gpt-4"):
        """Initialize tiktoken counter.
        
        Args:
            model: Model name for tokenizer (default: gpt-4)
            
        Raises:
            ImportError: If tiktoken is not installed
        """
        try:
            import tiktoken
            self.encoding = tiktoken.encoding_for_model(model)
        except ImportError:
            raise ImportError(
                "tiktoken is not installed. Install it with: pip install tiktoken"
            )
    
    def count(self, text: str) -> int:
        """Count tokens using tiktoken.
        
        Args:
            text: Text to count tokens in
            
        Returns:
            Exact number of tokens
        """
        if not text:
            return 0
        
        return len(self.encoding.encode(text))
    
    def name(self) -> str:
        """Get counter method name."""
        return "tiktoken"


def create_token_counter(method: str = "estimate", model: str = "gpt-4") -> TokenCounter:
    """Create a token counter instance.
    
    Args:
        method: Counter method ("estimate" or "tiktoken")
        model: Model name for tiktoken (ignored for estimate)
        
    Returns:
        TokenCounter instance
        
    Raises:
        ValueError: If method is unknown
        ImportError: If tiktoken method is requested but not installed
    """
    if method == "estimate":
        return EstimateTokenCounter()
    elif method == "tiktoken":
        return TiktokenCounter(model=model)
    else:
        raise ValueError(f"Unknown token counter method: {method}")


def count_tokens(text: str, method: str = "estimate") -> int:
    """Convenience function to count tokens.
    
    Args:
        text: Text to count tokens in
        method: Counter method ("estimate" or "tiktoken")
        
    Returns:
        Number of tokens
    """
    counter = create_token_counter(method)
    return counter.count(text)
