"""UserCredentials model - stores encrypted GitHub tokens for users."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class UserCredentials(Base):
    """
    User credentials model for storing encrypted GitHub tokens.
    
    Each credential represents a GitHub Personal Access Token (PAT) for a user:
    - Encrypted storage of the token
    - Token metadata (last 4 chars, scopes, expiry)
    - Usage tracking (last used, revocation status)
    """
    
    __tablename__ = "user_credentials"
    
    # ========================================================================
    # Primary Key
    # ========================================================================
    id = Column(Integer, primary_key=True, index=True)
    
    # ========================================================================
    # Foreign Keys
    # ========================================================================
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One token per user (can be changed to False for multiple tokens)
        index=True
    )
    
    # ========================================================================
    # Token Storage
    # ========================================================================
    encrypted_token = Column(Text, nullable=False)  # Fernet-encrypted GitHub PAT
    token_last4 = Column(String(4), nullable=True)  # Last 4 characters for display
    
    # ========================================================================
    # Token Metadata
    # ========================================================================
    scopes = Column(Text, nullable=True)  # Comma-separated scopes (e.g., "repo,user")
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Token expiration
    
    # ========================================================================
    # Usage Tracking
    # ========================================================================
    last_used_at = Column(DateTime(timezone=True), nullable=True)  # Last time token was used
    revoked_at = Column(DateTime(timezone=True), nullable=True)  # If token was revoked
    
    # ========================================================================
    # Metadata
    # ========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # ========================================================================
    # Relationships
    # ========================================================================
    user = relationship("User", backref="credentials")
    
    # ========================================================================
    # Methods
    # ========================================================================
    
    def __repr__(self):
        return f"<UserCredentials(id={self.id}, user_id={self.user_id}, last4=...{self.token_last4})>"
    
    @property
    def is_revoked(self) -> bool:
        """Check if token has been revoked."""
        return self.revoked_at is not None
    
    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        if self.expires_at is None:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_active(self) -> bool:
        """Check if token is active (not revoked and not expired)."""
        return not self.is_revoked and not self.is_expired
    
    def to_dict(self) -> dict:
        """Convert credentials to dictionary (without exposing encrypted token)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token_last4": self.token_last4,
            "scopes": self.scopes,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
