# String Processor - Easy Complexity Sample

## Overview
Simple string processing module with function calls and constants.

## Features
- Constants used within functions
- Functions calling other functions
- Basic string operations with bugs
- Tests that reveal the bugs

## Bugs
1. `normalize_text` calls `_remove_punctuation` but bug in normalization
2. `validate_email` calls `_is_valid_domain` with incorrect logic
3. Constants `VALID_DOMAINS` and `MAX_LENGTH` are used but logic errors exist

## Learning Goals
- Function call tracking (normalize_text → _remove_punctuation)
- Constant usage tracking (VALID_DOMAINS, MAX_LENGTH)
- Simple call graph visualization
- References between functions and constants
