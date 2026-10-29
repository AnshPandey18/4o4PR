"""Pipeline run management endpoints (Orchestrator Integration)."""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import logging
import os
import sys
from pathlib import Path

from ..database import get_db
from ..models.user import User
from ..models.repository import Repository
from ..models.user_credentials import UserCredentials
from ..models.pipeline_run import PipelineRun
from ..schemas.pipeline_run import (
    PipelineRunCreate,
    PipelineRunUpdate,
    PipelineRunResponse,
    PipelineRunListResponse,
    PipelineRunStatsResponse,
    PipelineRunTriggerRequest,
    PipelineRunTriggerResponse,
    PipelineRunCancelRequest,
    PipelineRunCancelResponse,
)
from ..utils.security import get_current_active_user
from ..tools.github_client import GitHubClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline-runs", tags=["pipeline-runs"])

BACKEND_DIR = Path(__file__).parent.parent.parent.resolve()

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from orchestrator import OrchestratorDB, execute_onboarding_task

# Statuses that mean a pipeline run is still in flight
ACTIVE_RUN_STATUSES = ("pending", "queued", "running")


# ============================================================================
# Pipeline Run CRUD Endpoints
# ============================================================================

@router.post("/", response_model=PipelineRunResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline_run(
    run_data: PipelineRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new pipeline run record.
    
    This endpoint is typically called by the orchestrator at run start.
    Use /trigger endpoint to start a new pipeline run from the UI.
    """
    # Verify repository exists and belongs to user
    repo = db.query(Repository).filter(
        Repository.id == run_data.repository_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    
    # Check if repository is cloned
    if not repo.is_cloned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository must be cloned first. Current status: {repo.clone_status}"
        )
    
    # Create pipeline run with new schema
    new_run = PipelineRun(
        repository_id=repo.id,
        status="pending",
        input_mode=run_data.input_mode or "branch",
        input_ref=run_data.input_ref or repo.default_branch,
        commit_sha=run_data.commit_sha,
    )
    
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    
    # Calculate success_rate property
    response = PipelineRunResponse.from_orm(new_run)
    response.success_rate = new_run.success_rate
    
    return response


@router.get("/", response_model=PipelineRunListResponse)
def list_pipeline_runs(
    repository_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List pipeline runs for the current user.
    
    Optionally filter by repository_id and/or status.
    Supports pagination via skip/limit.
    """
    # Query through repository to ensure ownership
    query = db.query(PipelineRun).join(Repository).filter(
        Repository.owner_id == current_user.id
    )
    
    if repository_id:
        # Verify repository belongs to user
        repo = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.owner_id == current_user.id
        ).first()
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
        query = query.filter(PipelineRun.repository_id == repository_id)
    
    if status:
        query = query.filter(PipelineRun.status == status)
    
    # Order by most recent first
    query = query.order_by(PipelineRun.created_at.desc())
    
    total = query.count()
    runs = query.offset(skip).limit(limit).all()
    
    # Add success_rate to each run
    runs_with_rate = []
    for run in runs:
        run_response = PipelineRunResponse.from_orm(run)
        run_response.success_rate = run.success_rate
        runs_with_rate.append(run_response)
    
    return {
        "total": total,
        "runs": runs_with_rate
    }


@router.get("/{run_id}", response_model=PipelineRunResponse)
def get_pipeline_run(
    run_id: int,  # Changed from str to int (using database ID now)
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get details of a specific pipeline run."""
    run = db.query(PipelineRun).join(Repository).filter(
        PipelineRun.id == run_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found"
        )
    
    response = PipelineRunResponse.from_orm(run)
    response.success_rate = run.success_rate
    return response


@router.patch("/{run_id}", response_model=PipelineRunResponse)
def update_pipeline_run(
    run_id: int,  # Changed from str to int
    updates: PipelineRunUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update pipeline run status and results.
    
    This endpoint is typically called by the orchestrator during/after execution.
    """
    run = db.query(PipelineRun).join(Repository).filter(
        PipelineRun.id == run_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found"
        )
    
    # Update fields
    if updates.status is not None:
        run.status = updates.status
        
        # Auto-set timestamps based on status
        if updates.status == "running" and not run.started_at:
            run.started_at = datetime.now(timezone.utc)
        elif updates.status in ("completed", "failed", "cancelled") and not run.completed_at:
            run.completed_at = datetime.now(timezone.utc)
            # Note: duration_seconds no longer exists, calculate on-the-fly if needed
    
    if updates.bugs_detected is not None:
        run.bugs_detected = updates.bugs_detected
    if updates.bugs_fixed is not None:
        run.bugs_fixed = updates.bugs_fixed
    if updates.patches_generated is not None:
        run.patches_generated = updates.patches_generated
    if updates.error_message is not None:
        run.error_message = updates.error_message
    # Note: error_traceback no longer exists in schema
    
    db.commit()
    db.refresh(run)
    
    response = PipelineRunResponse.from_orm(run)
    response.success_rate = run.success_rate
    return response


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_run(
    run_id: int,  # Changed from str to int
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a pipeline run record."""
    run = db.query(PipelineRun).join(Repository).filter(
        PipelineRun.id == run_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found"
        )
    
    # Don't delete running pipelines
    if run.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a running pipeline. Cancel it first."
        )
    
    db.delete(run)
    db.commit()
    
    return None


# ============================================================================
# Pipeline Run Control Endpoints
# ============================================================================

@router.post("/trigger", response_model=PipelineRunTriggerResponse)
def trigger_pipeline_run(
    trigger_req: PipelineRunTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Trigger a new pipeline run on a repository.

    This is the main endpoint for starting the orchestrator from the UI.

    Supports three modes:
    - branch: Run on a specific branch (repository_id + branch name required)
    - pr: Run on a pull request (PR URL required, will fetch repo if needed)
    - commit: Run on a specific commit (repository_id + commit SHA required)

    Steps:
    1. Parse and validate input based on mode
    2. Fetch/verify repository (create if PR mode)
    3. Validate commit SHA or PR (if applicable)
    4. Create the PipelineRun record
    5. Start the orchestrator in the background
    6. Return the run_id immediately

    The real execution state is observed through GET /api/pipeline-runs/{run_id}.
    """
    repo = None
    repo_url = None
    branch = None
    commit_sha = None
    
    # Get user's PAT from credentials
    user_creds = db.query(UserCredentials).filter(
        UserCredentials.user_id == current_user.id
    ).first()
    
    pat = None
    if user_creds:
        try:
            pat = GitHubClient().decrypt_pat(user_creds.encrypted_token)
        except ValueError:
            logger.warning("Stored access token could not be decrypted for user %s", current_user.id)
    
    github_client = GitHubClient(personal_access_token=pat)
    
    # ======================================================================
    # MODE 1: Branch Mode
    # ======================================================================
    if trigger_req.input_mode == "branch":
        if not trigger_req.repository_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="repository_id is required for branch mode"
            )
        
        # Verify repository exists and belongs to user
        repo = db.query(Repository).filter(
            Repository.id == trigger_req.repository_id,
            Repository.owner_id == current_user.id
        ).first()
        
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
        
        repo_url = f"https://github.com/{repo.full_name}"
        branch = trigger_req.input_ref or repo.default_branch or "main"
    
    # ======================================================================
    # MODE 2: Pull Request Mode
    # ======================================================================
    elif trigger_req.input_mode == "pr":
        # Parse PR URL: https://github.com/owner/repo/pull/123
        pr_url = trigger_req.input_ref
        
        # Extract owner/repo from PR URL
        import re
        pr_pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.search(pr_pattern, pr_url)
        
        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PR URL format. Expected: https://github.com/owner/repo/pull/123"
            )
        
        owner, repo_name, pr_number = match.groups()
        full_name = f"{owner}/{repo_name}"
        repo_url = f"https://github.com/{full_name}"
        
        # Check if repository already exists
        repo = db.query(Repository).filter(
            Repository.owner_id == current_user.id,
            Repository.full_name == full_name
        ).first()
        
        # Fetch PR information from GitHub to get the commit SHA
        try:
            github = github_client.github
            if not github:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="GitHub authentication required to fetch PR information"
                )
            
            gh_repo = github.get_repo(full_name)
            pr = gh_repo.get_pull(int(pr_number))
            
            commit_sha = pr.head.sha  # Full 40-character SHA
            branch = pr.head.ref  # Branch name from PR head
            
            # Create repository if it doesn't exist
            if not repo:
                repo = Repository(
                    full_name=full_name,
                    owner_id=current_user.id,
                    description=f"Added from PR #{pr_number}",
                    github_id=gh_repo.id,
                    default_branch=gh_repo.default_branch,
                    is_private=gh_repo.private,
                    clone_status="not_cloned"
                )
                db.add(repo)
                db.commit()
                db.refresh(repo)
                logger.info(f"Created repository {full_name} from PR #{pr_number}")
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch PR information: {str(e)}"
            )
    
    # ======================================================================
    # MODE 3: Commit Hash Mode
    # ======================================================================
    elif trigger_req.input_mode == "commit":
        if not trigger_req.repository_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="repository_id is required for commit mode"
            )
        
        # Verify repository exists and belongs to user
        repo = db.query(Repository).filter(
            Repository.id == trigger_req.repository_id,
            Repository.owner_id == current_user.id
        ).first()
        
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
        
        repo_url = f"https://github.com/{repo.full_name}"
        branch = repo.default_branch or "main"
        
        # Validate commit SHA with GitHub API and expand short SHA
        try:
            github = github_client.github
            if not github:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="GitHub authentication required to validate commit SHA"
                )
            
            gh_repo = github.get_repo(repo.full_name)
            commit = gh_repo.get_commit(trigger_req.input_ref)  # This validates and expands short SHA
            commit_sha = commit.sha  # Full 40-character SHA
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid commit SHA: {str(e)}"
            )
    
    # ======================================================================
    # Common: Check for active runs and create pipeline run
    # ======================================================================
    
    # Prevent conflicting duplicate submissions
    existing_run = db.query(PipelineRun).filter(
        PipelineRun.repository_id == repo.id,
        PipelineRun.status.in_(ACTIVE_RUN_STATUSES)
    ).first()
    
    if existing_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline already running for this repository. Run ID: {existing_run.id}"
        )
    
    # Create pipeline run record
    new_run = PipelineRun(
        repository_id=repo.id,
        status="queued",
        input_mode=trigger_req.input_mode,
        input_ref=trigger_req.input_ref,
        commit_sha=commit_sha,  # Will be None for branch mode (determined during clone)
    )
    
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    
    # Start the orchestrator in the background
    background_tasks.add_task(
        execute_onboarding_task,
        current_user.id,
        repo.id,
        new_run.id,  # Using database ID
        repo_url,
        trigger_req.input_mode,  # Pass input_mode
        trigger_req.input_ref,   # Pass input_ref (branch, PR#, or commit SHA)
        pat,
    )
    
    logger.info(
        "Pipeline run queued: id=%s repository_id=%s mode=%s ref=%s",
        new_run.id, repo.id, trigger_req.input_mode, trigger_req.input_ref
    )
    
    return {
        "run_id": str(new_run.id),
        "repository_id": repo.id,
        "status": "queued",
        "message": f"Pipeline run queued successfully. Run ID: {new_run.id}",
        "orchestrator_root": repo.clone_path or ""
    }


