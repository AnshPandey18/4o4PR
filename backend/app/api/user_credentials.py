"""User credentials management endpoints (GitHub tokens)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

from ..database import get_db
from ..models.user import User
from ..models.user_credentials import UserCredentials
from ..utils.security import get_current_active_user
from ..tools.github_client import GitHubClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class CredentialsCreate(BaseModel):
    """Schema for creating/updating credentials."""
    github_token: str
    scopes: Optional[str] = None  # Allow empty/None for default scopes
    expires_at: Optional[str] = None  # ISO date string for expiration


class CredentialsResponse(BaseModel):
    """Schema for credentials response (no token exposed)."""
    id: int
    user_id: int
    token_last4: Optional[str]
    scopes: Optional[str]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================================================
# Credentials Endpoints
# ============================================================================

@router.post("/", response_model=CredentialsResponse, status_code=status.HTTP_201_CREATED)
def store_credentials(
    creds_data: CredentialsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Store GitHub Personal Access Token for the user.
    
    - Validates the PAT format
    - Encrypts the token before storage
    - Stores last 4 characters for display
    - Creates or updates existing credentials
    """
    try:
        # Validate PAT format
        github_client = GitHubClient()
        is_valid, error_msg = GitHubClient.validate_pat(creds_data.github_token)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GitHub PAT: {error_msg}"
            )
        
        # Encrypt token
        encrypted_token = github_client.encrypt_pat(creds_data.github_token)
        token_last4 = creds_data.github_token[-4:] if len(creds_data.github_token) >= 4 else None
        
        # Parse expiration date if provided
        expires_at = None
        if creds_data.expires_at:
            try:
                from datetime import datetime
                expires_at = datetime.fromisoformat(creds_data.expires_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid expiration date format. Use ISO format (YYYY-MM-DD)"
                )
        
        # Check if user already has credentials
        existing_creds = db.query(UserCredentials).filter(
            UserCredentials.user_id == current_user.id
        ).first()
        
        if existing_creds:
            # Update existing credentials
            existing_creds.encrypted_token = encrypted_token
            existing_creds.token_last4 = token_last4
            existing_creds.scopes = creds_data.scopes
            existing_creds.expires_at = expires_at
            existing_creds.revoked_at = None  # Un-revoke if previously revoked
            db.commit()
            db.refresh(existing_creds)
            logger.info(f"Updated credentials for user {current_user.id}")
            return existing_creds
        else:
            # Create new credentials
            new_creds = UserCredentials(
                user_id=current_user.id,
                encrypted_token=encrypted_token,
                token_last4=token_last4,
                scopes=creds_data.scopes,
                expires_at=expires_at
            )
            db.add(new_creds)
            db.commit()
            db.refresh(new_creds)
            logger.info(f"Created credentials for user {current_user.id}")
            return new_creds
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Failed to store credentials")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store credentials: {str(e)}"
        )


@router.get("/", response_model=CredentialsResponse)
def get_credentials(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get user's GitHub credentials info (without exposing the token).
    
    Returns metadata about the stored token including:
    - Last 4 characters
    - Scopes
    - Expiration date
    - Active status
    """
    creds = db.query(UserCredentials).filter(
        UserCredentials.user_id == current_user.id
    ).first()
    
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credentials found. Please store a GitHub token first."
        )
    
    return creds


@router.put("/", response_model=CredentialsResponse)
def update_credentials(
    creds_data: CredentialsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update user's GitHub Personal Access Token.
    
    This is equivalent to POST but explicitly for updating.
    """
    return store_credentials(creds_data, db, current_user)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def revoke_credentials(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Revoke user's GitHub credentials.
    
    Marks the credentials as revoked (soft delete).
    The encrypted token is kept in database for audit purposes.
    """
    creds = db.query(UserCredentials).filter(
        UserCredentials.user_id == current_user.id
    ).first()
    
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credentials found"
        )
    
    if creds.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credentials already revoked"
        )
    
    # Mark as revoked (soft delete)
    creds.revoked_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Revoked credentials for user {current_user.id}")
    return None


@router.post("/test", status_code=status.HTTP_200_OK)
def test_credentials(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Test if the stored GitHub credentials are valid.
    
    Makes a simple API call to GitHub to verify the token works.
    Updates last_used_at timestamp.
    """
    creds = db.query(UserCredentials).filter(
        UserCredentials.user_id == current_user.id
    ).first()
    
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credentials found"
        )
    
    if not creds.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credentials are not active (expired or revoked)"
        )
    
    try:
        # Decrypt and test the token
        github_client = GitHubClient()
        decrypted_token = github_client.decrypt_pat(creds.encrypted_token)
        
        # Test by initializing client (this validates the token)
        test_client = GitHubClient(personal_access_token=decrypted_token)
        
        # Update last_used_at
        creds.last_used_at = datetime.utcnow()
        db.commit()
        
        return {
            "status": "valid",
            "message": "GitHub credentials are valid",
            "scopes": creds.scopes,
            "token_last4": creds.token_last4
        }
        
    except ValueError as e:
        logger.warning(f"Credential test failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid credentials: {str(e)}"
        )
    except Exception as e:
        logger.exception("Failed to test credentials")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test credentials: {str(e)}"
        )
