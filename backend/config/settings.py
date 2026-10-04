"""Settings management for 4o4PR pipeline.

Loads and validates configuration from settings.yaml.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class DetectorSettings:
    """Bug Detector configuration."""
    timeout_seconds: int = 300
    flaky_reruns: int = 2
    embed_source_snapshot: bool = True
    snapshot_max_lines: int = 80


@dataclass
class GrouperSettings:
    """Bug Grouper configuration."""
    max_bugs_per_group: int = 8


@dataclass
class ContextBudget:
    """Token budget for a context profile."""
    input_budget: int
    output_reserved: int


@dataclass
class ContextSettings:
    """Context Builder configuration."""
    analysis: ContextBudget
    fix: ContextBudget
    token_counter: str = "estimate"
    tiktoken_model: str = "gpt-4"
    tier_budgets: Dict[str, float] = field(default_factory=dict)
    redact_patterns: List[str] = field(default_factory=list)
    denylist_files: List[str] = field(default_factory=list)


@dataclass
class RunsSettings:
    """Run management configuration."""
    base_dir: str = "runs"
    max_runs_to_keep: int = 50


@dataclass
class CacheSettings:
    """Cache management configuration."""
    base_dir: str = "cache"
    enable_index_cache: bool = True
    max_age_days: int = 30


@dataclass
class LoggingSettings:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


@dataclass
class SchemaVersions:
    """Schema version numbers."""
    index: str = "1.0"
    bug_report: str = "2.0"
    bug_groups: str = "1.0"
    context_manifest: str = "1.0"
    baseline_results: str = "1.0"


@dataclass
class Settings:
    """Complete pipeline settings."""
    project_root: Path
    import_roots: List[str]
    test_dirs: List[str]
    exclude_dirs: List[str]
    detector: DetectorSettings
    grouper: GrouperSettings
    context: ContextSettings
    runs: RunsSettings
    cache: CacheSettings
    logging: LoggingSettings
    schema_versions: SchemaVersions
    
    @property
    def runs_dir(self) -> Path:
        """Get absolute path to runs directory."""
        return self.project_root / self.runs.base_dir
    
    @property
    def cache_dir(self) -> Path:
        """Get absolute path to cache directory."""
        return self.project_root / self.cache.base_dir
    
    def get_import_root_paths(self) -> List[Path]:
        """Get absolute paths for import roots."""
        return [self.project_root / root for root in self.import_roots]


def load_settings(config_path: Optional[Path] = None, project_root: Optional[Path] = None) -> Settings:
    """Load settings from YAML configuration file.
    
    Args:
        config_path: Path to settings.yaml (default: config/settings.yaml)
        project_root: Override project root from config file
        
    Returns:
        Settings object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    # Default config path
    if config_path is None:
        backend_dir = Path(__file__).parent.parent
        config_path = backend_dir / "config" / "settings.yaml"
    
    # Load YAML
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Determine project root
    if project_root is None:
        config_dir = Path(config_path).parent
        backend_dir = config_dir.parent
        root_from_config = config.get('project_root', '.')
        project_root = (backend_dir / root_from_config).resolve()
    else:
        # Ensure passed project_root is absolute
        project_root = Path(project_root).resolve()
    
    # Parse detector settings
    detector_config = config.get('detector', {})
    detector = DetectorSettings(
        timeout_seconds=detector_config.get('timeout_seconds', 300),
        flaky_reruns=detector_config.get('flaky_reruns', 2),
        embed_source_snapshot=detector_config.get('embed_source_snapshot', True),
        snapshot_max_lines=detector_config.get('snapshot_max_lines', 80)
    )
    
    # Parse grouper settings
    grouper_config = config.get('grouper', {})
    grouper = GrouperSettings(
        max_bugs_per_group=grouper_config.get('max_bugs_per_group', 8)
    )
    
    # Parse context settings
    context_config = config.get('context', {})
    analysis_budget = context_config.get('analysis', {})
    fix_budget = context_config.get('fix', {})
    
    context = ContextSettings(
        analysis=ContextBudget(
            input_budget=analysis_budget.get('input_budget', 10000),
            output_reserved=analysis_budget.get('output_reserved', 1500)
        ),
        fix=ContextBudget(
            input_budget=fix_budget.get('input_budget', 12000),
            output_reserved=fix_budget.get('output_reserved', 2000)
        ),
        token_counter=context_config.get('token_counter', 'estimate'),
        tiktoken_model=context_config.get('tiktoken_model', 'gpt-4'),
        tier_budgets=context_config.get('tier_budgets', {}),
        redact_patterns=context_config.get('redact_patterns', []),
        denylist_files=context_config.get('denylist_files', [])
    )
    
    # Parse runs settings
    runs_config = config.get('runs', {})
    runs = RunsSettings(
        base_dir=runs_config.get('base_dir', 'runs'),
        max_runs_to_keep=runs_config.get('max_runs_to_keep', 50)
    )
    
    # Parse cache settings
    cache_config = config.get('cache', {})
    cache = CacheSettings(
        base_dir=cache_config.get('base_dir', 'cache'),
        enable_index_cache=cache_config.get('enable_index_cache', True),
        max_age_days=cache_config.get('max_age_days', 30)
    )
    
    # Parse logging settings
    logging_config = config.get('logging', {})
    logging_settings = LoggingSettings(
        level=logging_config.get('level', 'INFO'),
        format=logging_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        file=logging_config.get('file')
    )
    
    # Parse schema versions
    schema_config = config.get('schema_versions', {})
    schema_versions = SchemaVersions(
        index=schema_config.get('index', '1.0'),
        bug_report=schema_config.get('bug_report', '2.0'),
        bug_groups=schema_config.get('bug_groups', '1.0'),
        context_manifest=schema_config.get('context_manifest', '1.0'),
        baseline_results=schema_config.get('baseline_results', '1.0')
    )
    
    # Create Settings object
    return Settings(
        project_root=project_root,
        import_roots=config.get('import_roots', ['src']),
        test_dirs=config.get('test_dirs', ['tests']),
        exclude_dirs=config.get('exclude_dirs', []),
        detector=detector,
        grouper=grouper,
        context=context,
        runs=runs,
        cache=cache,
        logging=logging_settings,
        schema_versions=schema_versions
    )


def setup_logging(settings: Settings) -> None:
    """Configure logging based on settings.
    
    Args:
        settings: Settings object
    """
    import logging
    
    # Set log level
    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    
    # Configure logging
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(settings.logging.format))
    handlers.append(console_handler)
    
    # File handler (if configured)
    if settings.logging.file:
        log_file = settings.project_root / settings.logging.file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(settings.logging.format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )
