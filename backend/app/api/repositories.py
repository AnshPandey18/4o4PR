"""Repository management endpoints (GitHub Integration)."""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging
import subprocess
import sys
from pathlib import Path

from ..database import get_db
from ..models.user import User
from ..models.repository import Repository
from ..models.pipeline_run import PipelineRun
from ..schemas.repository import (
    RepositoryCreate,
    RepositoryUpdate,
    RepositoryResponse,
    RepositoryListResponse,
    RepositoryOnboardRequest,
    RepositoryOnboardResponse,
    CloneRequest,
    CloneResponse,
    CloneStatusResponse,
    CacheStatsResponse,
)
from ..utils.security import get_current_active_user
from ..tools.github_client import GitHubClient
from ..tools.redis_client import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["repositories"])

# Path to orchestrator_db.py
BACKEND_DIR = Path(__file__).parent.parent.parent.resolve()
ORCHESTRATOR_DB_PATH = BACKEND_DIR / "orchestrator_db.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from orchestrator_db import OrchestratorDB, execute_onboarding_task


# Statuses that mean a pipeline run is still in flight
ACTIVE_RUN_STATUSES = ("pending", "queued", "running")


# ============================================================================
# Repository Onboarding Endpoint
# ============================================================================

@router.post("/onboard", response_model=RepositoryOnboardResponse, status_code=status.HTTP_202_ACCEPTED)
def onboard_repository(
    repo_data: RepositoryOnboardRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Onboard a GitHub repository and start the pipeline for it.

    This is the single entry point used by the "Run Pipeline" button and
    replaces the previous two-step create/clone flow.

    The endpoint performs only short database work:
    1. Validates the repository configuration
    2. Persists (or reuses) the repository record
    3. Creates the pipeline run record
    4. Hands the clone and the pipeline execution to a background worker

    The actual pipeline state is observed through GET /api/pipeline-runs/{run_id}.
    """
    # ── 1. Validate the request ──────────────────────────────────────────
    is_valid, error_msg = GitHubClient.validate_repo_url(repo_data.url)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository URL: {error_msg}"
        )

    branch = (repo_data.branch or "main").strip()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch name cannot be empty"
        )

    pat = repo_data.personal_access_token
    visibility = repo_data.visibility or ("private" if pat else "public")

    if visibility == "private" and not pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A GitHub access token is required for private repositories"
        )

    if pat:
        is_valid, error_msg = GitHubClient.validate_pat(pat)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GitHub access token: {error_msg}"
            )

    try:
        # ── 2. Prevent conflicting duplicate submissions ─────────────────
        repo_identifier = GitHubClient._parse_repo_identifier(repo_data.url)
        existing_repo = db.query(Repository).filter(
            Repository.owner_id == current_user.id,
            Repository.name == repo_identifier
        ).first()

        if existing_repo:
            active_run = db.query(PipelineRun).filter(
                PipelineRun.repository_id == existing_repo.id,
                PipelineRun.status.in_(ACTIVE_RUN_STATUSES)
            ).first()

            if active_run:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A pipeline run is already in progress for this repository "
                        f"(Run ID: {active_run.run_id})"
                    )
                )

        # ── 3. Persist the repository and pipeline run records ────────────
        orchestrator = OrchestratorDB(user_id=current_user.id, db=db)
        registration = orchestrator.register_repository(
            repo_url=repo_data.url,
            branch=branch,
            visibility=visibility,
            pat=pat,
        )

        if registration["status"] != "COMPLETED":
            error_text = registration.get("error", "Repository registration failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_text
            )

        repository_id = registration["repository_id"]
        run_id = registration["run_id"]

        # ── 4. Clone and execute the pipeline in the background ───────────
        background_tasks.add_task(
            execute_onboarding_task,
            current_user.id,
            repository_id,
            run_id,
            repo_data.url,
            branch,
            pat,
        )

        new_repo = db.query(Repository).filter(
            Repository.id == repository_id
        ).first()

        if not new_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Repository record could not be created"
            )

        logger.info(
            "Repository onboarding accepted: repository_id=%s run_id=%s visibility=%s",
            repository_id,
            run_id,
            visibility,
        )

        return {
            "repository_id": repository_id,
            "run_id": run_id,
            "status": "queued",
            "message": "Repository onboarding started",
            "repository": new_repo,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Repository onboarding failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Repository onboarding could not be started"
        )


# ============================================================================
# Repository CRUD Endpoints
# ============================================================================

@router.post("/", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def create_repository(
    repo_data: RepositoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Add a new GitHub repository to track.
    
    - Validates GitHub URL
    - Fetches repository metadata from GitHub API (if PAT provided)
    - Encrypts and stores PAT if provided
    - Creates repository record in database
    """
    try:
        # Initialize GitHub client
        pat = repo_data.personal_access_token
        github_client = GitHubClient(personal_access_token=pat)
        
        # Validate URL format
        is_valid, error_msg = GitHubClient.validate_repo_url(repo_data.url)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid repository URL: {error_msg}"
            )
        
        # Validate PAT format if provided
        if pat:
            is_valid, error_msg = GitHubClient.validate_pat(pat)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid GitHub PAT: {error_msg}"
                )
        
        # Fetch repository info from GitHub
        repo_info = None
        if pat:
            try:
                repo_info = github_client.get_repo_info(repo_data.url)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e)
                )
        
        # Check if repository already exists for this user
        repo_identifier = GitHubClient._parse_repo_identifier(repo_data.url)
        existing_repo = db.query(Repository).filter(
            Repository.owner_id == current_user.id,
            Repository.name == repo_identifier
        ).first()
        
        if existing_repo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Repository {repo_identifier} already exists"
            )
        
        # Create repository record
        new_repo = Repository(
            name=repo_identifier,
            url=repo_data.url,
            branch=repo_data.branch or "main",
            owner_id=current_user.id,
            description=repo_data.description,
            clone_status="not_cloned",
        )
        
        # Add GitHub metadata if available
        if repo_info:
            new_repo.github_id = repo_info.get("github_id")
            new_repo.full_name = repo_info.get("full_name")
            new_repo.owner_login = repo_info.get("owner_login")
            new_repo.repo_name = repo_info.get("repo_name")
            new_repo.default_branch = repo_info.get("default_branch")
            new_repo.is_private = repo_info.get("is_private")
            new_repo.stars_count = repo_info.get("stars_count")
            new_repo.language = repo_info.get("language")
            new_repo.description = new_repo.description or repo_info.get("description")
        
        # Encrypt and store PAT if provided
        if pat:
            new_repo.encrypted_pat = github_client.encrypt_pat(pat)
        
        db.add(new_repo)
        db.commit()
        db.refresh(new_repo)
        
        return new_repo
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create repository: {str(e)}"
        )


