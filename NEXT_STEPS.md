# Next Steps - Bug Detector Complete ✅

## What You Have Now

✅ **Fully functional Bug Detector module**
- Detects failing tests in Python repositories
- Extracts complete code context
- Returns structured bug reports
- Handles edge cases gracefully
- Production-ready with comprehensive tests

## Immediate Actions (Day 1)

### 1. Verify Installation
```bash
cd backend
python verify_bug_detector.py
```
Expected: All checks should pass ✓

### 2. Review Documentation
- [ ] Read `backend/app/agents/QUICK_START.md` (5 minutes)
- [ ] Skim `backend/app/agents/README.md` (15 minutes)
- [ ] Review `BUG_DETECTOR_COMPLETE.md` (summary)

### 3. Run Tests
```bash
pytest tests/test_bug_detector.py -v
```
Expected: 25+ tests pass ✓

### 4. Try Example
```bash
python examples/bug_detector_example.py
```
(Update the repo path in the example first)

## Next Development Phase: Patch Generator (Step 2)

### Design Considerations

The Patch Generator should:

1. **Input**: Take `BugReport` objects from Bug Detector
2. **Process**: Use Claude API to generate fixes
3. **Output**: Return code patches

### Recommended Structure

```python
# backend/app/agents/patch_generator.py

from typing import List, Optional
from app.models.schemas import BugReport
from app.tools.claude_client import ClaudeClient

class PatchGenerator:
    """Generates code patches for detected bugs using AI."""
    
    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client
        self.bug_detector = BugDetector()
    
    def generate_patches(self, repo_path: str) -> List[Patch]:
        """Generate patches for all bugs in repository."""
        # Step 1: Detect bugs
        result = self.bug_detector.run(repo_path)
        
        if not result.has_failures:
            return []
        
        # Step 2: Generate patch for each bug
        patches = []
        for bug in result.bugs:
            patch = self._generate_patch_for_bug(bug)
            patches.append(patch)
        
        return patches
    
    def _generate_patch_for_bug(self, bug: BugReport) -> Patch:
        """Generate a patch for a single bug using Claude."""
        prompt = self._create_fix_prompt(bug)
        fixed_code = self.claude.generate_fix(prompt)
        
        return Patch(
            file_path=bug.file_path,
            line_number=bug.line_number,
            original_code=bug.failing_function_code,
            fixed_code=fixed_code,
            test_name=bug.test_name
        )
    
    def _create_fix_prompt(self, bug: BugReport) -> str:
        """Create a prompt for Claude to generate a fix."""
        return f"""
Fix the following bug:

Test that failed: {bug.test_name}
Error: {bug.error_type}: {bug.error_message}

Current code (BUGGY):
```python
{bug.failing_function_code}
```

Context before:
```python
{bug.context_before}
```

Context after:
```python
{bug.context_after}
```

Please provide ONLY the fixed function code, nothing else.
"""
```

### Implementation Steps

1. **Create Claude Client** (`backend/app/tools/claude_client.py`)
   - Initialize Anthropic client
   - Create method to send prompts
   - Handle API responses

2. **Create Patch Model** (add to `backend/app/models/schemas.py`)
   ```python
   @dataclass
   class Patch:
       file_path: str
       line_number: int
       original_code: str
       fixed_code: str
       test_name: str
   ```

3. **Implement Patch Generator** (`backend/app/agents/patch_generator.py`)
   - Use Bug Detector to find bugs
   - Use Claude to generate fixes
   - Return structured patches

4. **Write Tests** (`backend/tests/test_patch_generator.py`)
   - Mock Claude API responses
   - Test prompt generation
   - Test patch creation

5. **Create Diff Utils** (`backend/app/tools/diff_utils.py`)
   - Generate unified diffs
   - Apply patches to files
   - Validate patch format

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Bug Fixing Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐     ┌────────────┐ │
│  │ Bug Detector │  →   │    Patch     │  →  │    Test    │ │
│  │   (Step 1)   │      │  Generator   │     │ Validator  │ │
│  │      ✓       │      │   (Step 2)   │     │  (Step 3)  │ │
│  └──────────────┘      └──────────────┘     └────────────┘ │
│         ↓                     ↓                    ↓        │
│    BugReport             Patch              ValidationResult│
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Orchestrator (Step 4)                      │  │
│  │  - Coordinates all steps                             │  │
│  │  - Manages state                                     │  │
│  │  - Handles retries                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                            ↓                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           GitHub Integration (Step 5)                │  │
│  │  - Create branch                                     │  │
│  │  - Apply patches                                     │  │
│  │  - Generate PR with AI explanation                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Development Timeline

