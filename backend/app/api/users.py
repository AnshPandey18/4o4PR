"""User endpoints (protected routes)."""
from fastapi import APIRouter, Depends
from ..schemas.user import UserResponse
from ..utils.security import get_current_active_user
from ..models.user import User

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    """Get current user's profile."""
    return current_user
