import json

import pytest

from analysis.patch_generator import PatchGenerationError, PatchGenerator
from analysis.patch_applier import PatchApplicationError, PatchApplier


def patch_payload():
	return {
		"bug_ids": ["bug-1"],
		"target": {
			"file": "src/calculator.py",
			"qualified_name": "subtract",
			"line_start": 10,
			"line_end": 10,
		},
		"replacement_code": "def subtract(a, b):\n    return a - b",
		"rationale": "Use subtraction for the subtract contract.",
		"behavior_change": "Returns the difference instead of the sum.",
		"self_check": "subtract(5, 3) returns 2.",
	}


def test_patch_generator_validates_candidate_without_writing_files():
	generator = PatchGenerator(client=lambda prompt: json.dumps(patch_payload()))

	result = generator.generate(
		{"verdict": "source_bug", "root_cause": "wrong operator"},
		"source and test context",
	)

	assert result.target["qualified_name"] == "subtract"
	assert result.attempt == 1


def test_patch_generator_rejects_non_source_bug():
	generator = PatchGenerator(client=lambda prompt: json.dumps(patch_payload()))

	with pytest.raises(PatchGenerationError):
		generator.generate({"verdict": "unknown"}, "context")


def test_patch_applier_replaces_function_and_writes_diff(tmp_path):
	source = tmp_path / "src" / "calculator.py"
	source.parent.mkdir()
	source.write_text("def subtract(a, b):\n    return a + b\n", encoding="utf-8")
	payload = patch_payload()
	payload["target"]["line_start"] = 1
	payload["target"]["line_end"] = 2
	candidate = PatchGenerator._validate(payload, 1)

	result = PatchApplier().apply(tmp_path, candidate)

	assert result.changed is True
	assert "return a - b" in source.read_text(encoding="utf-8")
	assert "--- src/calculator.py" in result.diff


def test_patch_applier_rejects_test_targets(tmp_path):
	candidate_data = patch_payload()
	candidate_data["target"]["file"] = "tests/test_calculator.py"
	candidate = PatchGenerator._validate(candidate_data, 1)

	with pytest.raises(PatchApplicationError):
		PatchApplier().apply(tmp_path, candidate)
