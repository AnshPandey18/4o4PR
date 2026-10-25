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

from orchestrator_db import OrchestratorDB, execute_onboarding_task

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
    
    # Generate run_id
    run_id = OrchestratorDB.generate_run_id()
    
    # Determine output directory
    output_dir = run_data.output_dir or str(BACKEND_DIR / "runs" / run_id)
    
    # Create pipeline run
    new_run = PipelineRun(
        run_id=run_id,
        repository_id=repo.id,
        user_id=current_user.id,
        orchestrator_root=repo.clone_path,
        import_roots=run_data.import_roots or "src",
        output_dir=output_dir,
        config_file=run_data.config_file,
        verbose=run_data.verbose,
        status="pending",
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
    query = db.query(PipelineRun).filter(PipelineRun.user_id == current_user.id)
    
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
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get details of a specific pipeline run."""
    run = db.query(PipelineRun).filter(
        PipelineRun.run_id == run_id,
        PipelineRun.user_id == current_user.id
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
    run_id: str,
    updates: PipelineRunUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update pipeline run status and results.
    
    This endpoint is typically called by the orchestrator during/after execution.
    """
    run = db.query(PipelineRun).filter(
        PipelineRun.run_id == run_id,
        PipelineRun.user_id == current_user.id
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
            completed_at = datetime.now(timezone.utc)
            run.completed_at = completed_at
            if run.started_at:
                run.duration_seconds = int((completed_at - run.started_at).total_seconds())
    
    if updates.bugs_detected is not None:
        run.bugs_detected = updates.bugs_detected
    if updates.bugs_fixed is not None:
        run.bugs_fixed = updates.bugs_fixed
    if updates.patches_generated is not None:
        run.patches_generated = updates.patches_generated
    if updates.error_message is not None:
        run.error_message = updates.error_message
    if updates.error_traceback is not None:
        run.error_traceback = updates.error_traceback
    
    db.commit()
    db.refresh(run)
    
    response = PipelineRunResponse.from_orm(run)
    response.success_rate = run.success_rate
    return response


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a pipeline run record."""
    run = db.query(PipelineRun).filter(
        PipelineRun.run_id == run_id,
        PipelineRun.user_id == current_user.id
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

    Steps:
    1. Verify the repository exists and belongs to the user
    2. Reject the request when a run is already active for the repository
    3. Create the PipelineRun record
    4. Start the orchestrator in the background (clone if needed, then execute)
    5. Return the run_id immediately

    The real execution state is observed through GET /api/pipeline-runs/{run_id}.
    """
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
    
    # Prevent conflicting duplicate submissions
    existing_run = db.query(PipelineRun).filter(
        PipelineRun.repository_id == repo.id,
        PipelineRun.status.in_(ACTIVE_RUN_STATUSES)
    ).first()
    
    if existing_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline already running for this repository. Run ID: {existing_run.run_id}"
        )
    
    # Generate a unique run_id
    run_id = OrchestratorDB.generate_run_id()
    branch = repo.branch or "main"
    output_dir = str(BACKEND_DIR / "runs" / run_id)
    
    # Create pipeline run record
    new_run = PipelineRun(
        run_id=run_id,
        repository_id=repo.id,
        user_id=current_user.id,
        orchestrator_root=repo.clone_path or "",
        import_roots=trigger_req.import_roots or "src",
        output_dir=output_dir,
        verbose=trigger_req.verbose,
        status="queued",
    )
    
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    
    # Recover the stored token for private repositories. Only the encrypted
    # form is persisted; it is decrypted here and never written to the logs.
    pat = None
    if repo.encrypted_pat:
        try:
            pat = GitHubClient().decrypt_pat(repo.encrypted_pat)
        except ValueError:
            logger.warning("Stored access token could not be decrypted for repository %s", repo.id)
    
    # Start the orchestrator in the background so the event loop is never blocked
    background_tasks.add_task(
        execute_onboarding_task,
        current_user.id,
        repo.id,
        run_id,
        repo.url,
        branch,
        pat,
    )
    
    logger.info(
        "Pipeline run queued: run_id=%s repository_id=%s", run_id, repo.id
    )
    
    return {
        "run_id": run_id,
        "repository_id": repo.id,
        "status": "queued",
        "message": f"Pipeline run queued successfully. Run ID: {run_id}",
        "orchestrator_root": repo.clone_path or ""
    }


@router.post("/{run_id}/cancel", response_model=PipelineRunCancelResponse)
def cancel_pipeline_run(
    run_id: str,
    cancel_req: PipelineRunCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel a running pipeline.
    
    This will attempt to gracefully stop the orchestrator process.
    """
    run = db.query(PipelineRun).filter(
        PipelineRun.run_id == run_id,
        PipelineRun.user_id == current_user.id
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
    completed_at = datetime.now(timezone.utc)
    run.completed_at = completed_at
    if run.started_at:
        run.duration_seconds = int((completed_at - run.started_at).total_seconds())
    
    if cancel_req.reason:
        run.error_message = f"Cancelled by user: {cancel_req.reason}"
    else:
        run.error_message = "Cancelled by user"
    
    db.commit()
    
    # TODO: Send cancellation signal to orchestrator process
    print(f"🛑 Pipeline run cancelled: {run_id}")
    
    return {
        "run_id": run_id,
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
    query = db.query(PipelineRun).filter(PipelineRun.user_id == current_user.id)
    
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
    
    # Calculate average duration
    finished_with_duration = [r for r in all_runs if r.is_finished and r.duration_seconds]
    if finished_with_duration:
        avg_duration_seconds = sum(r.duration_seconds for r in finished_with_duration) / len(finished_with_duration)
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
