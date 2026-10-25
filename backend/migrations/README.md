# Database Migrations

This directory contains SQL migration scripts for the 4o4PR database schema.

## Migration Files

### 002 - GitHub Integration
- **File**: `002_add_github_integration.sql`
- **Rollback**: `002_add_github_integration_rollback.sql`
- **Purpose**: Add GitHub repository integration with clone tracking and pipeline runs

**Changes**:
- Adds 16 new columns to `repositories` table for GitHub metadata, clone tracking, and PAT storage
- Creates `pipeline_runs` table to track orchestrator executions
- Adds indexes for performance optimization
- Includes automatic timestamp updates via triggers

## How to Run Migrations

### Using psql (Direct SQL execution)

```bash
# Run migration
psql -U admin -d 4o4_db -f migrations/002_add_github_integration.sql

# Rollback migration
psql -U admin -d 4o4_db -f migrations/002_add_github_integration_rollback.sql
```

### Using Docker container

```bash
# Copy migration file to container
docker cp backend/migrations/002_add_github_integration.sql 4o4_postgres:/tmp/

# Execute migration inside container
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -f /tmp/002_add_github_integration.sql

# Verify migration
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "\d repositories"
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "\d pipeline_runs"
```

### Using Python script

```python
from sqlalchemy import create_engine, text
import os

# Load database URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Read and execute migration
with open("migrations/002_add_github_integration.sql", "r") as f:
    migration_sql = f.read()

with engine.connect() as conn:
    # Split by semicolon and execute each statement
    for statement in migration_sql.split(";"):
        if statement.strip():
            conn.execute(text(statement))
    conn.commit()

print("✓ Migration completed")
```

## Migration Status Tracking

To track which migrations have been applied, you can create a `schema_migrations` table:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_number VARCHAR(10) NOT NULL UNIQUE,
    migration_name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- After running migration 002
INSERT INTO schema_migrations (migration_number, migration_name) 
VALUES ('002', 'add_github_integration');
```

## Verification Queries

After running migration 002, verify the changes:

```sql
-- Check repositories columns
\d repositories

-- Check pipeline_runs table
\d pipeline_runs

-- Count rows
SELECT COUNT(*) FROM repositories;
SELECT COUNT(*) FROM pipeline_runs;

-- Check indexes
\di idx_repositories_github_id
\di idx_pipeline_runs_repository_id
```

## Best Practices

1. **Always backup** before running migrations in production
2. **Test migrations** on a dev/staging database first
3. **Run rollback scripts** only when necessary (data loss may occur)
4. **Document changes** in migration file comments
5. **Use transactions** where possible (PostgreSQL auto-wraps DDL in transactions)

## Troubleshooting

### Error: "relation already exists"
- The table/column already exists
- Safe to ignore if using `IF NOT EXISTS`
- Check if migration was already applied

### Error: "permission denied"
- User lacks sufficient privileges
- Run as database superuser or grant necessary permissions

### Error: "constraint violation"
- Existing data violates new constraint
- Update data before adding constraint
- Or modify constraint to be less restrictive

## Future Migrations

When creating new migrations:

1. Name files: `NNN_descriptive_name.sql` (e.g., `003_add_bug_reports.sql`)
2. Create corresponding rollback: `NNN_descriptive_name_rollback.sql`
3. Update this README with migration details
4. Test thoroughly before committing
