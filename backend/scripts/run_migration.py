"""Script to run database migrations."""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration(migration_number: str = "004"):
    """Run a specific database migration."""
    
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
        migration_file = f"migrations/{migration_number}_*.sql"
        import glob
        matching_files = glob.glob(f"migrations/{migration_number}_*.sql")
        if not matching_files:
            print(f"❌ Migration file not found: migrations/{migration_number}_*.sql")
            return False
        
        # Filter out rollback files
        matching_files = [f for f in matching_files if "rollback" not in f.lower()]
        if not matching_files:
            print(f"❌ Migration file not found (only rollback found)")
            return False
            
        migration_file = matching_files[0]
        
        print(f"\n📄 Reading migration file: {migration_file}")
        with open(migration_file, "r", encoding="utf-8") as f:
            migration_sql = f.read()
        
        # Count statements (rough estimate)
        statement_count = migration_sql.count(";")
        print(f"   Statements to execute: ~{statement_count}")
        
        # Execute migration
        print(f"\n🔄 Executing migration {migration_number}...")
        with engine.begin() as conn:
            # Execute the entire migration as one transaction
            conn.execute(text(migration_sql))
        
        print(f"✓ Migration executed successfully!")
        
        # Verify migration
        print(f"\n🔍 Verifying migration...")
        with engine.connect() as conn:
            # Check tables exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"✓ Tables in database: {', '.join(tables)}")
            
            # Check row counts
            for table_name in ['users', 'repositories', 'pipeline_runs']:
                if table_name in tables:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name};"))
                    count = result.fetchone()[0]
                    print(f"  - {table_name}: {count} rows")
        
        print(f"\n✅ Migration {migration_number} completed successfully!")
        print(f"\nNext steps:")
        print(f"  1. Start backend: uvicorn app.main:app --reload")
        print(f"  2. Test API: curl http://localhost:8000/docs")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--migration", "-m", default="004", help="Migration number to run (default: 004)")
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"  Database Migration {args.migration}")
    print("=" * 60)
    print()
    
    success = run_migration(args.migration)
    sys.exit(0 if success else 1)
