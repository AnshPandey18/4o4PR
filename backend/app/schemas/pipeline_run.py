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
    input_mode: Optional[str] = Field(default="branch", description="Run mode: branch, pr, or commit")
    input_ref: Optional[str] = Field(default=None, description="Branch name, PR URL, or commit SHA")
    commit_sha: Optional[str] = Field(default=None, description="Commit SHA to process")


class PipelineRunUpdate(BaseModel):
    """Schema for updating pipeline run status/results."""
    status: Optional[str] = Field(default=None, description="Run status")
    bugs_detected: Optional[int] = Field(default=None, ge=0)
    bugs_fixed: Optional[int] = Field(default=None, ge=0)
    patches_generated: Optional[int] = Field(default=None, ge=0)
    error_message: Optional[str] = Field(default=None)
    
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
    status: str
    input_mode: Optional[str]
    input_ref: Optional[str]
    commit_sha: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    bugs_detected: int
    bugs_fixed: int
    patches_generated: int
    error_message: Optional[str]
    task_id: Optional[str]
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
    repository_id: Optional[int] = Field(default=None, description="Repository ID to analyze (for branch/commit modes)")
    input_mode: str = Field(..., description="Run mode: 'branch', 'pr', or 'commit'")
    input_ref: str = Field(..., description="Branch name, PR URL, or commit SHA")
    import_roots: Optional[str] = Field(default="src", description="Comma-separated import roots (e.g., 'src,lib')")
    verbose: bool = Field(default=True, description="Enable verbose output")
    force_reclone: bool = Field(default=False, description="Force reclone even if cached")
    
    @validator("input_mode")
    def validate_input_mode(cls, v):
        """Validate input_mode value."""
        valid_modes = ["branch", "pr", "commit"]
        if v not in valid_modes:
            raise ValueError(f"Invalid input_mode. Must be one of: {', '.join(valid_modes)}")
        return v


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
