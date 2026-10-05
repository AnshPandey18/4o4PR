from analysis.reporting import ExplanationGenerator, build_pr_body


def test_explanation_generator_uses_injected_client():
    generator = ExplanationGenerator(client=lambda prompt: "## Root Cause\nWrong operator")

    result = generator.generate({"verdict": "source_bug"})

    assert "Wrong operator" in result


def test_build_pr_body_is_deterministic():
    body = build_pr_body(
        {"G1": {"verdict": "source_bug", "faulty_location": {"file": "src/a.py", "line_start": 3}, "root_cause": "Wrong operator", "confidence": 0.9}},
        {"passed": True, "tests_run": 3, "failures": 0},
    )

    assert "src/a.py:3" in body
    assert "Status: `True`" in body