@router.get("/", response_model=RepositoryListResponse)
def list_repositories(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all repositories for the current user.
    
    - Supports pagination via skip/limit
    - Returns total count and list of repositories
    """
    query = db.query(Repository).filter(Repository.owner_id == current_user.id)
    total = query.count()
    repositories = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "repositories": repositories
    }


@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository(
    repository_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific repository by ID."""
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    return repo


@router.patch("/{repository_id}", response_model=RepositoryResponse)
def update_repository(
    repository_id: int,
    updates: RepositoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update repository information."""
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Update fields
    if updates.branch is not None:
        repo.branch = updates.branch
    if updates.description is not None:
        repo.description = updates.description
    if updates.is_active is not None:
        repo.is_active = updates.is_active
    
    db.commit()
    db.refresh(repo)
    
    return repo


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repository_id: int,
    delete_clone: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a repository.
    
    - delete_clone: If True, also delete cloned files from filesystem
    """
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Delete clone if requested
    if delete_clone and repo.clone_path and repo.encrypted_pat:
        try:
            pat = GitHubClient().decrypt_pat(repo.encrypted_pat)
            github_client = GitHubClient(personal_access_token=pat)
            github_client.delete_clone(
                user_id=current_user.id,
                repo_id=repo.id,
                clone_path=repo.clone_path
            )
        except Exception as e:
            print(f"⚠ Failed to delete clone: {e}")
    
    db.delete(repo)
    db.commit()
    
    return None


# ============================================================================
# Clone Management Endpoints
# ============================================================================

@router.post("/{repository_id}/clone", response_model=CloneResponse)
def clone_repository(
    repository_id: int,
    clone_req: CloneRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Clone a GitHub repository to local filesystem.
    
    - Uses shallow cloning (depth=1) for speed
    - Caches clone metadata in Redis
    - Updates database with clone info
    - Returns immediately (cloning happens in background if large repo)
    """
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Check if already cloned
    if repo.clone_status == "cloned" and not clone_req.force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already cloned. Use force=true to reclone."
        )
    
    # Decrypt PAT if available
    pat = None
    if repo.encrypted_pat:
        try:
            pat = GitHubClient().decrypt_pat(repo.encrypted_pat)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to decrypt PAT: {e}"
            )
    
    # Initialize GitHub client
    github_client = GitHubClient(personal_access_token=pat)
    
    # Update status to 'cloning'
    repo.clone_status = "cloning"
    db.commit()
    
    try:
        # Clone repository (synchronous for now)
        branch = clone_req.branch or repo.branch
        clone_metadata = github_client.clone_repository(
            repo_url=repo.url,
            user_id=current_user.id,
            repo_id=repo.id,
            branch=branch,
            use_cache=not clone_req.force
        )
        
        # Update database with clone info
        repo.clone_path = clone_metadata["clone_path"]
        repo.clone_status = clone_metadata["clone_status"]
        repo.cloned_at = clone_metadata["cloned_at"]
        repo.clone_size_mb = clone_metadata["clone_size_mb"]
        repo.redis_cache_key = clone_metadata["redis_cache_key"]
        
        db.commit()
        db.refresh(repo)
        
        return {
            "repository_id": repo.id,
            "clone_status": repo.clone_status,
            "clone_path": repo.clone_path,
            "clone_size_mb": repo.clone_size_mb,
            "clone_duration_seconds": clone_metadata["clone_duration_seconds"],
            "cloned_at": repo.cloned_at.isoformat(),
            "message": "Repository cloned successfully"
        }
        
    except ValueError as e:
        # Clone failed, update status
        repo.clone_status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{repository_id}/clone/status", response_model=CloneStatusResponse)
def get_clone_status(
    repository_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get clone status for a repository.
    
    - Checks database and Redis cache
    - Returns current clone status and metadata
    """
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Check Redis cache
    redis_client = get_redis_client()
    cached_metadata = None
    if redis_client.is_connected():
        cached_metadata = redis_client.get_clone_metadata(current_user.id, repo.id)
    
    return {
        "repository_id": repo.id,
        "clone_status": repo.clone_status,
        "clone_path": repo.clone_path,
        "cloned_at": repo.cloned_at,
        "clone_size_mb": repo.clone_size_mb,
        "cached": cached_metadata is not None,
        "message": f"Clone status: {repo.clone_status}"
    }


@router.delete("/{repository_id}/clone", status_code=status.HTTP_204_NO_CONTENT)
def delete_clone(
    repository_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete cloned repository from filesystem and cache.
    
    - Removes clone from local filesystem
    - Clears Redis cache
    - Updates database status to 'not_cloned'
    """
    repo = db.query(Repository).filter(
        Repository.id == repository_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    if repo.clone_status == "not_cloned":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository is not cloned"
        )
    
    # Decrypt PAT if available
    pat = None
    if repo.encrypted_pat:
        try:
            pat = GitHubClient().decrypt_pat(repo.encrypted_pat)
        except ValueError:
            pass  # Continue even if PAT decryption fails
    
    # Delete clone
    github_client = GitHubClient(personal_access_token=pat)
    success = github_client.delete_clone(
        user_id=current_user.id,
        repo_id=repo.id,
        clone_path=repo.clone_path or ""
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete clone"
        )
    
    # Update database
    repo.clone_status = "not_cloned"
    repo.clone_path = None
    repo.cloned_at = None
    repo.clone_size_mb = None
    repo.redis_cache_key = None
    
    db.commit()
    
    return None


# ============================================================================
# Cache Management Endpoints
# ============================================================================

@router.get("/cache/stats", response_model=CacheStatsResponse)
def get_cache_stats(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get Redis cache statistics.
    
    - Shows total clone cache entries
    - Shows hit rate percentage
    - Useful for monitoring cache performance
    """
    redis_client = get_redis_client()
    
    if not redis_client.is_connected():
        return {
            "connected": False,
            "total_clone_keys": None,
            "keyspace_hits": None,
            "keyspace_misses": None,
            "hit_rate": None,
            "message": "Redis not connected"
        }
    
    stats = redis_client.get_cache_stats()
    
    return {
        **stats,
        "message": f"Cache hit rate: {stats.get('hit_rate', 0)}%"
    }


@router.delete("/cache/flush", status_code=status.HTTP_204_NO_CONTENT)
def flush_cache(
    current_user: User = Depends(get_current_active_user)
):
    """
    Flush all clone cache entries from Redis.
    
    ⚠️  WARNING: This deletes ALL cached clone metadata for ALL users!
    Use with caution.
    """
    redis_client = get_redis_client()
    
    if not redis_client.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis not connected"
        )
    
    success = redis_client.flush_all_clones()
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to flush cache"
        )
    
    return None
