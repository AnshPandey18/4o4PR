"""Repository model - represents a GitHub repository."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class Repository(Base):
    """GitHub repository model."""
    
    __tablename__ = "repositories"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Repository info
    name = Column(String, nullable=False)  # e.g., "user/repo"
    url = Column(String, nullable=False)   # GitHub URL
    branch = Column(String, default="main")
    
    # Owner (foreign key to users table)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_scan = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to user
    owner = relationship("User", back_populates="repositories")
    
    def __repr__(self):
        return f"<Repository(id={self.id}, name={self.name})>"
