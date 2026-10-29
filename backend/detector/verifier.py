"""Candidate verifier - TASK 4.7.

Generates reproduction tests and runs them to verify candidates.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from common.io import ensure_dir, write_text

logger = logging.getLogger(__name__)


class CandidateVerifier:
    """TASK 4.7: Verifies candidates by generating and running reproduction tests."""
    
    def __init__(self, repo_root: Path, run_dir: Path):
        """Initialize verifier.
        
        Args:
            repo_root: Repository root path
            run_dir: Run directory for outputs
        """
        self.repo_root = repo_root
        self.run_dir = run_dir
        self.repro_dir = run_dir / 'repro'
        ensure_dir(self.repro_dir)
    
    def verify(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """TASK 4.7: Verify a candidate.
        
        Args:
            candidate: Candidate dict
            
        Returns:
            Updated candidate with verification result
        """
        source = candidate.get('source', '')
        
        # ITEM 2.1: pytest candidates - already confirmed with evidence from pytest_report.json
        if source == 'pytest':
            # Get test failure from pytest_report and candidate raw data
            test_assertion = "N/A"
            test_file = ""
            test_line = 0
            
            # First try to get from candidate's raw data
            if 'raw' in candidate and 'call' in candidate['raw']:
                call_data = candidate['raw']['call']
                if 'crash' in call_data:
                    crash = call_data['crash']
                    test_assertion = crash.get('message', 'N/A')
                    test_file = crash.get('path', '')
                    test_line = crash.get('lineno', 0)
            
            # Fallback to pytest_report if raw data doesn't have it
            if test_assertion == "N/A":
                pytest_report_path = self.run_dir / 'detector' / 'pytest_report.json'
                if pytest_report_path.exists():
                    from common.io import read_json
                    pytest_data = read_json(pytest_report_path)
                    test_name = candidate.get('test_name', candidate.get('test_ids', [''])[0])
                    # Find matching test failure
                    for test in pytest_data.get('tests', []):
                        if test.get('nodeid') == test_name and test.get('outcome') == 'failed':
                            call_data = test.get('call', {})
                            crash = call_data.get('crash', {})
                            test_assertion = crash.get('message', 'N/A')
                            test_file = crash.get('path', '')
                            test_line = crash.get('lineno', 0)
                            break
            
            # Build verification reason with assertion
            if test_file:
                # Extract just the file name from the full path
                from pathlib import Path
                test_file_name = Path(test_file).name
                candidate['verified'] = 'confirmed'
                candidate['verification_reason'] = f"Test assertion: {test_assertion} at {test_file_name} line {test_line}"
            else:
                candidate['verified'] = 'confirmed'
                candidate['verification_reason'] = f"Test assertion: {test_assertion}"
            
            return candidate
        
        # ITEM 2.2: ruff candidates - set to not_applicable (lint issues, not bugs)
        if source == 'ruff':
            candidate['verified'] = 'not_applicable'
            candidate['verification_reason'] = 'Lint finding, not a bug'
            return candidate
        
        # ITEM 2.3: llm candidates - generate test and verify
        if source == 'llm':
            # Check LLM kill switch
            if os.getenv('LLM_DISABLED') == '1':
                candidate['verified'] = 'unconfirmed'
                candidate['verification_reason'] = 'LLM disabled'
                return candidate
            
            candidate_id = candidate['candidate_id']
            
            logger.debug(f"Verifying LLM candidate {candidate_id}")
            
            # Generate reproduction test
            repro_test = self._generate_repro_test(candidate)
            
            if not repro_test:
                candidate['verified'] = 'unconfirmed'
                candidate['verification_reason'] = 'Failed to generate reproduction test'
                return candidate
            
            # Save test
            test_dir = self.repro_dir / candidate_id
            ensure_dir(test_dir)
            test_file = test_dir / 'test_repro.py'
            write_text(test_file, repro_test)
            
            # Run reproduction test
            result = self._run_repro_test(test_file)
            
            # Mark confirmed only when test fails with assertion/exception from suspect code
            if result['status'] == 'failed':
                candidate['verified'] = 'confirmed'
                candidate['verification_reason'] = 'Reproduction test failed as expected'
            else:
                candidate['verified'] = 'unconfirmed'
                candidate['verification_reason'] = result['reason']
            
            candidate['repro_test_path'] = str(test_file)
            candidate['repro_output'] = result.get('output', '')[:500]
            
            return candidate
        
        # Default for other sources (heuristic, etc.)
        candidate['verified'] = 'unconfirmed'
        candidate['verification_reason'] = 'No verification method for source type'
        return candidate
    
    def _generate_repro_test(self, candidate: Dict[str, Any]) -> Optional[str]:
        """TASK 4.7.1: Generate reproduction test (placeholder).
        
        In real implementation, would use LLM to generate test that:
        1. Imports the suspect module
        2. Calls the suspect symbol with inputs designed to expose the bug
        3. Asserts expected behavior or catches expected exception
        
        Args:
            candidate: Candidate dict
            
        Returns:
            Test source code or None
        """
        # Placeholder: Generate a simple template test
        # Real implementation would use LLM
        
        symbol = candidate.get('symbol', '')
        file = candidate.get('file', '')
        description = candidate.get('description', '')
        
        # Simple template (would be LLM-generated in real implementation)
        test_code = f'''"""
