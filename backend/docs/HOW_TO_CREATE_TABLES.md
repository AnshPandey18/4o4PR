# How to Create Database Tables from SQLAlchemy Models

## 🎯 Quick Summary

**Current Setup:** Tables are created **automatically** when the backend starts.

**Location:** `app/main.py` line: `Base.metadata.create_all(bind=engine)`

---

## 📝 Step-by-Step: Create a New Table

### Step 1: Create Model File

Create a new file in `app/models/` (e.g., `app/models/your_model.py`):

```python
"""Your model description."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class YourModel(Base):
    """Your model description."""
    
    __tablename__ = "your_table_name"
    
    # Primary key (required)
    id = Column(Integer, primary_key=True, index=True)
    
    # Your columns
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    age = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Foreign key (optional)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    # Timestamps (recommended)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships (optional)
    user = relationship("User", back_populates="your_models")
    
    def __repr__(self):
        return f"<YourModel(id={self.id}, name={self.name})>"
```

---

### Step 2: Import Model in `__init__.py`

Edit `app/models/__init__.py`:

```python
"""Models package."""
from .user import User
from .repository import Repository
from .your_model import YourModel  # Add this line

__all__ = ["User", "Repository", "YourModel"]  # Add to list
```

---

### Step 3: Import in `main.py`

Edit `app/main.py`:

```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base
from .api import auth, users

# Import all models (so they're registered with Base)
from .models import User, Repository, YourModel  # Add YourModel

# Create database tables
Base.metadata.create_all(bind=engine)
```

---

### Step 4: Restart Backend

**Automatic table creation:**
```powershell
cd "D:\Code - Programming\4o4\backend"
.\start.ps1
```

Or manually:
```powershell
cd "D:\Code - Programming\4o4\backend"
.\venv\Scripts\activate
uvicorn app.main:app --reload
```

**That's it!** The table will be created automatically.

---

## 🔍 Verify Table Creation

### Method 1: DBeaver
1. Right-click on database → Refresh
2. Expand "Schemas" → "public" → "Tables"
3. You should see your new table

### Method 2: PowerShell
```powershell
# List all tables
docker exec 4o4_postgres psql -U admin -d 4o4_db -c "\dt"

# Describe specific table
docker exec 4o4_postgres psql -U admin -d 4o4_db -c "\d your_table_name"
```

### Method 3: Python Shell
```powershell
cd "D:\Code - Programming\4o4\backend"
.\venv\Scripts\activate
python
```

```python
from app.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
print(inspector.get_table_names())
```

---

## 📊 Column Types Reference

### Common Column Types:

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, JSON, ForeignKey

# Strings
name = Column(String)                    # VARCHAR
name = Column(String(100))               # VARCHAR(100) - limited length
description = Column(Text)               # TEXT - unlimited length

# Numbers
age = Column(Integer)                    # Integer
price = Column(Float)                    # Float/Decimal
count = Column(Integer, default=0)       # With default value

# Boolean
is_active = Column(Boolean, default=True)
is_verified = Column(Boolean, nullable=False, default=False)

# Timestamps
created_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# JSON (for complex data)
metadata = Column(JSON)                  # Store JSON objects

# Foreign Key
user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
```

---

## 🔗 Relationships

### One-to-Many (User has many Repositories)

**Parent model (User):**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    
    # Relationship
    repositories = relationship("Repository", back_populates="owner", cascade="all, delete-orphan")
```

**Child model (Repository):**
```python
class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Integer, primary_key=True)
    
    # Foreign key
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    # Relationship
    owner = relationship("User", back_populates="repositories")
```

### Many-to-Many (Users and Roles)

**Association table:**
```python
user_roles = Table('user_roles', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('role_id', Integer, ForeignKey('roles.id'))
)
```

**Models:**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    roles = relationship("Role", secondary=user_roles, back_populates="users")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    users = relationship("User", secondary=user_roles, back_populates="roles")
```

---

## ⚙️ Column Constraints

```python
# Not null (required)
name = Column(String, nullable=False)

# Unique
email = Column(String, unique=True)

# Default value
is_active = Column(Boolean, default=True)

# Index (for faster queries)
email = Column(String, index=True)

