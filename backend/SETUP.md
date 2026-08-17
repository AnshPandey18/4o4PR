# Backend Setup Guide

## Installation

1. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

## Running Tests

Run all tests:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_bug_detector.py -v
```

Run with coverage:
```bash
pytest tests/ --cov=app --cov-report=html
```

## Running the Application

Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```

The API will be available at: `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Project Structure

```
backend/
├── app/
│   ├── agents/           # Core agent modules
│   │   ├── bug_detector.py      # Detects failing tests
│   │   ├── explainer.py          # Generates explanations
│   │   ├── patch_generator.py   # Creates fixes
│   │   └── test_validator.py    # Validates fixes
│   ├── api/              # FastAPI routes
│   │   ├── routes.py
│   │   └── dependencies.py
│   ├── models/           # Data models
│   │   └── schemas.py
│   ├── pipeline/         # Orchestration
│   │   ├── orchestrator.py
│   │   └── state.py
│   ├── tools/            # Utility modules
│   │   ├── claude_client.py
│   │   ├── github_client.py
│   │   ├── pytest_runner.py
│   │   ├── diff_utils.py
│   │   └── sandbox.py
│   └── utils/
│       └── logger.py
├── tests/                # Unit tests
├── examples/             # Usage examples
├── evaluation/           # Benchmarking
└── sandbox/              # Docker configs
```

## Testing the Bug Detector

### Quick Test

Create a test repository:

```python
# test_sample.py
def add(a, b):
    return a + b  # Bug: should return a - b

def test_add():
    assert add(5, 3) == 2  # This will fail
```

Run the bug detector:

```python
from app.agents import BugDetector

detector = BugDetector()
result = detector.run("/path/to/test/repo")

for bug in result.bugs:
    print(f"Found bug: {bug.test_name}")
    print(f"Error: {bug.error_message}")
    print(f"Code: {bug.failing_function_code}")
```

## Development

### Code Style

We follow PEP 8 guidelines. Format code with:
```bash
black app/
```

Check with:
```bash
flake8 app/
```

### Type Checking

Run mypy for type checking:
```bash
mypy app/
```

## Troubleshooting

### pytest not found
```bash
pip install pytest
```

### Import errors
Make sure you're in the backend directory and have installed requirements:
```bash
cd backend
pip install -r requirements.txt
```

### Docker issues
Ensure Docker is running:
```bash
docker --version
docker ps
```

## Next Steps

1. Test the Bug Detector module: `pytest tests/test_bug_detector.py -v`
2. Review the example: `python examples/bug_detector_example.py`
3. Implement the Patch Generator (Step 2 of the pipeline)
4. Set up the full orchestration pipeline
