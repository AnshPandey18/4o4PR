"""Validation script for repository index.

Checks index.json compliance with schema requirements:
1. No dangling symbol IDs
2. callees/callers and references/referenced_by mirror each other
3. No overlapping line ranges
4. Every import has same key set
5. unresolved_calls == len(unresolved)
6. test_to_source equals test entries in callees
7. run_id and generated_at have matching timestamps (UTC)
8. Every symbol has line_count, char_count, approx_tokens

Usage:
    python validate_index.py path/to/index.json
    python -c "from validate_index import validate_index; validate_index('index.json')"
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple
from datetime import datetime, timezone


def validate_index(index_path: str) -> Tuple[bool, List[str]]:
    """Validate an index.json file.
    
    Args:
        index_path: Path to index.json
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    try:
        with open(index_path) as f:
            index = json.load(f)
    except Exception as e:
        return False, [f"Failed to load index: {e}"]
    
    # Extract components
    symbols = index.get('symbols', {})
    files = index.get('files', {})
    call_graph = index.get('call_graph', {})
    test_to_source = index.get('test_to_source', {})
    run_id = index.get('run_id', '')
    generated_at = index.get('generated_at', '')
    parse_errors = index.get('parse_errors', [])
    
    callees = call_graph.get('callees', {})
    callers = call_graph.get('callers', {})
    references = call_graph.get('references', {})
    referenced_by = call_graph.get('referenced_by', {})
    
    # Validation 1: No dangling symbol IDs
    print("Checking for dangling symbol IDs...")
    all_symbol_ids = set(symbols.keys())
    for sym_id in list(callees.keys()) + list(callers.keys()) + list(references.keys()):
        if sym_id not in all_symbol_ids:
            errors.append(f"Dangling symbol in call_graph: {sym_id}")
    
    for test_id, source_ids in test_to_source.items():
        if test_id not in all_symbol_ids:
            errors.append(f"Dangling test ID in test_to_source: {test_id}")
        for source_id in source_ids:
            if source_id not in all_symbol_ids:
                errors.append(f"Dangling source ID in test_to_source: {source_id} (from {test_id})")
    
    # Validation 2: callees/callers mirror each other
    print("Checking callees/callers mirror...")
    for func_id, callee_list in callees.items():
        for callee_id in callee_list:
            if callee_id not in callers:
                errors.append(f"Callee {callee_id} not in callers (called by {func_id})")
            elif func_id not in callers[callee_id]:
                errors.append(f"Caller {func_id} not mirrored in callers[{callee_id}]")
    
    for func_id, caller_list in callers.items():
        for caller_id in caller_list:
            if caller_id not in callees:
                errors.append(f"Caller {caller_id} not in callees (calls {func_id})")
            elif func_id not in callees[caller_id]:
                errors.append(f"Callee {func_id} not mirrored in callees[{caller_id}]")
    
    # Validation 3: references/referenced_by mirror each other (if present)
    print("Checking references/referenced_by mirror...")
    for sym_id, ref_list in references.items():
        for ref_id in ref_list:
            if ref_id not in referenced_by:
                errors.append(f"Referenced {ref_id} not in referenced_by (from {sym_id})")
            elif sym_id not in referenced_by[ref_id]:
                errors.append(f"Referencing {sym_id} not mirrored in referenced_by[{ref_id}]")
    
    for ref_id, sym_list in referenced_by.items():
        for sym_id in sym_list:
            if sym_id not in references:
                errors.append(f"Referencing {sym_id} not in references (uses {ref_id})")
            elif ref_id not in references[sym_id]:
                errors.append(f"Referenced {ref_id} not mirrored in references[{sym_id}]")
    
    # Validation 4: No overlapping line ranges within files
    print("Checking for overlapping line ranges...")
    by_file: Dict[str, List[Tuple[int, int, str]]] = {}
    for sym_id, sym in symbols.items():
        file_path = sym.get('file')
        line_start = sym.get('line_start', 0)
        line_end = sym.get('line_end', 0)
        
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append((line_start, line_end, sym_id))
    
    for file_path, ranges in by_file.items():
        # Check file exists and has correct line count
        if file_path in files:
            file_lines = files[file_path].get('lines', 0)
            for line_start, line_end, sym_id in ranges:
                if line_end > file_lines and files[file_path].get('parse_ok', True):
                    errors.append(f"Symbol {sym_id} line_end ({line_end}) exceeds file lines ({file_lines})")
        
        # Check for overlaps (excluding parent classes which can have overlapping ranges with methods)
        ranges_sorted = sorted(ranges)
        for i in range(len(ranges_sorted) - 1):
            s1, e1, id1 = ranges_sorted[i]
            s2, e2, id2 = ranges_sorted[i + 1]
            # Allow overlap if one is a method (parent class)
            kind1 = symbols[id1].get('kind')
            kind2 = symbols[id2].get('kind')
            if e1 >= s2 and not (kind1 == 'class' and kind2 == 'method'):
                errors.append(f"Overlapping ranges: {id1} ({s1}-{e1}) and {id2} ({s2}-{e2})")
    
    # Validation 5: Every import has same key set
    print("Checking import key consistency...")
    required_import_keys = {'style', 'level', 'line', 'module', 'names', 'resolved_file'}
    for file_path, file_info in files.items():
        for imp in file_info.get('imports', []):
            imp_keys = set(imp.keys())
            if imp_keys != required_import_keys:
                missing = required_import_keys - imp_keys
                extra = imp_keys - required_import_keys
                if missing:
                    errors.append(f"Import in {file_path} missing keys: {missing}")
                if extra:
                    errors.append(f"Import in {file_path} has extra keys: {extra}")
            
            # Validate level is int
            if not isinstance(imp.get('level'), int):
                errors.append(f"Import in {file_path} has non-int level: {imp.get('level')}")
    
    # Validation 6: unresolved_calls == len(unresolved)
    print("Checking unresolved_calls counts...")
    for sym_id, sym in symbols.items():
        unresolved_count = sym.get('unresolved_calls', 0)
        unresolved_list = sym.get('unresolved', [])
        if unresolved_count != len(unresolved_list):
            errors.append(f"Symbol {sym_id}: unresolved_calls ({unresolved_count}) != len(unresolved) ({len(unresolved_list)})")
    
    # Validation 7: test_to_source matches test entries in callees
    print("Checking test_to_source...")
    for test_id, source_ids in test_to_source.items():
        # test_id should be a test function
        if test_id in symbols and not symbols[test_id].get('is_test', False):
            errors.append(f"test_to_source has non-test ID: {test_id}")
        
        # source_ids should match callees[test_id]
        test_callees = set(callees.get(test_id, []))
        test_sources = set(source_ids)
        if test_callees != test_sources:
            missing_in_test_to_source = test_callees - test_sources
            extra_in_test_to_source = test_sources - test_callees
            if missing_in_test_to_source:
                errors.append(f"test_to_source missing entries for {test_id}: {missing_in_test_to_source}")
            if extra_in_test_to_source:
                errors.append(f"test_to_source has extra entries for {test_id}: {extra_in_test_to_source}")
    
    # Validation 8: run_id and generated_at consistency (UTC)
    print("Checking UTC timestamp consistency...")
    
    # run_id format: r_YYYYMMDD_HHMMSS (if following convention)
    run_id_dt = None  # Initialize
    if not re.match(r'^r_\d{8}_\d{6}$', run_id):
        # Custom run_id is OK, just skip timestamp validation
        pass
    else:
        # Extract time from run_id
        try:
            date_part = run_id[2:10]  # YYYYMMDD
            time_part = run_id[11:17]  # HHMMSS
            run_id_dt = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
        except ValueError as e:
            errors.append(f"run_id timestamp is invalid: {run_id} ({e})")
            run_id_dt = None
    
    # generated_at should be ISO format with Z
    if not generated_at.endswith('Z'):
        errors.append(f"generated_at does not end with Z (not UTC): {generated_at}")
    else:
        try:
            # Parse ISO timestamp
            gen_dt_str = generated_at.replace('Z', '+00:00')
            gen_dt = datetime.fromisoformat(gen_dt_str)
            
            # Compare with run_id if both valid
            if run_id_dt:
                # Make run_id_dt timezone-aware for comparison
                if run_id_dt.tzinfo is None:
                    run_id_dt = run_id_dt.replace(tzinfo=timezone.utc)
                # Allow 1-second difference due to precision
                delta = abs((gen_dt - run_id_dt).total_seconds())
                if delta > 1:
                    errors.append(f"run_id and generated_at times differ by {delta}s (should be <1s)")
        except ValueError as e:
            errors.append(f"generated_at timestamp is invalid: {generated_at} ({e})")
    
    # Validation 9: Every symbol has metrics (line_count, char_count, approx_tokens)
    print("Checking symbol metrics...")
    for sym_id, sym in symbols.items():
        # Skip broken files
        if not files.get(sym.get('file'), {}).get('parse_ok', True):
            continue
        
        # Check required metrics
        has_line_count = 'line_count' in sym and isinstance(sym['line_count'], int)
        has_char_count = 'char_count' in sym and isinstance(sym['char_count'], int)
        has_approx_tokens = 'approx_tokens' in sym and isinstance(sym['approx_tokens'], int)
        
        if not has_line_count:
            errors.append(f"Symbol {sym_id} missing/invalid line_count")
        if not has_char_count:
            errors.append(f"Symbol {sym_id} missing/invalid char_count")
        if not has_approx_tokens:
            errors.append(f"Symbol {sym_id} missing/invalid approx_tokens")
    
    # Validation 10: Parse errors are documented
    print("Checking parse error handling...")
    broken_files = {path for path, info in files.items() if not info.get('parse_ok', True)}
    documented_broken = {err['file'] for err in parse_errors}
    
    if broken_files != documented_broken:
        missing_errors = broken_files - documented_broken
        if missing_errors:
            errors.append(f"Broken files not in parse_errors: {missing_errors}")
        extra_errors = documented_broken - broken_files
        if extra_errors:
            errors.append(f"parse_errors for non-broken files: {extra_errors}")
    
    # Summary
    is_valid = len(errors) == 0
    return is_valid, errors


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python validate_index.py <path/to/index.json>")
        sys.exit(1)
    
    index_path = sys.argv[1]
    is_valid, errors = validate_index(index_path)
    
    if is_valid:
        print(f"[OK] Index is valid!")
        sys.exit(0)
    else:
        print(f"[FAIL] Index has {len(errors)} errors:")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
