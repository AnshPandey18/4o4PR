"""
Template for creating a new SQLAlchemy model.

Copy this file and modify for your needs.

Instructions:
1. Copy this file to app/models/your_model_name.py
2. Replace "YourModel" with your model name (PascalCase)
3. Replace "your_table_name" with database table name (snake_case)
4. Add your columns
5. Import in app/models/__init__.py
6. Import in app/main.py
7. Restart backend - table created automatically!
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class YourModel(Base):
    """
    Description of what this model represents.
    
    Example: User accounts, GitHub repositories, Bug reports, etc.
    """
    
    # Table name in database (snake_case)
    __tablename__ = "your_table_name"
    
    # ============================================================
    # PRIMARY KEY (Required)
    # ============================================================
    id = Column(Integer, primary_key=True, index=True)
    
    
    # ============================================================
    # YOUR COLUMNS
    # ============================================================
    
    # String columns
    name = Column(String, nullable=False)                    # Required string
    email = Column(String, unique=True, index=True)          # Unique + indexed
    description = Column(Text, nullable=True)                # Long text, optional
    
    # Number columns
    age = Column(Integer, default=0)                         # Integer with default
    price = Column(Float)                                    # Decimal number
    count = Column(Integer, nullable=False, default=0)       # Required with default
    
    # Boolean columns
    is_active = Column(Boolean, default=True)                # Active/inactive flag
    is_verified = Column(Boolean, default=False)             # Verification flag
    
    # JSON column (for complex data)
    metadata = Column(JSON, nullable=True)                   # Store JSON objects
    settings = Column(JSON, default={})                      # JSON with default
    
    
    # ============================================================
    # FOREIGN KEYS (Relationships to other tables)
    # ============================================================
    
    # Foreign key to users table
    user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),  # Delete this if user deleted
        nullable=False                                # Required field
    )
    
    # Foreign key to repositories table (optional)
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="SET NULL"),  # Set to NULL if repo deleted
        nullable=True                                         # Optional field
    )
    
    
    # ============================================================
    # TIMESTAMPS (Recommended)
    # ============================================================
    
    # Automatically set when created
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    
    # Automatically updated when row changes
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )
    
    
    # ============================================================
    # RELATIONSHIPS (For accessing related data)
    # ============================================================
    
    # Many-to-One: This model belongs to a User
    user = relationship(
        "User",                          # Related model name
        back_populates="your_models"     # Attribute name on User model
    )
    
    # One-to-Many: This model has many children
    # children = relationship(
    #     "ChildModel",
    #     back_populates="parent",
    #     cascade="all, delete-orphan"   # Delete children when parent deleted
    # )
    
    
    # ============================================================
    # STRING REPRESENTATION (For debugging)
    # ============================================================
    def __repr__(self):
        return f"<YourModel(id={self.id}, name={self.name})>"


# ============================================================
# USAGE EXAMPLES
# ============================================================

"""
# Create a new record
new_item = YourModel(
    name="Example",
    email="test@example.com",
    user_id=1,
    is_active=True,
    metadata={"key": "value"}
)
db.add(new_item)
db.commit()

# Query records
all_items = db.query(YourModel).all()
active_items = db.query(YourModel).filter(YourModel.is_active == True).all()
one_item = db.query(YourModel).filter(YourModel.id == 1).first()

# Update a record
item = db.query(YourModel).filter(YourModel.id == 1).first()
item.name = "Updated Name"
db.commit()

# Delete a record
item = db.query(YourModel).filter(YourModel.id == 1).first()
db.delete(item)
db.commit()

# Access relationships
item = db.query(YourModel).filter(YourModel.id == 1).first()
print(item.user.email)  # Access related user
"""


# ============================================================
# COMMON COLUMN PATTERNS
# ============================================================

"""
# Required field
name = Column(String, nullable=False)

# Optional field
description = Column(String, nullable=True)

# Unique constraint
email = Column(String, unique=True)

# Indexed for faster queries
user_id = Column(Integer, index=True)

# Default value
status = Column(String, default="pending")

# Auto-increment (default for primary keys)
id = Column(Integer, primary_key=True, autoincrement=True)

# Limited length string
code = Column(String(10))  # Max 10 characters

# Enum-like (use String with choices in Pydantic schema)
status = Column(String)  # Values: "open", "closed", "pending"

# Current timestamp on create
created_at = Column(DateTime(timezone=True), server_default=func.now())

# Update timestamp on every change
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
"""


# ============================================================
# FOREIGN KEY DELETE OPTIONS
# ============================================================

"""
CASCADE:     Delete this record when parent is deleted
SET NULL:    Set to NULL when parent is deleted (column must be nullable)
RESTRICT:    Prevent parent deletion if children exist
NO ACTION:   Database default (usually same as RESTRICT)
SET DEFAULT: Set to default value when parent deleted

Example:
user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
"""


# ============================================================
# RELATIONSHIP CASCADE OPTIONS
# ============================================================

"""
all, delete-orphan:  Delete children when parent deleted or relationship removed
all:                 Delete children when parent deleted
delete:              Delete children when parent deleted (only)
save-update:         Add children to session when parent added
merge:               Merge children when parent merged
expunge:             Remove children from session when parent removed
"""
