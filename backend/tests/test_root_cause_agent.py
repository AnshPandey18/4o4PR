import json

import pytest

from analysis.root_cause_agent import RootCauseAnalysisAgent, RootCauseAnalysisError


def valid_payload():
    return {
        "bug_ids": ["bug-1"],
        "verdict": "source_bug",
        "faulty_location": {
            "file": "src/calculator.py",
            "qualified_name": "subtract",
            "line_start": 10,
            "line_end": 10,
        },
        "root_cause": "The function adds operands instead of subtracting them.",
        "evidence": [
            {
                "file": "tests/test_calculator.py",
                "line": 8,
                "observation": "The test expected 2 but received 8.",
            }
        ],
        "fix_strategy": "Replace addition with subtraction.",
        "affected_symbols": [],
        "blast_radius": "low",
        "confidence": 0.98,
        "needs_more_context": [],
        "assumptions": [],
    }


def test_analyze_accepts_json_and_does_not_need_files():
    payload = valid_payload()
    agent = RootCauseAnalysisAgent(client=lambda prompt: json.dumps(payload))

    result = agent.analyze("all evidence is already in this prompt")

    assert result.verdict == "source_bug"
    assert result.faulty_location.file == "src/calculator.py"
    assert result.to_dict()["confidence"] == 0.98


def test_analyze_accepts_fenced_json():
    response = "```json\n" + json.dumps(valid_payload()) + "\n```"

    result = RootCauseAnalysisAgent(client=lambda prompt: response).analyze("context")

    assert result.bug_ids == ["bug-1"]


@pytest.mark.parametrize("response", ["", "{}", "not json"])
def test_analyze_rejects_invalid_model_output(response):
    with pytest.raises(RootCauseAnalysisError):
        RootCauseAnalysisAgent(client=lambda prompt: response).analyze("context")


def test_analyze_rejects_empty_prompt():
    with pytest.raises(RootCauseAnalysisError):
        RootCauseAnalysisAgent(client=lambda prompt: "{}").analyze(" ")
