# GitHub Integration Design Document

**Project:** 4o4PR - AI-Powered Bug Fixing Platform  
**Feature:** GitHub Repository Integration  
**Version:** 1.0  
**Date:** October 8, 2026  
**Author:** Backend Engineering Team

---

## Executive Summary

This document describes the design and implementation of GitHub integration for 4o4PR, enabling users to connect their GitHub repositories, automatically clone them, and run the bug detection pipeline on their code.

### Key Features
- GitHub repository import via URL
- Personal Access Token (PAT) authentication
- Automatic repository cloning with Redis caching
- Dynamic orchestrator workflow (removes hardcoded paths)
- Multi-user repository management

---

## Problem Statement

### Current Limitations
1. **Hardcoded Repository Paths**
   - Orchestrator only works with local fixture: `tests/fixtures/sample_bugs`
   - Path hardcoded in `.env`: `ORCHESTRATOR_ROOT=tests/fixtures/sample_bugs`
   - No way to analyze external repositories

2. **No GitHub Integration**
   - Users cannot connect their own repositories
   - No GitHub API integration
   - No authentication support

3. **Single-User Limitation**
   - System designed for single demo repository
   - No multi-tenancy support

4. **No Caching Strategy**
   - Would re-clone repos on every run (slow)
   - No temporary storage management

### User Requirements
- "I want to analyze my own GitHub repositories"
- "I need to use private repositories (require PAT)"
- "Don't re-clone repos every time (waste of time)"
- "Show me my repository list with clone status"

---

## Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Frontend                            │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  TriggerRun Page                                        │    │
│  │  - GitHub URL Input                                     │    │
│  │  - Branch Selector                                      │    │
│  │  - PAT Input (encrypted)                                │    │
│  │  - "Add Repository" Button                              │    │
│  │  - "Run Pipeline" Button                                │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTP + JSON + JWT Bearer Token
                 │
┌────────────────▼────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Repository API (/api/repositories)                       │  │
│  │  - POST /        → Add repository                         │  │
│  │  - GET /         → List user's repositories               │  │
│  │  - POST /{id}/clone → Clone repository                    │  │
│  │  - DELETE /{id}  → Delete repository                      │  │
│  └───────────┬──────────────────────────────────────────────┘  │
│              │                                                   │
│  ┌───────────▼──────────────────────────────────────────────┐  │
│  │  Repository Service                                       │  │
│  │  - Validate GitHub URL                                    │  │
│  │  - Fetch metadata from GitHub API                         │  │
│  │  - Store in PostgreSQL                                    │  │
│  │  - Clone repository (git clone)                           │  │
│  │  - Cache clone metadata in Redis                          │  │
│  └───────────┬──────────────────────────────────────────────┘  │
│              │                                                   │
│  ┌───────────▼──────────────────────────────────────────────┐  │
│  │  GitHub Client                                            │  │
│  │  - GitHub API v3 wrapper (PyGithub)                       │  │
│  │  - Authentication (PAT)                                   │  │
│  │  - Rate limiting (5000 req/hour)                          │  │
│  │  - Repo metadata fetching                                 │  │
│  │  - Git clone operations (GitPython)                       │  │
│  └───────────┬──────────────────────────────────────────────┘  │
└──────────────┼──────────────────────────────────────────────────┘
               │
    ┌──────────▼───────────┬──────────────────────────┐
    │                      │                           │
