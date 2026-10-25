"""Tests for data processor."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from processor import DataProcessor, aggregate, batch_process
from constants import MIN_VALUE, MAX_VALUE, AGGREGATION_SUM, AGGREGATION_AVG, AGGREGATION_MAX, DEFAULT_BATCH_SIZE


def test_filter_valid_data():
    """Test filtering keeps valid data.
    
    This should FAIL because _validate always returns True.
    """
    processor = DataProcessor([10, 20, 30, 40, 50])
    result = processor.filter()
    # Should filter based on MIN_VALUE and MAX_VALUE
    assert len(result) == 5
    assert all(MIN_VALUE <= v <= MAX_VALUE for v in result)


def test_filter_removes_invalid():
    """Test filtering removes out-of-range data.
    
    This should FAIL because _validate always returns True.
    """
    processor = DataProcessor([-10, 0, 50, 150, 200])
    result = processor.filter()
    # Should only keep values between MIN_VALUE and MAX_VALUE
    assert 150 not in result
    assert 200 not in result
    assert -10 not in result


def test_sort_ascending():
    """Test sorting in ascending order.
    
    This should FAIL because _compare is wrong.
    """
    processor = DataProcessor([50, 10, 40, 20, 30])
    result = processor.sort()
    assert result == [10, 20, 30, 40, 50]


def test_sort_descending():
    """Test sorting with negative numbers.
    
    This should FAIL because _compare is wrong.
    """
    processor = DataProcessor([3, 1, 4, 1, 5])
    result = processor.sort()
    assert result == [1, 1, 3, 4, 5]


def test_process():
    """Test complete processing pipeline.
    
    Should call both filter and sort.
    """
    processor = DataProcessor([50, 10, 40, 20, 30])
    result = processor.process()
    assert processor.processed == True
    assert isinstance(result, list)


def test_aggregate_sum():
    """Test sum aggregation."""
    result = aggregate([10, 20, 30, 40, 50], AGGREGATION_SUM)
    assert result == 150


def test_aggregate_avg():
    """Test average aggregation.
    
    This should FAIL due to division by len(data) vs len(processed).
    """
    result = aggregate([10, 20, 30, 40, 50], AGGREGATION_AVG)
    assert result == 30  # (10+20+30+40+50)/5


def test_aggregate_max():
    """Test max aggregation."""
    result = aggregate([10, 20, 30, 40, 50], AGGREGATION_MAX)
    assert result == 50


def test_aggregate_min():
    """Test min aggregation."""
    result = aggregate([10, 20, 30, 40, 50], AGGREGATION_MIN)
    assert result == 10


def test_batch_process():
    """Test batch processing."""
    data = list(range(100))
    result = batch_process(data, batch_size=20)
    assert len(result) == 5
