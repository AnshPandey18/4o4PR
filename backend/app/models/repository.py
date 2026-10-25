"""Repository model - represents a GitHub repository."""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class Repository(Base):
    """
    GitHub repository model with clone tracking and metadata.
    
    Represents a GitHub repository tracked by a user, including:
    - Basic repository info (name, URL, branch)
    - GitHub API metadata (stars, language, privacy)
    - Clone tracking (path, status, size)
    - Encrypted PAT storage for authentication
    """
    
    __tablename__ = "repositories"
    
    # ========================================================================
    # Primary Key
    # ========================================================================
    id = Column(Integer, primary_key=True, index=True)
    
    # ========================================================================
    # Basic Repository Info
    # ========================================================================
    name = Column(String, nullable=False)  # e.g., "owner/repo"
    url = Column(String, nullable=False)   # Full GitHub URL
    branch = Column(String, default="main")  # Branch to track/clone
    description = Column(Text, nullable=True)  # Repository description
    
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
    # GitHub API Metadata (fetched from GitHub)
    # ========================================================================
    github_id = Column(BigInteger, unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=True)  # owner/repo format
    owner_login = Column(String(255), nullable=True, index=True)  # GitHub username
    repo_name = Column(String(255), nullable=True)  # Repository name only
    default_branch = Column(String(100), default="main")  # Default branch from GitHub
    is_private = Column(Boolean, default=False)  # Private/public flag
    stars_count = Column(Integer, default=0)  # Star count
    language = Column(String(100), nullable=True)  # Primary language
    
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
    clone_size_mb = Column(Numeric(10, 2), nullable=True)  # Size in megabytes
    commit_sha = Column(String(64), nullable=True)  # SHA of the checked-out commit
    
    # ========================================================================
    # Redis Cache
    # ========================================================================
    redis_cache_key = Column(String(255), nullable=True)  # Format: clone:{user_id}:{repo_id}
    
    # ========================================================================
    # Security (Encrypted PAT)
    # ========================================================================
    encrypted_pat = Column(Text, nullable=True)  # Fernet-encrypted GitHub PAT
    
    # ========================================================================
    # Status & Metadata
    # ========================================================================
    is_active = Column(Boolean, default=True)
    last_scan = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ========================================================================
    # Relationships
    # ========================================================================
    owner = relationship("User", back_populates="repositories")
    # pipeline_runs relationship will be added when PipelineRun model is created
    
    # ========================================================================
    # Methods
    # ========================================================================
    
    def __repr__(self):
        return f"<Repository(id={self.id}, name={self.name}, status={self.clone_status})>"
    
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
    
    @property
    def repo_identifier(self) -> str:
        """Get repository identifier in owner/repo format."""
        return self.full_name or self.name
    
    def to_dict(self) -> dict:
        """Convert repository to dictionary (useful for API responses)."""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "branch": self.branch,
            "description": self.description,
            "owner_id": self.owner_id,
            "github_id": self.github_id,
            "full_name": self.full_name,
            "owner_login": self.owner_login,
            "repo_name": self.repo_name,
            "default_branch": self.default_branch,
            "is_private": self.is_private,
            "stars_count": self.stars_count,
            "language": self.language,
            "clone_path": self.clone_path,
            "clone_status": self.clone_status,
            "cloned_at": self.cloned_at.isoformat() if self.cloned_at else None,
            "clone_size_mb": float(self.clone_size_mb) if self.clone_size_mb else None,
            "commit_sha": self.commit_sha,
            "redis_cache_key": self.redis_cache_key,
            "is_active": self.is_active,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