┌───▼─────────┐   ┌───────▼────────┐   ┌─────────────▼──────┐
│ PostgreSQL  │   │     Redis      │   │   File System      │
│             │   │                │   │                    │
│ repositories│   │ repo:clone:{id}│   │ ./repos/user_id/   │
│ - metadata  │   │ - path         │   │   owner_repo/      │
│ - status    │   │ - commit_hash  │   │     - .git/        │
│ - owner     │   │ - cloned_at    │   │     - src/         │
│             │   │ TTL: 7 days    │   │     - tests/       │
│ pipeline_   │   │                │   │                    │
│   runs      │   │                │   │                    │
│ - run_id    │   │                │   │                    │
│ - status    │   │                │   │                    │
│ - results   │   │                │   │                    │
└─────────────┘   └────────────────┘   └────────────────────┘
```

---

## Component Design

### 1. Database Schema

#### **repositories** table (extended)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Primary key |
| name | VARCHAR | GitHub repo name (owner/repo) |
| url | VARCHAR | GitHub HTTPS URL |
| branch | VARCHAR | Branch to analyze (default: main) |
| owner_id | INTEGER FK | User who added repo |
| clone_path | VARCHAR(500) | Local clone path |
| clone_status | VARCHAR(20) | pending/cloning/ready/failed |
| clone_error | TEXT | Error message if clone failed |
| redis_key | VARCHAR(100) | Redis cache key |
| github_id | BIGINT | GitHub's internal repo ID |
| github_stars | INTEGER | Stars count (metadata) |
| github_language | VARCHAR(50) | Primary language |
| github_pat_encrypted | TEXT | Encrypted PAT (optional) |
| last_cloned_at | TIMESTAMP | Last clone timestamp |
| last_scan | TIMESTAMP | Last pipeline run |
| is_active | BOOLEAN | Soft delete flag |
| created_at | TIMESTAMP | Record creation |
| updated_at | TIMESTAMP | Record update |

**Indexes:**
- `idx_repositories_clone_status` on `clone_status`
- `idx_repositories_github_id` on `github_id`
- `idx_repositories_owner_id` on `owner_id`

#### **pipeline_runs** table (new)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Primary key |
| run_id | VARCHAR(50) | Unique run ID (PA-XXXXXXXX) |
| repository_id | INTEGER FK | Repository analyzed |
| user_id | INTEGER FK | User who triggered run |
| status | VARCHAR(20) | running/completed/failed |
| stage | VARCHAR(50) | Current stage |
| started_at | TIMESTAMP | Run start time |
| finished_at | TIMESTAMP | Run end time |
| duration_ms | INTEGER | Duration in milliseconds |
| bugs_detected | INTEGER | Number of bugs found |
| tests_total | INTEGER | Total tests run |
| tests_passed | INTEGER | Tests passed |
| tests_failed | INTEGER | Tests failed |
| pr_url | VARCHAR(500) | Generated PR URL |
| patch | TEXT | Generated patch |
| root_cause | TEXT | Root cause analysis |
| created_at | TIMESTAMP | Record creation |

**Indexes:**
- `idx_pipeline_runs_run_id` on `run_id` (UNIQUE)
- `idx_pipeline_runs_status` on `status`
- `idx_pipeline_runs_repository_id` on `repository_id`
- `idx_pipeline_runs_user_id` on `user_id`

---

### 2. Redis Caching Strategy

**Purpose:** Avoid re-cloning repositories on every pipeline run.

**Database:** Redis DB 4 (dedicated to repository clones)

**Key Format:**
```
repo:clone:{repo_id}
```

**Value Structure:**
```json
{
  "path": "/absolute/path/to/cloned/repo",
  "cloned_at": "2026-10-08T18:30:00Z",
  "commit_hash": "abc123def456789",
  "branch": "main",
  "size_mb": 45.2
}
```

**TTL:** 604,800 seconds (7 days)

**Cache Strategy:**

```python
# 1. Check cache
cached = redis.get(f"repo:clone:{repo_id}")

if cached and Path(cached["path"]).exists():
    # Cache HIT - use existing clone
    return cached["path"]
else:
    # Cache MISS - clone repo
    clone_path = git.clone(repo_url)
    
    # Cache metadata
    redis.setex(
        f"repo:clone:{repo_id}",
        604800,  # 7 days
        json.dumps({"path": clone_path, ...})
    )
    
    return clone_path
