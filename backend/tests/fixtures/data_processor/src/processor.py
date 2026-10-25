"""Data processor module with class and functions."""

from constants import MIN_VALUE, MAX_VALUE, DEFAULT_BATCH_SIZE, AGGREGATION_SUM, AGGREGATION_AVG


class DataProcessor:
    """Process and filter data."""
    
    def __init__(self, data: list):
        """Initialize with data."""
        self.data = data
        self.processed = False
    
    def _validate(self, value):
        """Validate a single value.
        
        BUG: Returns True for any value (should check MIN_VALUE and MAX_VALUE).
        """
        return True  # Should be: MIN_VALUE <= value <= MAX_VALUE
    
    def _compare(self, a, b):
        """Compare two values for sorting.
        
        BUG: Always returns wrong comparison.
        """
        return 1  # Should be: -1 if a < b, 0 if a == b, 1 if a > b
    
    def filter(self):
        """Filter data keeping only valid values."""
        result = []
        for value in self.data:
            # Calls _validate
            if self._validate(value):
                result.append(value)
        return result
    
    def sort(self):
        """Sort data using custom comparison.
        
        Calls _compare method.
        """
        sorted_data = self.data.copy()
        # Uses _compare for sorting
        for i in range(len(sorted_data)):
            for j in range(i + 1, len(sorted_data)):
                if self._compare(sorted_data[i], sorted_data[j]) > 0:
                    sorted_data[i], sorted_data[j] = sorted_data[j], sorted_data[i]
        return sorted_data
    
    def process(self):
        """Process data by filtering and sorting."""
        filtered = self.filter()
        sorted_data = self.sort()
        self.processed = True
        return sorted_data


def aggregate(data: list, aggregation_type: str):
    """Aggregate data using specified method.
    
    Calls DataProcessor methods.
    """
    processor = DataProcessor(data)
    
    # Process data first
    processed = processor.process()
    
    if not processed:
        return None
    
    if aggregation_type == AGGREGATION_SUM:
        return sum(processed)
    elif aggregation_type == AGGREGATION_AVG:
        # BUG: Uses len(data) instead of len(processed)
        return sum(processed) / len(data)  # Should be: len(processed)
    elif aggregation_type == AGGREGATION_MAX:
        return max(processed) if processed else None
    elif aggregation_type == AGGREGATION_MIN:
        return min(processed) if processed else None
    
    return None


def batch_process(data: list, batch_size: int = DEFAULT_BATCH_SIZE):
    """Process data in batches."""
    results = []
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        # Calls aggregate function
        result = aggregate(batch, AGGREGATION_AVG)
        results.append(result)
    return results
