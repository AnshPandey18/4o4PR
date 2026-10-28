"""Repository model - represents a GitHub repository."""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class Repository(Base):
    """
    GitHub repository model with clone tracking and metadata.
    
    Represents a GitHub repository tracked by a user, including:
    - Basic repository info (name, description, branch)
    - GitHub API metadata (ID, privacy)
    - Clone tracking (path, status, commit SHA)
    """
    
    __tablename__ = "repositories"
    
    # ========================================================================
    # Primary Key
    # ========================================================================
    id = Column(Integer, primary_key=True, index=True)
    
    # ========================================================================
    # Owner (Foreign Key)
    # ========================================================================
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # ========================================================================
    # GitHub API Metadata
    # ========================================================================
    github_id = Column(BigInteger, unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=False)  # owner/repo format
    description = Column(Text, nullable=True)  # Repository description
    default_branch = Column(String(100), default="main")  # Default branch from GitHub
    is_private = Column(Boolean, default=False)  # Private/public flag
    
    # ========================================================================
    # Clone Tracking
    # ========================================================================
    clone_path = Column(Text, nullable=True)  # Local filesystem path
    clone_status = Column(
        String(50),
        default="not_cloned",
        nullable=False,
        index=True
    )  # not_cloned, cloning, cloned, failed, updating
    cloned_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp of clone
    commit_sha = Column(String(64), nullable=True)  # SHA of the checked-out commit
    
    # ========================================================================
    # Status & Metadata
    # ========================================================================
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ========================================================================
    # Relationships
    # ========================================================================
    owner = relationship("User", back_populates="repositories")
    # pipeline_runs relationship will be added via backref from PipelineRun
    
    # ========================================================================
    # Methods
    # ========================================================================
    
    def __repr__(self):
        return f"<Repository(id={self.id}, full_name={self.full_name}, status={self.clone_status})>"
    
    @property
    def is_cloned(self) -> bool:
        """Check if repository is successfully cloned."""
        return self.clone_status == "cloned"
    
    @property
    def is_cloning(self) -> bool:
        """Check if repository is currently being cloned."""
        return self.clone_status == "cloning"
    
    @property
    def clone_failed(self) -> bool:
        """Check if clone operation failed."""
        return self.clone_status == "failed"
    
    def to_dict(self) -> dict:
        """Convert repository to dictionary (useful for API responses)."""
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "github_id": self.github_id,
            "full_name": self.full_name,
            "description": self.description,
            "default_branch": self.default_branch,
            "is_private": self.is_private,
            "clone_path": self.clone_path,
            "clone_status": self.clone_status,
            "cloned_at": self.cloned_at.isoformat() if self.cloned_at else None,
            "commit_sha": self.commit_sha,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

