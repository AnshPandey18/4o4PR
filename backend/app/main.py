"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base
from .api import auth, users

# Import all models (so they're registered with Base)
from .models import User, Repository

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (allow React frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)

# Root endpoint
@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Welcome to 4o4PR API",
        "docs": "/docs",
        "health": "/api/health"
    }

# Health check
@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