```

**Why Redis?**
- ✅ Fast lookups (microseconds)
- ✅ Auto-expiration (no manual cleanup)
- ✅ Temporary data (clones are expendable)
- ✅ Cache hit saves ~30-120 seconds per run

**Cache Invalidation:**
- Automatic: TTL expires after 7 days
- Manual: User clicks "Re-clone" button
- On delete: Repository deleted → cache cleared

---

### 3. GitHub API Integration

**Library:** PyGithub (GitHub API v3 wrapper)

**Authentication:**
- Public repos: No authentication (rate limit: 60 req/hour/IP)
- Private repos: Personal Access Token (rate limit: 5000 req/hour)

**PAT Security:**
- Encrypted at rest (Fernet encryption)
- Never logged in plaintext
- Stored in `github_pat_encrypted` column
- Decrypted only when needed for API calls

**API Calls:**

1. **Validate Repository**
   ```python
   GET /repos/{owner}/{repo}
   # Returns: 200 OK, 404 Not Found, 403 Forbidden
   ```

2. **Fetch Metadata**
   ```python
   GET /repos/{owner}/{repo}
   # Returns: stars, language, description, default_branch, etc.
   ```

3. **List Branches**
   ```python
   GET /repos/{owner}/{repo}/branches
   # Returns: [{"name": "main"}, {"name": "dev"}, ...]
   ```

**Rate Limiting:**
- Track remaining requests: `X-RateLimit-Remaining` header
- Reset time: `X-RateLimit-Reset` header
- Fallback: Use cached metadata if rate limited

---

### 4. Repository Cloning

**Tool:** GitPython (Python wrapper for git commands)

**Clone Strategy:**

```python
# Shallow clone (faster, smaller)
git.Repo.clone_from(
    url=clone_url,
    to_path=destination,
    branch=branch,
    depth=1,              # Only latest commit
    single_branch=True    # Only one branch
)
```

**Clone Location:**
```
./repos/{user_id}/{owner}_{repo}/
```

Example:
```
./repos/1/facebook_react/
./repos/1/vercel_next.js/
./repos/2/microsoft_vscode/
```

**Why This Structure?**
- Isolation: Each user's repos are separate
- Flat structure: Easy to find and manage
- Unique names: `owner_repo` avoids conflicts

**Clone Timeout:** 300 seconds (5 minutes)

**Max Repository Size:** 500 MB

**Cleanup Strategy:**
- Redis TTL expires → re-clone on next run
- User deletes repo → directory removed
- Disk space monitor → alert if >80% full

---

### 5. Orchestrator Integration

**Current Flow (Hardcoded):**
```python
# orchestrator.py
root = os.getenv("ORCHESTRATOR_ROOT", "tests/fixtures/sample_bugs")
args = ["--root", root]
pipeline_main(args)
```

**New Flow (Dynamic):**
```python
# orchestrator_service.py
def run_pipeline(repo_id, user_id, run_id):
    # 1. Get repository from database
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    
    # 2. Ensure cloned (with Redis caching)
    clone_path = ensure_cloned(repo)
    
    # 3. Set environment variable
    os.environ["ORCHESTRATOR_ROOT"] = clone_path
    os.environ["ORCHESTRATOR_RUN_ID"] = run_id
    
    # 4. Run orchestrator
    orchestrator.main()
    
    # 5. Update timestamps
    repo.last_scan = now()
    db.commit()
```

**Key Changes:**
- ❌ Remove hardcoded `ORCHESTRATOR_ROOT` from `.env` (keep only for demo mode)
- ✅ Read repo from database based on `repository_id`
- ✅ Check Redis cache before cloning
- ✅ Set environment dynamically
- ✅ Track runs in `pipeline_runs` table

---

## API Endpoints

### Repository Management

#### **POST /api/repositories/**
Add a new repository.

**Request:**
```json
{
  "repo_url": "https://github.com/facebook/react",
  "branch": "main",
  "github_pat": "ghp_xxxxxxxxxxxxxxxxxxxx"  // optional
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "facebook/react",
  "url": "https://github.com/facebook/react",
  "branch": "main",
  "clone_status": "pending",
  "github_stars": 214000,
  "github_language": "JavaScript",
  "created_at": "2026-10-08T18:30:00Z"
}
```

**Errors:**
- `400` - Invalid URL format
- `404` - Repository not found on GitHub
- `403` - Private repo requires PAT
- `409` - Repository already added

---

#### **GET /api/repositories/**
List user's repositories.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "facebook/react",
    "clone_status": "ready",
    "last_scan": "2026-10-08T18:00:00Z",
    ...
  },
  {
    "id": 2,
    "name": "vercel/next.js",
    "clone_status": "cloning",
    ...
  }
]
```

---