# Primary key
id = Column(Integer, primary_key=True)

# Auto-increment (default for Integer primary keys)
id = Column(Integer, primary_key=True, autoincrement=True)

# Server-side default (database generates value)
created_at = Column(DateTime(timezone=True), server_default=func.now())

# Update on change
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

---

## 🔄 Update Existing Tables (Add Column)

**⚠️ Important:** `create_all()` does NOT modify existing tables!

To add columns to existing tables, you have 2 options:

### Option 1: Drop and Recreate (Development Only - LOSES DATA!)

```powershell
# Connect to database
docker exec -it 4o4_postgres psql -U admin -d 4o4_db

# Drop table
DROP TABLE your_table_name CASCADE;

# Exit psql
\q

# Restart backend (table will be recreated)
```

### Option 2: Use Alembic Migrations (Production - RECOMMENDED)

Will be covered in advanced section.

---

## 🧪 Test Your Model

### Create a test endpoint:

Create `app/api/repositories.py`:

```python
"""Repository endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.repository import Repository
from ..models.user import User

router = APIRouter(prefix="/api/repositories", tags=["repositories"])

@router.post("/")
def create_repository(name: str, url: str, user_id: int, db: Session = Depends(get_db)):
    """Create a new repository."""
    repo = Repository(name=name, url=url, owner_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo

@router.get("/")
def list_repositories(db: Session = Depends(get_db)):
    """List all repositories."""
    return db.query(Repository).all()
```

Register in `main.py`:
```python
from .api import auth, users, repositories

app.include_router(repositories.router)
```

Test at: http://127.0.0.1:8000/docs

---

## 📋 Example Models

### Simple Model (No Relationships)

```python
class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Model with Foreign Key

```python
class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    task = relationship("Task")
```

### Complex Model (JSON data)

```python
class BugReport(Base):
    __tablename__ = "bug_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    status = Column(String, default="open")
    
    # Store complex data as JSON
    traceback = Column(JSON)  # {"error": "...", "line": 42, ...}
    metadata = Column(JSON)   # {"browser": "Chrome", "os": "Windows", ...}
    
    # Relationships
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    repository = relationship("Repository")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## 🚨 Common Errors & Solutions

### Error: "Table already exists"
**Cause:** Table was manually created or already exists.
**Solution:** Drop the table first or ignore (create_all skips existing tables).

### Error: "No such table"
**Cause:** Model not imported in main.py or backend not restarted.
**Solution:** Import model in main.py and restart backend.

### Error: "Foreign key constraint fails"
**Cause:** Referenced table doesn't exist or foreign key points to wrong table.
**Solution:** Make sure parent table is created first (import order matters).

### Error: "Cannot add column with NOT NULL"
**Cause:** Trying to add non-nullable column to table with existing data.
**Solution:** Make column nullable or provide default value.

---

## ✅ Checklist: Adding a New Model

- [ ] Create model file in `app/models/`
- [ ] Define `__tablename__`
- [ ] Add primary key column (`id`)
- [ ] Add your columns
- [ ] Add timestamps (`created_at`, `updated_at`)
- [ ] Add relationships if needed
- [ ] Import in `app/models/__init__.py`
- [ ] Import in `app/main.py`
- [ ] Restart backend
- [ ] Verify table in DBeaver or psql
- [ ] Test with API endpoint

---

## 🎓 Real Example: Our Current Models

### User Model (already exists)
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    repositories = relationship("Repository", back_populates="owner")
```

### Repository Model (just created)
```python
class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    branch = Column(String, default="main")
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    is_active = Column(Boolean, default=True)
    last_scan = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    owner = relationship("User", back_populates="repositories")
```

Check in DBeaver:
```sql
SELECT * FROM repositories;
SELECT * FROM users;
```

---

## 📚 Resources

- SQLAlchemy Docs: https://docs.sqlalchemy.org/
- Column Types: https://docs.sqlalchemy.org/en/20/core/types.html
- Relationships: https://docs.sqlalchemy.org/en/20/orm/relationships.html
- FastAPI + SQLAlchemy: https://fastapi.tiangolo.com/tutorial/sql-databases/
