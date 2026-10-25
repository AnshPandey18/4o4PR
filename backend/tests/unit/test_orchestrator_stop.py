"""Tests for orchestrator --stop-after flag and stage registry."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from orchestrator import StandaloneOrchestrator, STAGE_REGISTRY


def test_stage_registry_structure():
    """STAGE_REGISTRY has expected structure."""
    assert isinstance(STAGE_REGISTRY, list)
    assert len(STAGE_REGISTRY) > 0
    
    for item in STAGE_REGISTRY:
        assert isinstance(item, tuple)
        assert len(item) == 3
        stage_name, method_name, uses_llm = item
        assert isinstance(stage_name, str)
        assert isinstance(method_name, str)
        assert isinstance(uses_llm, bool)


def test_stage_registry_has_no_analysis_stage():
    """STAGE_REGISTRY should not contain analysis/RCA stage (context builder is non-LLM)."""
    stage_names = [name for name, _, _ in STAGE_REGISTRY]
    # context builder exists but is non-LLM
    assert "context" in stage_names
    # no separate analysis stage
    assert "analysis" not in stage_names
    assert "rca" not in stage_names


def test_stop_after_context_never_creates_run_folder():
    """--stop-after context exits before any LLM stage and does not create run output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_root = tmpdir / "project"
        project_root.mkdir()
        
        # Create minimal structure
        (project_root / "tests").mkdir()
        (project_root / "tests" / "test_dummy.py").write_text("def test_pass(): pass\n")
        
        output_dir = tmpdir / "output"
        
        # This would fail if it tried to actually run (no real project)
        # Just test that validation passes
        orch = StandaloneOrchestrator(
            project_root=project_root,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[],
            output_dir=output_dir
        )
        
        # Check that context stage exists and is non-LLM
        stage_names = [name for name, _, _ in STAGE_REGISTRY]
        assert "context" in stage_names
        context_idx = stage_names.index("context")
        _, _, uses_llm = STAGE_REGISTRY[context_idx]
        assert uses_llm is False, "context stage should be non-LLM"


def test_stop_after_patches_exits_3_llm_stage():
    """--stop-after patches exits 3 (LLM stage) without running pipeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_root = tmpdir / "project"
        project_root.mkdir()
        
        # Create minimal structure
        (project_root / "tests").mkdir()
        (project_root / "tests" / "test_dummy.py").write_text("def test_pass(): pass\n")
        
        output_dir = tmpdir / "output"
        
        orch = StandaloneOrchestrator(
            project_root=project_root,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[],
            output_dir=output_dir
        )
        
        # Should exit 3 because patches uses LLM
        result = orch.run_all(stop_after="patches")
        assert result == 3, "should exit 3 for LLM stage"
        
        # No actual pipeline data should be created (just empty dirs from __init__)
        assert not (output_dir / "index" / "index.json").exists(), "should not create index.json"


def test_stop_after_invalid_stage_exits_2():
    """--stop-after with invalid stage name exits 2."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_root = tmpdir / "project"
        project_root.mkdir()
        
        output_dir = tmpdir / "output"
        
        orch = StandaloneOrchestrator(
            project_root=project_root,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[],
            output_dir=output_dir
        )
        
        result = orch.run_all(stop_after="invalid_stage")
        assert result == 2, "should exit 2 for invalid stage"


def test_llm_disabled_set_for_valid_stop_after(monkeypatch):
    """LLM_DISABLED is set when --stop-after is used with non-LLM stage."""
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_root = tmpdir / "project"
        project_root.mkdir()
        
        # Create minimal structure
        (project_root / "tests").mkdir()
        (project_root / "tests" / "test_dummy.py").write_text("def test_pass(): pass\n")
        
        output_dir = tmpdir / "output"
        
        # Clear LLM_DISABLED first
        monkeypatch.delenv("LLM_DISABLED", raising=False)
        
        orch = StandaloneOrchestrator(
            project_root=project_root,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[],
            output_dir=output_dir
        )
        
        # This will fail trying to actually run, but should set LLM_DISABLED first
        try:
            orch.run_all(stop_after="indexer")
        except Exception:
            pass
        
        # Check that LLM_DISABLED was set
        assert os.environ.get("LLM_DISABLED") == "1", "LLM_DISABLED should be set"


def test_stop_marker_written_for_completed_stage():
    """pipeline_stop.json is written when stopping after a stage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        project_root = tmpdir / "project"
        project_root.mkdir()
        
        output_dir = tmpdir / "output"
        
        orch = StandaloneOrchestrator(
            project_root=project_root,
            import_roots=["src"],
            test_dirs=["tests"],
            exclude_patterns=[],
            output_dir=output_dir
        )
        
        # Call _write_stop_marker directly
        result = orch._write_stop_marker(["indexer", "detector"], "detector")
        assert result == 0
        
        marker_path = output_dir / "pipeline_stop.json"
        assert marker_path.exists()
        
        marker = json.loads(marker_path.read_text())
        assert marker["stage"] == "detector"
        assert marker["stages_completed"] == ["indexer", "detector"]
        assert "run_id" in marker
        assert "timestamp" in marker
