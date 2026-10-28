-- Migration 004 Rollback: Restore Previous Database Schema
--
-- This rollback migration restores the database to its previous state
--
-- Run this rollback with:
-- psql -U admin -d 4o4_db -f migrations/004_restructure_database_schema_rollback.sql

-- ============================================================================
-- PART 1: Restore pipeline_runs columns
-- ============================================================================

-- Add back removed columns
ALTER TABLE pipeline_runs
ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS run_id VARCHAR(100) UNIQUE,
ADD COLUMN IF NOT EXISTS orchestrator_root TEXT,
ADD COLUMN IF NOT EXISTS import_roots TEXT,
ADD COLUMN IF NOT EXISTS output_dir TEXT,
ADD COLUMN IF NOT EXISTS config_file TEXT,
ADD COLUMN IF NOT EXISTS "verbose" BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS duration_seconds INTEGER,
ADD COLUMN IF NOT EXISTS error_traceback TEXT;

-- Remove new columns
ALTER TABLE pipeline_runs
DROP COLUMN IF EXISTS input_mode,
DROP COLUMN IF EXISTS input_ref,
DROP COLUMN IF EXISTS commit_sha,
DROP COLUMN IF EXISTS task_id;

-- Restore indexes
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_user_id ON pipeline_runs(user_id);
DROP INDEX IF EXISTS idx_pipeline_runs_task_id;

-- ============================================================================
-- PART 2: Restore repositories columns
-- ============================================================================

-- Add back removed columns
ALTER TABLE repositories
ADD COLUMN IF NOT EXISTS name VARCHAR(255),
ADD COLUMN IF NOT EXISTS url VARCHAR(255),
ADD COLUMN IF NOT EXISTS branch VARCHAR(100) DEFAULT 'main',
ADD COLUMN IF NOT EXISTS owner_login VARCHAR(255),
ADD COLUMN IF NOT EXISTS repo_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS stars_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS language VARCHAR(100),
ADD COLUMN IF NOT EXISTS clone_size_mb NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS redis_cache_key VARCHAR(255),
ADD COLUMN IF NOT EXISTS encrypted_pat TEXT,
ADD COLUMN IF NOT EXISTS last_scan TIMESTAMP WITH TIME ZONE;

-- Restore full_name to nullable
ALTER TABLE repositories
ALTER COLUMN full_name DROP NOT NULL;

-- Restore indexes
CREATE INDEX IF NOT EXISTS idx_repositories_owner_login ON repositories(owner_login);

-- ============================================================================
-- PART 3: Migrate encrypted tokens back to repositories
-- ============================================================================

-- Migrate the first encrypted token back to each user's repository
-- This is a best-effort migration and may not restore the exact previous state
WITH first_repo_per_user AS (
    SELECT DISTINCT ON (owner_id) 
        id as repo_id,
        owner_id
    FROM repositories
    ORDER BY owner_id, created_at
)
UPDATE repositories r
SET encrypted_pat = uc.encrypted_token
FROM user_credentials uc
JOIN first_repo_per_user frpu ON frpu.owner_id = uc.user_id
WHERE r.id = frpu.repo_id
  AND uc.encrypted_token IS NOT NULL;

-- ============================================================================
-- PART 4: Drop user_credentials table
-- ============================================================================

DROP TRIGGER IF EXISTS trigger_update_user_credentials_updated_at ON user_credentials;
DROP FUNCTION IF EXISTS update_user_credentials_updated_at();
DROP TABLE IF EXISTS user_credentials CASCADE;

-- ============================================================================
-- PART 5: Verify rollback
-- ============================================================================

DO $$
DECLARE
    users_count INTEGER;
    repos_count INTEGER;
    runs_count INTEGER;
    creds_exists BOOLEAN;
BEGIN
    -- Count rows
    SELECT COUNT(*) INTO users_count FROM users;
    SELECT COUNT(*) INTO repos_count FROM repositories;
    SELECT COUNT(*) INTO runs_count FROM pipeline_runs;
    
    -- Check if user_credentials still exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'user_credentials'
    ) INTO creds_exists;
    
    RAISE NOTICE '✓ Migration 004 rollback completed successfully';
    RAISE NOTICE '  - users table: % rows', users_count;
    RAISE NOTICE '  - repositories table: % rows', repos_count;
    RAISE NOTICE '  - pipeline_runs table: % rows', runs_count;
    RAISE NOTICE '  - user_credentials table exists: %', creds_exists;
    RAISE NOTICE '';
    RAISE NOTICE 'Rollback changes:';
    RAISE NOTICE '  - Dropped user_credentials table';
    RAISE NOTICE '  - Restored encrypted_pat to repositories';
    RAISE NOTICE '  - Restored all removed columns to repositories and pipeline_runs';
END $$;
