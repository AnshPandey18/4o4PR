"""Pydantic schemas for PipelineRun API."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================================
# PipelineRun Schemas
# ============================================================================

class PipelineRunCreate(BaseModel):
    """Schema for creating a new pipeline run."""
    repository_id: int = Field(..., description="Repository ID to run pipeline on")
    import_roots: Optional[str] = Field(default="src", description="Comma-separated import roots")
    output_dir: Optional[str] = Field(default=None, description="Output directory for results")
    config_file: Optional[str] = Field(default=None, description="Path to settings.yaml")
    verbose: bool = Field(default=True, description="Enable verbose logging")
    
    @validator("import_roots")
    def validate_import_roots(cls, v):
        """Validate import_roots format."""
        if v and not v.strip():
            raise ValueError("import_roots cannot be empty")
        return v.strip() if v else "src"


class PipelineRunUpdate(BaseModel):
    """Schema for updating pipeline run status/results."""
    status: Optional[str] = Field(default=None, description="Run status")
    bugs_detected: Optional[int] = Field(default=None, ge=0)
    bugs_fixed: Optional[int] = Field(default=None, ge=0)
    patches_generated: Optional[int] = Field(default=None, ge=0)
    error_message: Optional[str] = Field(default=None)
    error_traceback: Optional[str] = Field(default=None)
    
    @validator("status")
    def validate_status(cls, v):
        """Validate status value."""
        if v is not None:
            valid_statuses = ["pending", "queued", "running", "completed", "failed", "cancelled"]
            if v not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v


class PipelineRunResponse(BaseModel):
    """Schema for pipeline run response."""
    id: int
    repository_id: int
    user_id: int
    run_id: str
    status: str
    orchestrator_root: str
    import_roots: Optional[str]
    output_dir: Optional[str]
    config_file: Optional[str]
    verbose: bool
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    bugs_detected: int
    bugs_fixed: int
    patches_generated: int
    error_message: Optional[str]
    error_traceback: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Computed field
    success_rate: Optional[float] = Field(default=None, description="Bug fix success rate (%)")
    
    class Config:
        from_attributes = True


class PipelineRunListResponse(BaseModel):
    """Schema for list of pipeline runs."""
    total: int
    runs: list[PipelineRunResponse]


class PipelineRunStatsResponse(BaseModel):
    """Schema for pipeline run statistics."""
    total_runs: int
    pending_runs: int
    running_runs: int
    completed_runs: int
    failed_runs: int
    cancelled_runs: int
    total_bugs_detected: int
    total_bugs_fixed: int
    total_patches_generated: int
    average_success_rate: float
    average_duration_seconds: Optional[float]


# ============================================================================
# Run Control Schemas
# ============================================================================

class PipelineRunTriggerRequest(BaseModel):
    """Schema for triggering a new pipeline run."""
    repository_id: int = Field(..., description="Repository ID to analyze")
    import_roots: Optional[str] = Field(default="src", description="Comma-separated import roots (e.g., 'src,lib')")
    verbose: bool = Field(default=True, description="Enable verbose output")
    force_reclone: bool = Field(default=False, description="Force reclone even if cached")


class PipelineRunTriggerResponse(BaseModel):
    """Schema for pipeline run trigger response."""
    run_id: str
    repository_id: int
    status: str
    message: str
    orchestrator_root: str


class PipelineRunCancelRequest(BaseModel):
    """Schema for cancelling a pipeline run."""
    reason: Optional[str] = Field(default=None, description="Reason for cancellation")


class PipelineRunCancelResponse(BaseModel):
    """Schema for pipeline run cancel response."""
    run_id: str
    status: str
    message: str
