"""PipelineRun model - represents an orchestrator pipeline execution."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class PipelineRun(Base):
    """
    Pipeline run model for tracking orchestrator executions.
    
    Each run represents a complete execution of the 4o4PR orchestrator
    on a specific repository, including:
    - Input configuration (mode, ref, commit)
    - Execution tracking (start time, duration, status)
    - Results (bugs detected, patches generated)
    - Error tracking (if failed)
    """
    
    __tablename__ = "pipeline_runs"
    
    # ========================================================================
    # Primary Key
    # ========================================================================
    id = Column(Integer, primary_key=True, index=True)
    
    # ========================================================================
    # Foreign Keys
    # ========================================================================
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # ========================================================================
    # Run Status & Tracking
    # ========================================================================
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True
    )  # pending, queued, running, completed, failed, cancelled
    
    # ========================================================================
    # Input Configuration
    # ========================================================================
    input_mode = Column(String(50), nullable=True)  # e.g., "branch", "tag", "pr", "commit"
    input_ref = Column(String(255), nullable=True)  # e.g., "main", "v1.0.0", "123", "abc123..."
    commit_sha = Column(String(64), nullable=True)  # Actual commit SHA that was processed
    
    # ========================================================================
    # Execution Tracking
    # ========================================================================
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # ========================================================================
    # Results
    # ========================================================================
    bugs_detected = Column(Integer, default=0)
    bugs_fixed = Column(Integer, default=0)
    patches_generated = Column(Integer, default=0)
    
    # ========================================================================
    # Error Tracking
    # ========================================================================
    error_message = Column(Text, nullable=True)
    
    # ========================================================================
    # Background Task ID (for Celery/Redis)
    # ========================================================================
    task_id = Column(String(255), nullable=True, index=True)  # Celery task ID or similar
    
    # ========================================================================
    # Metadata
    # ========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # ========================================================================
    # Relationships
    # ========================================================================
    repository = relationship("Repository", backref="pipeline_runs")
    
    # ========================================================================
    # Methods
    # ========================================================================
    
    def __repr__(self):
        return f"<PipelineRun(id={self.id}, repository_id={self.repository_id}, status={self.status})>"
    
    @property
    def is_pending(self) -> bool:
        """Check if run is pending."""
        return self.status == "pending"
    
    @property
    def is_running(self) -> bool:
        """Check if run is currently executing."""
        return self.status == "running"
    
    @property
    def is_completed(self) -> bool:
        """Check if run completed successfully."""
        return self.status == "completed"
    
    @property
    def is_failed(self) -> bool:
        """Check if run failed."""
        return self.status == "failed"
    
    @property
    def is_cancelled(self) -> bool:
        """Check if run was cancelled."""
        return self.status == "cancelled"
    
    @property
    def is_finished(self) -> bool:
        """Check if run is finished (completed, failed, or cancelled)."""
        return self.status in ("completed", "failed", "cancelled")
    
    @property
    def success_rate(self) -> float:
        """Calculate bug fix success rate (0-100%)."""
        if self.bugs_detected == 0:
            return 0.0
        return round((self.bugs_fixed / self.bugs_detected) * 100, 2)
    
    def to_dict(self) -> dict:
        """Convert pipeline run to dictionary."""
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "status": self.status,
            "input_mode": self.input_mode,
            "input_ref": self.input_ref,
            "commit_sha": self.commit_sha,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "bugs_detected": self.bugs_detected,
            "bugs_fixed": self.bugs_fixed,
            "patches_generated": self.patches_generated,
            "success_rate": self.success_rate,
            "error_message": self.error_message,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

