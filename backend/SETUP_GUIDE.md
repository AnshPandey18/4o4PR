# Pre-Phase 4 Setup Guide

Complete these steps to prepare for Phase 4 (Frontend Integration).

---

## Step 1: Start Docker Services ✅ (Partially Done)

### Check Current Status
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Current Status:**
- ✅ PostgreSQL (4o4_postgres) - Running on port 5432
- ❌ Redis (4o4_redis) - NOT running

### Start Redis
```powershell
# Option 1: Using docker-compose (recommended)
docker-compose up -d redis

# Option 2: Check if redis container exists and start it
docker start 4o4_redis

# Option 3: If redis container doesn't exist, docker-compose will create it
cd "d:\Code - Programming\4o4"
docker-compose up -d
```

### Verify Services
```powershell
# Check PostgreSQL
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "SELECT version();"

# Check Redis
docker exec -it 4o4_redis redis-cli ping
# Should return: PONG
```

---

## Step 2: Run Database Migration 002

### Option A: Using Python Script (Recommended)
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python run_migration.py
```

### Option B: Using Docker exec (If Python script fails)
```powershell
# Copy migration file to container
docker cp backend/migrations/002_add_github_integration.sql 4o4_postgres:/tmp/

# Execute migration
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -f /tmp/002_add_github_integration.sql
```

### Verify Migration
```powershell
# Check repositories table (should have 24 columns)
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "\d repositories"

# Check pipeline_runs table (should exist)
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "\d pipeline_runs"

# Check row counts
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "SELECT COUNT(*) FROM repositories;"
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "SELECT COUNT(*) FROM pipeline_runs;"
```

**Expected Output:**
```
✓ repositories table: 24 columns
✓ pipeline_runs table: 20 columns
- repositories: X rows
- pipeline_runs: 0 rows (initially)
```

---

## Step 3: Start Backend Server

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**Expected Output:**
```
INFO:     Will watch for changes in these directories: ['D:\\Code - Programming\\4o4\\backend']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [XXXXX] using WatchFiles
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
✓ Redis connected: localhost:6379 (DB 4)
```

---

## Step 4: Test API Endpoints

### 4.1 Check API Documentation
Open in browser: http://localhost:8000/docs

**Should see:**
- Authentication endpoints (register, login)
- User endpoints (me)
- Repository endpoints (10 endpoints)
- Pipeline Run endpoints (8 endpoints)

### 4.2 Register User
```powershell
$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/auth/register" `
  -ContentType "application/json" `
  -Body '{"email":"test@example.com","password":"password123","full_name":"Test User"}'

$response
```

**Expected:** User created with ID

### 4.3 Login
```powershell
$loginResponse = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"test@example.com","password":"password123"}'

$token = $loginResponse.access_token
Write-Host "Token: $token"
```

**Expected:** JWT token returned

### 4.4 Test Repository API
```powershell
# Add repository (replace YOUR_GITHUB_PAT with actual token)
$headers = @{
  "Authorization" = "Bearer $token"
  "Content-Type" = "application/json"
}

$repoBody = @{
  url = "https://github.com/octocat/Hello-World"
  branch = "master"
  personal_access_token = "ghp_YOUR_GITHUB_PAT"  # Optional for public repos
  description = "Test repository"
} | ConvertTo-Json

$repo = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/repositories" `
  -Headers $headers -Body $repoBody

$repoId = $repo.id
Write-Host "Repository ID: $repoId"
```

**Expected:** Repository created with metadata

### 4.5 Test Clone API
```powershell
$cloneBody = @{
  branch = "master"
  force = $false
} | ConvertTo-Json

$cloneResult = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/repositories/$repoId/clone" `
  -Headers $headers -Body $cloneBody

$cloneResult
```

**Expected:** Repository cloned, path returned

### 4.6 Test Pipeline Run API
```powershell
# Trigger pipeline
$triggerBody = @{
  repository_id = $repoId
  import_roots = "src"
  verbose = $true
} | ConvertTo-Json

$runResult = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/pipeline-runs/trigger" `
  -Headers $headers -Body $triggerBody

$runId = $runResult.run_id
Write-Host "Run ID: $runId"
```

**Expected:** Pipeline run created with status "queued"

---

## Step 5: Test Orchestrator

### 5.1 Run Orchestrator with Run ID
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python orchestrator_db.py --run-id $runId
```

**Expected Output:**
```
============================================================
  4o4PR Pipeline Orchestrator (Database Mode)
============================================================
✓ Loaded run configuration:
  Run ID: run_XXXXXXXXX_XXXXXX
  Repository: octocat/Hello-World
  Clone path: D:\Code - Programming\4o4\backend\repos\1\octocat_Hello-World
  Import roots: src
  Output dir: runs/run_XXXXXXXXX_XXXXXX
  Verbose: True
  Current status: queued

📝 Status updated: running
📂 Working directory: D:\Code - Programming\4o4\backend\repos\1\octocat_Hello-World
📊 Output directory: runs/run_XXXXXXXXX_XXXXXX

============================================================
  Stage 1: Bug Detection
============================================================
🐛 Bugs detected: 5

============================================================
  Stage 2: Root Cause Analysis
============================================================

============================================================
  Stage 3: Patch Generation
============================================================
📄 Patches generated: 3

============================================================
  Stage 4: Patch Validation
============================================================
✅ Bugs fixed: 2

============================================================
  Pipeline Complete!
============================================================
✓ Bugs detected: 5
✓ Patches generated: 3
✓ Bugs fixed: 2
✓ Success rate: 40.0%

📝 Status updated: completed
⏱️  Pipeline finished in XX.Xs
```

