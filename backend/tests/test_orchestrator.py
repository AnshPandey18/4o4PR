import orchestrator


def test_build_pipeline_args_reads_environment(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_ROOT", "tests/fixtures/sample_bugs")
    monkeypatch.setenv("ORCHESTRATOR_IMPORT_ROOTS", "src,lib")
    monkeypatch.setenv("ORCHESTRATOR_VERBOSE", "false")

    args = orchestrator.build_pipeline_args()

    assert "--generate-patches" in args
    assert "--patch-only" in args
    assert "--apply-patches" not in args
    assert args[args.index("--import-root") + 1] == "src"
    assert args[args.index("--import-root", args.index("--import-root") + 1) + 1] == "lib"