@router.post("/{run_id}/cancel", response_model=PipelineRunCancelResponse)
def cancel_pipeline_run(
    run_id: int,  # Changed from str to int
    cancel_req: PipelineRunCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel a running pipeline.
    
    This will attempt to gracefully stop the orchestrator process.
    """
    run = db.query(PipelineRun).join(Repository).filter(
        PipelineRun.id == run_id,
        Repository.owner_id == current_user.id
    ).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline run not found"
        )
    
    # Can only cancel pending/queued/running pipelines
    if run.is_finished:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel pipeline with status: {run.status}"
        )
    
    # Update status
    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    # Note: duration_seconds no longer exists, calculate on-the-fly if needed
    
    if cancel_req.reason:
        run.error_message = f"Cancelled by user: {cancel_req.reason}"
    else:
        run.error_message = "Cancelled by user"
    
    db.commit()
    
    # TODO: Send cancellation signal to orchestrator process
    print(f"🛑 Pipeline run cancelled: {run_id}")
    
    return {
        "run_id": str(run_id),
        "status": "cancelled",
        "message": "Pipeline run cancelled successfully"
    }


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/stats/summary", response_model=PipelineRunStatsResponse)
def get_pipeline_run_stats(
    repository_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get aggregate statistics for pipeline runs.
    
    Optionally filter by repository_id.
    """
    query = db.query(PipelineRun).join(Repository).filter(
        Repository.owner_id == current_user.id
    )
    
    if repository_id:
        # Verify repository belongs to user
        repo = db.query(Repository).filter(
            Repository.id == repository_id,
            Repository.owner_id == current_user.id
        ).first()
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )
        query = query.filter(PipelineRun.repository_id == repository_id)
    
    all_runs = query.all()
    
    # Calculate statistics
    total_runs = len(all_runs)
    pending_runs = sum(1 for r in all_runs if r.is_pending)
    running_runs = sum(1 for r in all_runs if r.is_running)
    completed_runs = sum(1 for r in all_runs if r.is_completed)
    failed_runs = sum(1 for r in all_runs if r.is_failed)
    cancelled_runs = sum(1 for r in all_runs if r.is_cancelled)
    
    total_bugs_detected = sum(r.bugs_detected for r in all_runs)
    total_bugs_fixed = sum(r.bugs_fixed for r in all_runs)
    total_patches_generated = sum(r.patches_generated for r in all_runs)
    
    # Calculate average success rate
    completed_with_bugs = [r for r in all_runs if r.is_completed and r.bugs_detected > 0]
    if completed_with_bugs:
        avg_success_rate = sum(r.success_rate for r in completed_with_bugs) / len(completed_with_bugs)
    else:
        avg_success_rate = 0.0
    
    # Calculate average duration (on-the-fly since duration_seconds no longer exists)
    finished_with_times = [r for r in all_runs if r.is_finished and r.started_at and r.completed_at]
    if finished_with_times:
        durations = [(r.completed_at - r.started_at).total_seconds() for r in finished_with_times]
        avg_duration_seconds = sum(durations) / len(durations)
    else:
        avg_duration_seconds = None
    
    return {
        "total_runs": total_runs,
        "pending_runs": pending_runs,
        "running_runs": running_runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "cancelled_runs": cancelled_runs,
        "total_bugs_detected": total_bugs_detected,
        "total_bugs_fixed": total_bugs_fixed,
        "total_patches_generated": total_patches_generated,
        "average_success_rate": round(avg_success_rate, 2),
        "average_duration_seconds": round(avg_duration_seconds, 2) if avg_duration_seconds else None,
    }
