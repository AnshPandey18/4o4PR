"""Script to run database migration 002."""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Run migration 002: GitHub Integration."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    print(f"📦 Connecting to database...")
    print(f"   URL: {database_url.replace('admin123', '****')}")
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✓ Connected to PostgreSQL: {version}")
        
        # Read migration file
        migration_file = "migrations/002_add_github_integration.sql"
        if not os.path.exists(migration_file):
            print(f"❌ Migration file not found: {migration_file}")
            return False
        
        print(f"\n📄 Reading migration file: {migration_file}")
        with open(migration_file, "r") as f:
            migration_sql = f.read()
        
        # Count statements (rough estimate)
        statement_count = migration_sql.count(";")
        print(f"   Statements to execute: ~{statement_count}")
        
        # Execute migration
        print(f"\n🔄 Executing migration 002...")
        with engine.begin() as conn:
            # Execute the entire migration as one transaction
            conn.execute(text(migration_sql))
        
        print(f"✓ Migration executed successfully!")
        
        # Verify migration
        print(f"\n🔍 Verifying migration...")
        with engine.connect() as conn:
            # Check repositories columns
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'repositories' 
                ORDER BY ordinal_position;
            """))
            repo_columns = result.fetchall()
            print(f"✓ repositories table: {len(repo_columns)} columns")
            
            # Check if new columns exist
            new_columns = ["github_id", "clone_status", "encrypted_pat", "redis_cache_key"]
            found_columns = [col[0] for col in repo_columns]
            for col in new_columns:
                if col in found_columns:
                    print(f"  ✓ {col} exists")
                else:
                    print(f"  ✗ {col} MISSING")
                    return False
            
            # Check pipeline_runs table
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'pipeline_runs' 
                ORDER BY ordinal_position;
            """))
            run_columns = result.fetchall()
            print(f"\n✓ pipeline_runs table: {len(run_columns)} columns")
            
            # Check row counts
            result = conn.execute(text("SELECT COUNT(*) FROM repositories;"))
            repo_count = result.fetchone()[0]
            print(f"\n📊 Current data:")
            print(f"  - repositories: {repo_count} rows")
            
            result = conn.execute(text("SELECT COUNT(*) FROM pipeline_runs;"))
            run_count = result.fetchone()[0]
            print(f"  - pipeline_runs: {run_count} rows")
        
        print(f"\n✅ Migration 002 completed successfully!")
        print(f"\nNext steps:")
        print(f"  1. Start Redis: docker-compose up -d redis")
        print(f"  2. Start backend: uvicorn app.main:app --reload")
        print(f"  3. Test API: curl http://localhost:8000/docs")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("  Database Migration 002: GitHub Integration")
    print("=" * 60)
    print()
    
    success = run_migration()
    sys.exit(0 if success else 1)