### 5.2 Check Run Results
```powershell
$runDetails = Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/pipeline-runs/$runId" `
  -Headers $headers

$runDetails | ConvertTo-Json
```

**Expected:** Run details with results and status "completed"

---

## Step 6: Test Cache Performance

### 6.1 Check Cache Stats
```powershell
$cacheStats = Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/repositories/cache/stats" `
  -Headers $headers

$cacheStats
```

**Expected:**
```json
{
  "connected": true,
  "total_clone_keys": 1,
  "keyspace_hits": X,
  "keyspace_misses": Y,
  "hit_rate": Z.Z,
  "message": "Cache hit rate: Z.Z%"
}
```

### 6.2 Test Cache Hit (Clone Again)
```powershell
# Clone same repository again (should use cache)
$cloneResult2 = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/repositories/$repoId/clone" `
  -Headers $headers -Body $cloneBody

Write-Host "Cache used: $($cloneResult2.cached)"
```

**Expected:** Clone completes in <1 second (cache hit)

---

## Step 7: Test Pipeline Run Statistics

```powershell
$stats = Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/pipeline-runs/stats/summary" `
  -Headers $headers

$stats | ConvertTo-Json
```

**Expected:**
```json
{
  "total_runs": 1,
  "pending_runs": 0,
  "running_runs": 0,
  "completed_runs": 1,
  "failed_runs": 0,
  "cancelled_runs": 0,
  "total_bugs_detected": 5,
  "total_bugs_fixed": 2,
  "total_patches_generated": 3,
  "average_success_rate": 40.0,
  "average_duration_seconds": XX.X
}
```

---

## Troubleshooting

### Issue: PostgreSQL Not Running
```powershell
docker start 4o4_postgres
# Wait 10 seconds for health check
Start-Sleep -Seconds 10
docker ps
```

### Issue: Redis Not Running
```powershell
docker-compose up -d redis
# Verify
docker exec -it 4o4_redis redis-cli ping
```

### Issue: Migration Already Applied
```
ERROR:  column "github_id" of relation "repositories" already exists
```
**Solution:** Migration already applied, this is OK. Skip to next step.

### Issue: Cannot Connect to Redis
```powershell
# Check Redis is running
docker ps | Select-String redis

# Check Redis logs
docker logs 4o4_redis

# Restart Redis
docker restart 4o4_redis
```

### Issue: Backend Won't Start
```powershell
# Check if port 8000 is already in use
netstat -ano | findstr :8000

# Kill process using port 8000 (if needed)
# taskkill /PID <PID> /F

# Restart backend
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

### Issue: Clone Path Not Found
```
ValueError: Clone path does not exist: D:\Code - Programming\4o4\backend\repos\...
```
**Solution:** Clone the repository first via API before running pipeline.

---

## Checklist

Use this checklist to track your progress:

- [ ] PostgreSQL running (port 5432)
- [ ] Redis running (port 6379)
- [ ] Migration 002 applied successfully
- [ ] Backend server started (http://localhost:8000)
- [ ] API documentation accessible (http://localhost:8000/docs)
- [ ] User registered and logged in
- [ ] Repository added via API
- [ ] Repository cloned successfully
- [ ] Pipeline run triggered via API
- [ ] Orchestrator executed successfully
- [ ] Run results saved to database
- [ ] Cache statistics showing hits
- [ ] All tests passing

---

## Quick Commands Reference

### Start All Services
```powershell
cd "d:\Code - Programming\4o4"
docker-compose up -d

cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

### Check All Services
```powershell
# Docker services
docker ps

# PostgreSQL
docker exec -it 4o4_postgres psql -U admin -d 4o4_db -c "SELECT COUNT(*) FROM users;"

# Redis
docker exec -it 4o4_redis redis-cli ping

# Backend API
Invoke-RestMethod -Uri "http://localhost:8000/api/health"
```

### Stop All Services
```powershell
# Stop backend (Ctrl+C in terminal)

# Stop Docker services
cd "d:\Code - Programming\4o4"
docker-compose down
```

---

## Next: Phase 4 - Frontend Integration

Once all tests pass, you're ready for Phase 4!

**Phase 4 will update:**
- `frontend/src/components/TriggerRun.jsx`
- Create `frontend/src/api/repositories.js`
- Create `frontend/src/api/pipelineRuns.js`
- Create `frontend/src/components/RepositoryList.jsx`
- Create `frontend/src/components/RunHistory.jsx`

**Estimated time:** 3-4 hours

---

**Setup Guide Version:** 1.0  
**Last Updated:** October 9, 2026  
**Status:** Ready for Testing
