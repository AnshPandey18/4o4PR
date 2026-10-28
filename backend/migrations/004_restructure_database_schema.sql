-- Migration 004: Database Schema Restructuring
-- 
-- This migration restructures the database schema:
-- 1. Creates user_credentials table for storing GitHub tokens
-- 2. Removes unnecessary columns from repositories table
-- 3. Removes unnecessary columns from pipeline_runs table
-- 4. Moves encrypted_pat from repositories to user_credentials
--
-- Run this migration with:
-- psql -U admin -d 4o4_db -f migrations/004_restructure_database_schema.sql
--
-- Rollback:
-- psql -U admin -d 4o4_db -f migrations/004_restructure_database_schema_rollback.sql

-- ============================================================================
-- PART 1: Create user_credentials table
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_credentials (
    -- Primary key
    id SERIAL PRIMARY KEY,
    
    -- Foreign key (one token per user - unique constraint)
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    
    -- Token storage
    encrypted_token TEXT NOT NULL,
    token_last4 VARCHAR(4),
    
    -- Token metadata
    scopes TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Usage tracking
    last_used_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for user_credentials
CREATE INDEX IF NOT EXISTS idx_user_credentials_user_id ON user_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_user_credentials_created_at ON user_credentials(created_at DESC);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_credentials_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_user_credentials_updated_at ON user_credentials;
CREATE TRIGGER trigger_update_user_credentials_updated_at
    BEFORE UPDATE ON user_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_user_credentials_updated_at();

COMMENT ON TABLE user_credentials IS 'Stores encrypted GitHub Personal Access Tokens for users';
COMMENT ON COLUMN user_credentials.encrypted_token IS 'Fernet-encrypted GitHub PAT';
COMMENT ON COLUMN user_credentials.token_last4 IS 'Last 4 characters of token for display purposes';
COMMENT ON COLUMN user_credentials.scopes IS 'Comma-separated GitHub token scopes (e.g., repo,user)';

-- ============================================================================
-- PART 2: Migrate encrypted_pat from repositories to user_credentials
-- ============================================================================

-- Migrate existing encrypted PATs from repositories to user_credentials
-- Only migrate if user doesn't already have credentials
INSERT INTO user_credentials (user_id, encrypted_token, created_at, updated_at)
SELECT DISTINCT 
    r.owner_id,
    r.encrypted_pat,
    NOW(),
    NOW()
FROM repositories r
WHERE r.encrypted_pat IS NOT NULL
  AND r.encrypted_pat != ''
  AND NOT EXISTS (
      SELECT 1 FROM user_credentials uc WHERE uc.user_id = r.owner_id
  )
ON CONFLICT (user_id) DO NOTHING;

-- ============================================================================
-- PART 3: Clean up repositories table
-- ============================================================================

-- Delete all existing repository data (as requested)
-- This will cascade to pipeline_runs due to foreign key
DELETE FROM repositories;

-- Drop columns that are no longer needed
ALTER TABLE repositories 
DROP COLUMN IF EXISTS name,
DROP COLUMN IF EXISTS url,
DROP COLUMN IF EXISTS branch,
DROP COLUMN IF EXISTS owner_login,
DROP COLUMN IF EXISTS repo_name,
DROP COLUMN IF EXISTS stars_count,
DROP COLUMN IF EXISTS language,
DROP COLUMN IF EXISTS clone_size_mb,
DROP COLUMN IF EXISTS redis_cache_key,
DROP COLUMN IF EXISTS encrypted_pat,
DROP COLUMN IF EXISTS last_scan;

-- Make full_name NOT NULL (it's the main identifier now)
ALTER TABLE repositories 
ALTER COLUMN full_name SET NOT NULL;

-- Update description in case there are any issues (no data, but good for future)
ALTER TABLE repositories 
ALTER COLUMN description SET DEFAULT '';

-- ============================================================================
-- PART 4: Clean up pipeline_runs table
-- ============================================================================

-- Drop columns that are no longer needed
ALTER TABLE pipeline_runs
DROP COLUMN IF EXISTS user_id,
DROP COLUMN IF EXISTS run_id,
DROP COLUMN IF EXISTS orchestrator_root,
DROP COLUMN IF EXISTS import_roots,
DROP COLUMN IF EXISTS output_dir,
DROP COLUMN IF EXISTS config_file,
DROP COLUMN IF EXISTS "verbose",
DROP COLUMN IF EXISTS duration_seconds,
DROP COLUMN IF EXISTS error_traceback;

-- Add new columns if they don't exist
ALTER TABLE pipeline_runs
ADD COLUMN IF NOT EXISTS input_mode VARCHAR(50),
ADD COLUMN IF NOT EXISTS input_ref VARCHAR(255),
ADD COLUMN IF NOT EXISTS commit_sha VARCHAR(64),
ADD COLUMN IF NOT EXISTS task_id VARCHAR(255);

-- Add index for task_id
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_task_id ON pipeline_runs(task_id);

-- Update comments
COMMENT ON COLUMN pipeline_runs.input_mode IS 'Input mode: branch, tag, pr, commit';
COMMENT ON COLUMN pipeline_runs.input_ref IS 'Input reference: branch name, tag name, PR number, or commit SHA';
COMMENT ON COLUMN pipeline_runs.commit_sha IS 'Actual commit SHA that was processed';
COMMENT ON COLUMN pipeline_runs.task_id IS 'Background task ID (Celery, Redis Queue, etc.)';

-- ============================================================================
-- PART 5: Verify schema changes
-- ============================================================================

DO $$
DECLARE
    users_count INTEGER;
    repos_count INTEGER;
    runs_count INTEGER;
    creds_count INTEGER;
    repos_columns INTEGER;
    runs_columns INTEGER;
BEGIN
    -- Count rows
    SELECT COUNT(*) INTO users_count FROM users;
    SELECT COUNT(*) INTO repos_count FROM repositories;
    SELECT COUNT(*) INTO runs_count FROM pipeline_runs;
    SELECT COUNT(*) INTO creds_count FROM user_credentials;
    
    -- Count columns in repositories (should be 14)
    SELECT COUNT(*) INTO repos_columns 
    FROM information_schema.columns 
    WHERE table_name = 'repositories';
    
    -- Count columns in pipeline_runs (should be 14)
    SELECT COUNT(*) INTO runs_columns 
    FROM information_schema.columns 
    WHERE table_name = 'pipeline_runs';
    
    RAISE NOTICE '✓ Migration 004 completed successfully';
    RAISE NOTICE '  - users table: % rows', users_count;
    RAISE NOTICE '  - repositories table: % rows, % columns', repos_count, repos_columns;
    RAISE NOTICE '  - pipeline_runs table: % rows, % columns', runs_count, runs_columns;
    RAISE NOTICE '  - user_credentials table: % rows', creds_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Schema changes:';
    RAISE NOTICE '  - Created user_credentials table';
    RAISE NOTICE '  - Migrated encrypted_pat from repositories to user_credentials';
    RAISE NOTICE '  - Removed 11 columns from repositories';
    RAISE NOTICE '  - Removed 8 columns from pipeline_runs, added 4 new columns';
END $$;
