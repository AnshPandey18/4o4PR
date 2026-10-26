-- Migration 002: GitHub Integration
-- Add columns to repositories table and create pipeline_runs table
-- 
-- Run this migration with:
-- psql -U admin -d 4o4_db -f migrations/002_add_github_integration.sql
--
-- Rollback:
-- psql -U admin -d 4o4_db -f migrations/002_add_github_integration_rollback.sql

-- ============================================================================
-- PART 1: Add GitHub Integration columns to repositories table
-- ============================================================================

-- Add GitHub-specific columns
ALTER TABLE repositories 
ADD COLUMN IF NOT EXISTS github_id BIGINT UNIQUE,
ADD COLUMN IF NOT EXISTS full_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS owner_login VARCHAR(255),
ADD COLUMN IF NOT EXISTS repo_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS default_branch VARCHAR(100) DEFAULT 'main',
ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS stars_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS language VARCHAR(100);

-- Add clone tracking columns
ALTER TABLE repositories
ADD COLUMN IF NOT EXISTS clone_path TEXT,
ADD COLUMN IF NOT EXISTS clone_status VARCHAR(50) DEFAULT 'not_cloned',
ADD COLUMN IF NOT EXISTS cloned_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS clone_size_mb NUMERIC(10,2);

-- Add Redis cache tracking
ALTER TABLE repositories
ADD COLUMN IF NOT EXISTS redis_cache_key VARCHAR(255);

-- Add PAT (Personal Access Token) storage
ALTER TABLE repositories
ADD COLUMN IF NOT EXISTS encrypted_pat TEXT;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_repositories_github_id ON repositories(github_id);
CREATE INDEX IF NOT EXISTS idx_repositories_owner_login ON repositories(owner_login);
CREATE INDEX IF NOT EXISTS idx_repositories_clone_status ON repositories(clone_status);
CREATE INDEX IF NOT EXISTS idx_repositories_owner_id ON repositories(owner_id);

-- Update clone_status check constraint
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'repositories_clone_status_check'
    ) THEN
        ALTER TABLE repositories 
        ADD CONSTRAINT repositories_clone_status_check 
        CHECK (clone_status IN ('not_cloned', 'cloning', 'cloned', 'failed', 'updating'));
    END IF;
END $$;

-- ============================================================================
-- PART 2: Create pipeline_runs table
-- ============================================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    -- Primary key
    id SERIAL PRIMARY KEY,
    
    -- Foreign keys
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Run metadata
    run_id VARCHAR(100) UNIQUE NOT NULL,  -- e.g., "run_20261008_143022"
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    
    -- Orchestrator configuration
    orchestrator_root TEXT NOT NULL,  -- Path to cloned repo
    import_roots TEXT,  -- Comma-separated import roots (e.g., "src,lib")
    output_dir TEXT,  -- Where results are stored
    config_file TEXT,  -- Path to settings.yaml if used
    "verbose" BOOLEAN DEFAULT TRUE,  -- Note: quoted because verbose is a reserved word
    
    -- Execution tracking
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Results
    bugs_detected INTEGER DEFAULT 0,
    bugs_fixed INTEGER DEFAULT 0,
    patches_generated INTEGER DEFAULT 0,
    
    -- Error tracking
    error_message TEXT,
    error_traceback TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT pipeline_runs_status_check 
        CHECK (status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled'))
);

-- Indexes for pipeline_runs
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_repository_id ON pipeline_runs(repository_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_user_id ON pipeline_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id ON pipeline_runs(run_id);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_pipeline_runs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_pipeline_runs_updated_at ON pipeline_runs;
CREATE TRIGGER trigger_update_pipeline_runs_updated_at
    BEFORE UPDATE ON pipeline_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_pipeline_runs_updated_at();

-- ============================================================================
-- PART 3: Data cleanup and validation
-- ============================================================================

-- Update existing repositories with default values
UPDATE repositories 
SET 
    clone_status = 'not_cloned',
    default_branch = COALESCE(branch, 'main')
WHERE clone_status IS NULL;

-- ============================================================================
-- PART 4: Add helpful comments
-- ============================================================================

COMMENT ON TABLE repositories IS 'GitHub repositories tracked by users';
COMMENT ON COLUMN repositories.github_id IS 'GitHub API repository ID (unique across GitHub)';
COMMENT ON COLUMN repositories.encrypted_pat IS 'Fernet-encrypted GitHub Personal Access Token';
COMMENT ON COLUMN repositories.clone_path IS 'Local filesystem path where repo is cloned';
COMMENT ON COLUMN repositories.clone_status IS 'Current clone status: not_cloned, cloning, cloned, failed, updating';
COMMENT ON COLUMN repositories.redis_cache_key IS 'Redis key for clone metadata cache (format: clone:{user_id}:{repo_id})';

COMMENT ON TABLE pipeline_runs IS 'Orchestrator pipeline execution history';
COMMENT ON COLUMN pipeline_runs.run_id IS 'Unique identifier for this pipeline run';
COMMENT ON COLUMN pipeline_runs.orchestrator_root IS 'Path to cloned repository used as orchestrator root';

-- ============================================================================
-- Migration complete
-- ============================================================================

-- Verify migration
DO $$
DECLARE
    repos_count INTEGER;
    runs_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO repos_count FROM repositories;
    SELECT COUNT(*) INTO runs_count FROM pipeline_runs;
    
    RAISE NOTICE '✓ Migration 002 completed successfully';
    RAISE NOTICE '  - repositories table: % rows', repos_count;
    RAISE NOTICE '  - pipeline_runs table: % rows', runs_count;
END $$;
