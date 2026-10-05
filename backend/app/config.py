"""Application configuration."""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    """Application settings."""
    
    # Project Info
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "4o4PR")
    DEBUG: bool = os.getenv("DEBUG", "True") == "True"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # CORS (Frontend URLs)
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

settings = Settings()

# Validate required settings
if not settings.SECRET_KEY:
    raise ValueError("SECRET_KEY not set in .env file")
if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env file")
