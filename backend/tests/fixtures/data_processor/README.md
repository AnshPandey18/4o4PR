# Data Processor - Medium Complexity Sample

## Overview
Data processing module with class methods, function calls, and constants.

## Features
- Class definitions with methods
- Methods calling other methods
- Functions calling other functions
- Constants used across modules
- Multi-level call chains

## Bugs
1. `DataProcessor.filter()` calls `_validate()` but validation logic is incorrect
2. `DataProcessor.sort()` calls `_compare()` with wrong comparison
3. `aggregate()` function calls `DataProcessor.process()` but processes data incorrectly
4. Constants `MIN_VALUE` and `MAX_VALUE` used but range checks are wrong

## Learning Goals
- Class and method extraction
- Call graph with multiple levels
- References to module-level constants from methods
- Cross-file function calls
