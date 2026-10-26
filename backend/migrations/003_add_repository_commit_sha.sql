-- Migration 003: Record the checked-out commit SHA for cloned repositories
--
-- Run this migration with:
-- psql -U admin -d 4o4_db -f migrations/003_add_repository_commit_sha.sql
--
-- Rollback:
-- psql -U admin -d 4o4_db -c "ALTER TABLE repositories DROP COLUMN IF EXISTS commit_sha;"

ALTER TABLE repositories
ADD COLUMN IF NOT EXISTS commit_sha VARCHAR(64);

COMMENT ON COLUMN repositories.commit_sha IS 'SHA of the git commit that was checked out during the last successful clone';
