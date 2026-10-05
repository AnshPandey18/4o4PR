"""Single-command orchestrator for the 4o4PR analysis-to-patch pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

from run_pipeline import load_local_env, main as pipeline_main


BACKEND_DIR = Path(__file__).parent.resolve()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_from_backend(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return str(path.resolve())


def build_pipeline_args() -> List[str]:
    """Build the sequential pipeline arguments from environment settings."""

    root = os.getenv("ORCHESTRATOR_ROOT", "tests/fixtures/sample_bugs")
    import_roots = os.getenv("ORCHESTRATOR_IMPORT_ROOTS", "src")
    args = ["run_pipeline.py", "--root", _resolve_from_backend(root)]

    for import_root in import_roots.split(","):
        import_root = import_root.strip()
        if import_root:
            args.extend(["--import-root", import_root])

    output_dir = os.getenv("ORCHESTRATOR_OUTPUT_DIR")
    if output_dir:
        args.extend(["--out-dir", _resolve_from_backend(output_dir)])

    run_id = os.getenv("ORCHESTRATOR_RUN_ID")
    if run_id:
        args.extend(["--run-id", run_id])

    config = os.getenv("ORCHESTRATOR_CONFIG")
    if config:
        args.extend(["--config", _resolve_from_backend(config)])

    if _env_bool("ORCHESTRATOR_VERBOSE", True):
        args.append("--verbose")

    # This is intentionally the final stage. It never applies generated patches.
    args.extend(["--generate-patches", "--patch-only"])
    return args


def main(argv: Optional[List[str]] = None) -> int:
    """Run all stages from the environment-configured project root."""

    load_local_env()
    original_argv = sys.argv
    try:
        sys.argv = list(argv) if argv is not None else build_pipeline_args()
        return pipeline_main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())