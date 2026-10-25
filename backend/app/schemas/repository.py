"""Pydantic schemas for Repository API."""
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================================
# Repository Schemas
# ============================================================================

class RepositoryCreate(BaseModel):
    """Schema for creating a new repository."""
    url: str = Field(..., description="GitHub repository URL (https://github.com/owner/repo)")
    branch: Optional[str] = Field(default="main", description="Branch to track")
    personal_access_token: Optional[str] = Field(default=None, description="GitHub PAT (for private repos)")
    description: Optional[str] = Field(default=None, description="Repository description")
    
    @validator("url")
    def validate_url(cls, v):
        """Validate repository URL format."""
        if not v:
            raise ValueError("URL cannot be empty")
        # Basic validation (more done in GitHubClient)
        if "github.com" not in v and "/" not in v:
            raise ValueError("Invalid GitHub repository URL")
        return v.strip()


class RepositoryOnboardRequest(BaseModel):
    """Schema for the unified repository onboarding request."""
    url: str = Field(..., description="GitHub repository URL (https://github.com/owner/repo)")
    branch: Optional[str] = Field(default="main", description="Branch to clone")
    visibility: Optional[Literal["public", "private"]] = Field(
        default=None,
        description="Repository visibility. Inferred from the token when omitted.",
    )
    personal_access_token: Optional[str] = Field(
        default=None, description="GitHub PAT (required for private repos)"
    )
    import_roots: Optional[str] = Field(
        default=None, description="Comma-separated import roots for the pipeline"
    )
    verbose: bool = Field(default=True, description="Verbose pipeline output")

    @validator("url")
    def validate_url(cls, v):
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip()

    @validator("branch")
    def validate_branch(cls, v):
        if v is None:
            return "main"
        return v.strip()


class RepositoryUpdate(BaseModel):
    """Schema for updating repository info."""
    branch: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RepositoryResponse(BaseModel):
    """Schema for repository response."""
    id: int
    name: str
    url: str
    branch: str
    owner_id: int
    is_active: bool
    last_scan: Optional[datetime]
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # GitHub metadata (may be None if not yet fetched)
    github_id: Optional[int]
    full_name: Optional[str]
    owner_login: Optional[str]
    repo_name: Optional[str]
    default_branch: Optional[str]
    is_private: Optional[bool]
    stars_count: Optional[int]
    language: Optional[str]
    
    # Clone metadata
    clone_path: Optional[str]
    clone_status: Optional[str]
    cloned_at: Optional[datetime]
    clone_size_mb: Optional[float]
    redis_cache_key: Optional[str]
    commit_sha: Optional[str]
    
    class Config:
        from_attributes = True


class RepositoryListResponse(BaseModel):
    """Schema for list of repositories."""
    total: int
    repositories: list[RepositoryResponse]


class RepositoryOnboardResponse(BaseModel):
    """Response returned when a repository onboarding operation is accepted."""
    repository_id: int
    run_id: str
    status: str
    message: str
    repository: RepositoryResponse

    class Config:
        from_attributes = True


# ============================================================================
# Clone Operation Schemas
# ============================================================================

class CloneRequest(BaseModel):
    """Schema for clone repository request."""
    branch: Optional[str] = Field(default=None, description="Branch to clone (default: main/master)")
    force: bool = Field(default=False, description="Force reclone if already cloned")


class CloneResponse(BaseModel):
    """Schema for clone operation response."""
    repository_id: int
    clone_status: str
    clone_path: str
    clone_size_mb: float
    clone_duration_seconds: float
    cloned_at: str
    message: str


class CloneStatusResponse(BaseModel):
    """Schema for clone status check."""
    repository_id: int
    clone_status: str
    clone_path: Optional[str]
    cloned_at: Optional[datetime]
    clone_size_mb: Optional[float]
    cached: bool
    message: str


# ============================================================================
# Cache Schemas
# ============================================================================

class CacheStatsResponse(BaseModel):
    """Schema for Redis cache statistics."""
    connected: bool
    total_clone_keys: Optional[int]
    keyspace_hits: Optional[int]
    keyspace_misses: Optional[int]
    hit_rate: Optional[float]
    message: str
