# Backend Quick Start Guide

## 🚀 Starting the Backend (Simple)

### Option 1: One Command (Recommended)
```powershell
cd "D:\Code - Programming\4o4\backend"
.\start.ps1
```

### Option 2: Manual Steps
```powershell
# 1. Navigate to backend folder
cd "D:\Code - Programming\4o4\backend"

# 2. Make sure Docker Desktop is running
docker ps

# 3. Start PostgreSQL (if not running)
docker-compose -f ../docker-compose.yml up -d postgres

# 4. Activate virtual environment
.\venv\Scripts\activate

# 5. Start backend
uvicorn app.main:app --reload
```

Backend will run at: **http://127.0.0.1:8000**

---

## 🧪 Testing the API

### Option 1: Automated Test
```powershell
.\test-api.ps1
```

### Option 2: Open Swagger UI
Open in browser: **http://127.0.0.1:8000/docs**

### Option 3: Manual Tests

**Test Registration:**
```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/auth/register" `
  -ContentType "application/json" `
  -Body '{"email":"test@example.com","password":"Test1234!","full_name":"Test User"}'
```

**Test Login:**
```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"test@example.com","password":"Test1234!"}'
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "Docker is not running"
**Solution:** Start Docker Desktop
1. Press Windows Key
2. Type "Docker Desktop"
3. Open Docker Desktop
4. Wait for it to start

---

### Issue 2: "Port 8000 is already in use"
**Solution:** Kill the process using port 8000
```powershell
# Find the process
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess

# Kill it
taskkill /PID <process_id> /F
```

---

### Issue 3: "ModuleNotFoundError"
**Solution:** Install dependencies
```powershell
cd "D:\Code - Programming\4o4\backend"
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

### Issue 4: Database connection error
**Check PostgreSQL is running:**
```powershell
docker ps --filter "name=4o4_postgres"
```

**Check logs:**
```powershell
docker logs 4o4_postgres
```

**Restart PostgreSQL:**
```powershell
docker restart 4o4_postgres
```

---

### Issue 5: Virtual environment not found
**Recreate it:**
```powershell
cd "D:\Code - Programming\4o4\backend"
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

## 📊 Check Status

**Backend status:**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000"
```
Should return: `{"message": "4o4PR API is running"}`

**Database status:**
```powershell
docker ps --filter "name=4o4_postgres"
```
Should show STATUS as "Up" and "healthy"

**Check users in database (via DBeaver):**
```sql
SELECT * FROM users;
```

---

## 🔑 API Endpoints

### Public Endpoints (No Auth)
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Get JWT token

### Protected Endpoints (Requires Bearer Token)
- `GET /api/users/me` - Get current user profile

---

## 🛠️ Development Tips

**Hot Reload:** The `--reload` flag automatically restarts the server when you change code.

**View Logs:** Backend logs show SQL queries (DEBUG=True in .env)

**Interactive API Docs:** 
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

**Test with curl (PowerShell):**
```powershell
$token = (Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/auth/login" -ContentType "application/json" -Body '{"email":"test@example.com","password":"Test1234!"}').access_token

Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/users/me" -Headers @{Authorization="Bearer $token"}
```

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings
│   ├── database.py          # DB connection
│   ├── api/
│   │   ├── auth.py          # Registration, login
│   │   └── users.py         # User endpoints
│   ├── models/
│   │   └── user.py          # SQLAlchemy model
│   ├── schemas/
│   │   └── user.py          # Pydantic schemas
│   └── utils/
│       └── security.py      # JWT, password hashing
├── .env                     # Environment variables
├── requirements.txt         # Dependencies
├── start.ps1               # Quick start script
└── test-api.ps1            # API testing script
```

---

## 🔐 Security Notes

- Passwords are hashed with bcrypt (cost factor 12)
- JWT tokens expire in 60 minutes
- SECRET_KEY is in .env (never commit this!)
- Database credentials are in docker-compose.yml (change for production!)

---

## 📝 Next Steps

1. Start frontend: `cd ../frontend && npm run dev`
2. Test full flow: Register → Login → Dashboard
3. Check DBeaver to see users table populated
4. Read API docs at http://127.0.0.1:8000/docs