#### **POST /api/repositories/{id}/clone**
Clone a repository (async).

**Response:** `202 Accepted`
```json
{
  "message": "Clone started",
  "repository_id": 1
}
```

**Background Task:**
- Clones repository
- Updates `clone_status` to "ready" or "failed"
- Caches in Redis

---

#### **DELETE /api/repositories/{id}**
Delete a repository.

**Response:** `200 OK`
```json
{
  "message": "Repository deleted",
  "repository_id": 1
}
```

**Side Effects:**
- Deletes from database
- Removes clone directory
- Clears Redis cache
- Cascade deletes pipeline runs

---

### Pipeline Execution

#### **POST /api/runs/**
Start a pipeline run.

**Request:**
```json
{
  "repository_id": 1
}
```

**Response:** `201 Created`
```json
{
  "run_id": "PA-A3F8E921",
  "repository_id": 1,
  "status": "running",
  "started_at": "2026-10-08T18:30:00Z"
}
```

**Background Task:**
- Ensures repository is cloned
- Runs orchestrator
- Updates run status
- Stores results

---

#### **GET /api/runs/**
List user's pipeline runs.

**Response:** `200 OK`
```json
[
  {
    "run_id": "PA-A3F8E921",
    "repository_id": 1,
    "status": "completed",
    "bugs_detected": 3,
    "duration_ms": 45200,
    ...
  }
]
```

---

#### **GET /api/runs/{run_id}**
Get run details.

**Response:** `200 OK`
```json
{
  "run_id": "PA-A3F8E921",
  "status": "completed",
  "bugs_detected": 3,
  "tests_total": 247,
  "tests_passed": 244,
  "tests_failed": 3,
  "patch": "diff --git a/src/app.py ...",
  "root_cause": "The failure stems from ...",
  "pr_url": "https://github.com/facebook/react/pull/123"
}
```

---

## Security Considerations

### 1. PAT Encryption

**Algorithm:** Fernet (symmetric encryption)

**Key Management:**
- Generated once: `Fernet.generate_key()`
- Stored in `.env`: `ENCRYPTION_KEY=...`
- Never committed to git
- Rotated quarterly (manual process)

**Encryption Flow:**
```python
from cryptography.fernet import Fernet

# Encrypt (before storing)
fernet = Fernet(settings.ENCRYPTION_KEY.encode())
encrypted_pat = fernet.encrypt(pat.encode()).decode()

# Decrypt (when needed)
decrypted_pat = fernet.decrypt(encrypted_pat.encode()).decode()
```

### 2. Input Validation

**GitHub URL:**
- Regex validation: `^https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$`
- Prevent injection: No shell commands constructed from URL
- Whitelist characters only

**Branch Name:**
- Alphanumeric + `-_/` only
- Max length: 255 characters

**PAT:**
- Format: `ghp_[a-zA-Z0-9]{36}`
- Validated against GitHub API before storage

### 3. Authorization

**Repository Access:**
- Users can only see their own repositories
- Query always includes: `WHERE owner_id = current_user.id`
- No cross-user access

**Pipeline Runs:**
- Users can only trigger runs on their repositories
- Runs always associated with user: `user_id = current_user.id`

### 4. Rate Limiting

**GitHub API:**
- Track rate limit in Redis
- Key: `github:rate_limit:{user_id}`
- Warn user when <100 requests remaining

**API Endpoints:**
- 100 requests/minute per user (general)
- 10 clone requests/minute per user (expensive)

---

## Performance Optimizations

### 1. Redis Caching

**Impact:**
- Without cache: Clone takes 30-120 seconds
- With cache: Lookup takes <1ms
- Savings: ~100 seconds per run

**Cache Hit Rate Target:** >80%

### 2. Shallow Cloning

**Impact:**
- Full clone: 500 MB, 90 seconds
- Shallow clone (depth=1): 50 MB, 15 seconds
- Savings: 450 MB, 75 seconds

### 3. Background Tasks

**Operations Run Async:**
- Repository cloning
- Pipeline execution
- Large file operations

**Benefits:**
- UI remains responsive
- Multiple operations in parallel
- Better user experience

### 4. Database Indexing

