"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

# Base schema (shared fields)
class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: Optional[str] = None

# Schema for user registration (input)
class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(min_length=8, max_length=100)

# Schema for user login (input)
class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str

# Schema for user response (output)
class UserResponse(UserBase):
    """Schema for user response (excludes password)."""
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True  # Allow SQLAlchemy models

# Schema for JWT token response
class Token(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"

# Schema for token payload
class TokenData(BaseModel):
    """Token payload schema."""
    user_id: Optional[int] = None
    email: Optional[str] = None