Reproduction test for candidate {candidate['candidate_id']}

Description: {description}
Symbol: {symbol}
File: {file}
"""

import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

def test_reproduction():
    """Attempt to reproduce the suspected bug."""
    # Placeholder: Real test would be LLM-generated
    # This is a dummy test that always passes
    assert True  # Would contain actual reproduction logic
'''
        
        return test_code
    
    def _run_repro_test(self, test_file: Path) -> Dict[str, Any]:
        """TASK 4.7.2: Run reproduction test with pytest.
        
        Args:
            test_file: Path to test file
            
        Returns:
            Result dict with status, reason, output
        """
        try:
            cmd = ['pytest', str(test_file), '-v', '--tb=short']
            
            result = subprocess.run(
                cmd,
                cwd=self.run_dir,
                capture_output=True,
                text=True,
                timeout=60  # TASK 4.7.2: 60-second timeout
            )
            
            output = result.stdout + result.stderr
            
            if result.returncode != 0:
                # Test failed - check if it's assertion or exception
                if 'AssertionError' in output or 'Exception' in output:
                    return {
                        'status': 'failed',
                        'reason': 'Test failed with expected error',
                        'output': output
                    }
                elif 'ImportError' in output or 'ModuleNotFoundError' in output:
                    return {
                        'status': 'unconfirmed',
                        'reason': 'Import error',
                        'output': output
                    }
                elif 'SyntaxError' in output:
                    return {
                        'status': 'unconfirmed',
                        'reason': 'Syntax error in generated test',
                        'output': output
                    }
                else:
                    return {
                        'status': 'unconfirmed',
                        'reason': 'Test failed unexpectedly',
                        'output': output
                    }
            else:
                # Test passed
                return {
                    'status': 'passed',
                    'reason': 'Test passed (bug not reproduced)',
                    'output': output
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'unconfirmed',
                'reason': 'Test timed out',
                'output': ''
            }
        except Exception as e:
            return {
                'status': 'unconfirmed',
                'reason': f'Error running test: {e}',
                'output': ''
            }


def verify_candidates(
    candidates: list[Dict[str, Any]],
    repo_root: Path,
    run_dir: Path
) -> List[Dict[str, Any]]:
    """Verify all candidates.
    
    Args:
        candidates: List of candidate dicts
        repo_root: Repository root
        run_dir: Run directory
        
    Returns:
        List of verified candidates
    """
    verifier = CandidateVerifier(repo_root, run_dir)
    
    verified = []
    for candidate in candidates:
        verified_candidate = verifier.verify(candidate)
        verified.append(verified_candidate)
    
    return verified