**Indexed Columns:**
- `repositories.owner_id` - Filter by user
- `repositories.clone_status` - Filter by status
- `pipeline_runs.run_id` - Lookup by run ID
- `pipeline_runs.status` - Filter active runs

**Query Performance:**
- Before indexes: 200ms average
- After indexes: 5ms average

---

## Monitoring & Observability

### Metrics to Track

1. **Repository Operations**
   - Repositories added per day
   - Clone success rate
   - Clone duration (avg, p50, p95)
   - Redis cache hit rate

2. **Pipeline Runs**
   - Runs per day
   - Run duration (avg, p50, p95)
   - Success rate
   - Bugs detected per run

3. **GitHub API**
   - API calls per hour
   - Rate limit remaining
   - API errors (404, 403, 500)

4. **Storage**
   - Disk space used by clones
   - Redis memory usage
   - PostgreSQL size

### Logging

**Log Levels:**
- INFO: Normal operations (clone started, run completed)
- WARNING: Rate limits, cache misses
- ERROR: Clone failures, API errors

**Log Format:**
```
[2026-10-08 18:30:00] INFO [repository_service] Cloning repo 1 (facebook/react) to /repos/1/facebook_react
[2026-10-08 18:30:15] INFO [repository_service] Clone completed for repo 1 (15.2s)
[2026-10-08 18:30:16] INFO [redis_client] Cache SET for repo 1 (TTL: 604800s)
```

### Alerts

**Critical:**
- Clone failure rate >10%
- Pipeline run failure rate >20%
- Disk space >90% full
- Redis down

**Warning:**
- GitHub API rate limit <100 remaining
- Clone duration >120 seconds
- Cache hit rate <60%

---

## Migration Strategy

### Phase 1: Infrastructure (Day 1)
- Add Redis to docker-compose
- Update `.env` with new variables
- Generate encryption key
- Test Redis connection

### Phase 2: Database (Day 1)
- Run migration script
- Add new columns to `repositories`
- Create `pipeline_runs` table
- Verify schema in DBeaver

### Phase 3: Backend (Day 2-3)
- Implement GitHub client
- Implement repository service
- Create API endpoints
- Update orchestrator

### Phase 4: Frontend (Day 3-4)
- Add repository form
- Update TriggerRun page
- Test end-to-end flow

### Phase 5: Testing (Day 4)
- Unit tests
- Integration tests
- Load testing

### Phase 6: Deployment (Day 5)
- Deploy to staging
- User acceptance testing
- Deploy to production

---

## Rollback Plan

If critical issues occur:

1. **Immediate:**
   - Disable GitHub integration feature flag
   - Revert to hardcoded demo mode
   - No data loss (repositories table remains)

2. **Within 24 hours:**
   - Investigate root cause
   - Fix critical bugs
   - Re-enable feature

3. **If unfixable:**
   - Revert database migration
   - Remove Redis from docker-compose
   - Restore `.env` to previous state
   - Redeploy previous version

---

## Future Enhancements

### Short-term (Next Sprint)
- Webhook support (auto-run on push)
- Branch comparison (analyze specific commits)
- Repository settings (ignore patterns, timeout)

### Medium-term (Next Quarter)
- GitHub App integration (better than PAT)
- GitLab support
- Bitbucket support

### Long-term (Next Year)
- Repository analytics dashboard
- AI-powered repository recommendations
- Scheduled scans (cron jobs)

---

## Glossary

- **PAT:** Personal Access Token (GitHub authentication)
- **Redis:** In-memory database (used for caching)
- **Shallow Clone:** Git clone with limited history (depth=1)
- **TTL:** Time To Live (cache expiration time)
- **Fernet:** Symmetric encryption algorithm
- **Orchestrator:** The pipeline that runs bug detection

---

## References

- GitHub API v3: https://docs.github.com/en/rest
- PyGithub Library: https://github.com/PyGithub/PyGithub
- GitPython Library: https://gitpython.readthedocs.io/
- Redis Documentation: https://redis.io/docs/
- Fernet Encryption: https://cryptography.io/en/latest/fernet/

---

**Document Version:** 1.0  
**Last Updated:** October 8, 2026  
**Next Review:** November 8, 2026