### Week 1
- [x] Day 1-2: Bug Detector ✓ **COMPLETE**
- [ ] Day 3-4: Patch Generator
- [ ] Day 5: Claude API integration

### Week 2
- [ ] Day 1-2: Test Validator
- [ ] Day 3: Docker sandbox for safe test execution
- [ ] Day 4-5: Pipeline Orchestrator

### Week 3
- [ ] Day 1-2: GitHub API integration
- [ ] Day 3: PR generation with explanations
- [ ] Day 4-5: FastAPI endpoints

### Week 4
- [ ] Day 1-2: Frontend (React)
- [ ] Day 3: Integration testing
- [ ] Day 4-5: SWE-bench evaluation

## Required API Keys

### Anthropic Claude API
```bash
# In backend/.env
ANTHROPIC_API_KEY=your_key_here
```
Get at: https://console.anthropic.com/

### GitHub API
```bash
# In backend/.env
GITHUB_TOKEN=your_token_here
```
Get at: https://github.com/settings/tokens

## Testing Strategy

### Unit Tests (Per Module)
- Test each component in isolation
- Mock external dependencies
- Cover edge cases

### Integration Tests
- Test Bug Detector → Patch Generator flow
- Test Patch Generator → Test Validator flow
- Test full pipeline end-to-end

### Evaluation
- Use SWE-bench dataset
- Measure success rate
- Compare with baselines

## Documentation Pattern

For each new module, create:
1. **Implementation** (`backend/app/agents/module.py`)
2. **Tests** (`backend/tests/test_module.py`)
3. **README** (`backend/app/agents/MODULE_README.md`)
4. **Examples** (`backend/examples/module_example.py`)

## Code Quality Checklist

For each module:
- [ ] Clean, DRY code
- [ ] Type annotations
- [ ] Docstrings
- [ ] Error handling
- [ ] Unit tests
- [ ] Integration tests
- [ ] Documentation
- [ ] Examples

## Resources

### Documentation
- Bug Detector: `backend/app/agents/README.md`
- Quick Start: `backend/app/agents/QUICK_START.md`
- Design: `docs/bug_detector_design.md`

### Examples
- Bug Detector usage: `backend/examples/bug_detector_example.py`
- Test patterns: `backend/tests/test_bug_detector.py`

### External Resources
- Anthropic Claude API: https://docs.anthropic.com/
- GitHub API: https://docs.github.com/en/rest
- SWE-bench: https://www.swebench.com/
- FastAPI: https://fastapi.tiangolo.com/

## Questions to Consider

### For Patch Generator
1. How to handle multiple possible fixes?
2. Should we generate multiple patch candidates?
3. How to validate patches before applying?
4. What if Claude generates invalid code?

### For Test Validator
1. How to safely run potentially broken code?
2. Docker container configuration?
3. Timeout for test execution?
4. How to handle environment dependencies?

### For Pipeline
1. Retry strategy for failures?
2. State management across steps?
3. Logging and monitoring?
4. Rate limiting for APIs?

## Success Criteria

### Minimum Viable Product (MVP)
- [x] Bug Detector works ✓
- [ ] Patch Generator creates fixes
- [ ] Test Validator runs tests safely
- [ ] Can fix simple bugs end-to-end
- [ ] Basic FastAPI endpoint

### Full Featured
- [ ] GitHub integration
- [ ] PR generation
- [ ] AI-generated explanations
- [ ] Frontend interface
- [ ] SWE-bench evaluation

### Production Ready
- [ ] Error handling everywhere
- [ ] Rate limiting
- [ ] Monitoring/logging
- [ ] Documentation complete
- [ ] Security review
- [ ] Performance optimization

## Getting Help

### If You're Stuck
1. Review the Bug Detector implementation as a reference
2. Check the design documents
3. Look at test patterns for examples
4. Start with simple cases first

### Common Pitfalls
- Don't try to build everything at once
- Start with happy path, add edge cases later
- Write tests as you go
- Document as you code

## Final Checklist

Before moving to Patch Generator:
- [ ] Bug Detector verified working
- [ ] All tests passing
- [ ] Documentation reviewed
- [ ] Example run successfully
- [ ] Understanding of integration points

## You're Ready! 🚀

The Bug Detector is complete and production-ready. You have:
- ✅ Clean, modular implementation
- ✅ Comprehensive tests
- ✅ Detailed documentation
- ✅ Clear integration points

Now you can confidently build the Patch Generator on this solid foundation.

**Good luck with your capstone project!**
