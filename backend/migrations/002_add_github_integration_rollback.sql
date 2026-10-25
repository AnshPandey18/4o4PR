-- Rollback Migration 002: GitHub Integration
-- This script removes all changes made by 002_add_github_integration.sql
--
-- ⚠️  WARNING: This will DELETE all pipeline_runs data!
-- Run this rollback with:
-- psql -U admin -d 4o4_db -f migrations/002_add_github_integration_rollback.sql

-- ============================================================================
-- PART 1: Drop pipeline_runs table and related objects
-- ============================================================================

-- Drop trigger
DROP TRIGGER IF EXISTS trigger_update_pipeline_runs_updated_at ON pipeline_runs;

-- Drop trigger function
DROP FUNCTION IF EXISTS update_pipeline_runs_updated_at();

-- Drop table (CASCADE removes dependent objects)
DROP TABLE IF EXISTS pipeline_runs CASCADE;

RAISE NOTICE '✓ Dropped pipeline_runs table and related objects';

-- ============================================================================
-- PART 2: Remove columns from repositories table
-- ============================================================================

-- Drop indexes first
DROP INDEX IF EXISTS idx_repositories_github_id;
DROP INDEX IF EXISTS idx_repositories_owner_login;
DROP INDEX IF EXISTS idx_repositories_clone_status;
-- Note: idx_repositories_owner_id may have existed before, so we keep it

-- Drop check constraint
ALTER TABLE repositories DROP CONSTRAINT IF EXISTS repositories_clone_status_check;

-- Remove GitHub Integration columns
ALTER TABLE repositories 
DROP COLUMN IF EXISTS github_id,
DROP COLUMN IF EXISTS full_name,
DROP COLUMN IF EXISTS owner_login,
DROP COLUMN IF EXISTS repo_name,
DROP COLUMN IF EXISTS default_branch,
DROP COLUMN IF EXISTS is_private,
DROP COLUMN IF EXISTS stars_count,
DROP COLUMN IF EXISTS language,
DROP COLUMN IF EXISTS clone_path,
DROP COLUMN IF EXISTS clone_status,
DROP COLUMN IF EXISTS cloned_at,
DROP COLUMN IF EXISTS clone_size_mb,
DROP COLUMN IF EXISTS redis_cache_key,
DROP COLUMN IF EXISTS encrypted_pat;

RAISE NOTICE '✓ Removed GitHub Integration columns from repositories table';

-- ============================================================================
-- Rollback complete
-- ============================================================================

DO $$
DECLARE
    repos_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO repos_count FROM repositories;
    
    RAISE NOTICE '✓ Rollback 002 completed successfully';
    RAISE NOTICE '  - repositories table restored: % rows remaining', repos_count;
    RAISE NOTICE '  - pipeline_runs table removed';
END $$;
