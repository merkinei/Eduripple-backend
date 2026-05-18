"""
Database Setup and Initialization Script
Run this during deployment to initialize databases
Usage: python setup_db.py [--migrate-from-sqlite]
"""
import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from curriculum_db import init_curriculum_db
    # main.py.py has an unusual filename; use importlib to import it
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "main_app",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py.py")
    )
    _main_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_main_module)
    app = _main_module.app
    init_teachers_db = _main_module.init_teachers_db
    IMPORTS_AVAILABLE = True
except (ImportError, Exception) as e:
    logger.warning(f"Imports unavailable: {e}")
    IMPORTS_AVAILABLE = False


def init_databases():
    """Initialize application databases"""
    logger.info("Starting database initialization...")
    
    try:
        # Initialize teachers database
        logger.info("Initializing teachers database...")
        init_teachers_db()
        logger.info("✓ Teachers database initialized")
        
        # Initialize curriculum database
        logger.info("Initializing curriculum database...")
        if IMPORTS_AVAILABLE:
            init_curriculum_db()
            logger.info("✓ Curriculum database initialized")
        else:
            logger.warning("Curriculum initialization skipped (imports unavailable)")
        
        logger.info("✓ All databases initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}", exc_info=True)
        return False


def migrate_sqlite_to_postgresql():
    """
    Migrate data from SQLite to PostgreSQL
    Note: This is a template. Customize based on your database schema
    """
    logger.info("Starting SQLite to PostgreSQL migration...")
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        logger.error("psycopg2-binary not installed. Install with: pip install psycopg2-binary")
        return False
    
    try:
        # Source: SQLite databases
        sqlite_teachers_db = "teachers.db"
        
        # Destination: PostgreSQL connection string from env
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
        
        # Parse PostgreSQL connection string
        # Expected format: postgresql://user:password@host:port/dbname
        from urllib.parse import urlparse
        parsed_url = urlparse(db_url)
        
        pg_config = {
            'host': parsed_url.hostname,
            'port': parsed_url.port or 5432,
            'user': parsed_url.username,
            'password': parsed_url.password,
            'database': parsed_url.path.lstrip('/'),
        }
        
        # Connect to PostgreSQL
        pg_conn = psycopg2.connect(**pg_config)
        pg_cursor = pg_conn.cursor()
        
        logger.info(f"Connected to PostgreSQL at {pg_config['host']}")
        
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(sqlite_teachers_db)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        logger.info(f"Connected to SQLite at {sqlite_teachers_db}")
        
        # Migrate teachers table
        logger.info("Migrating teachers data...")
        sqlite_cursor.execute("SELECT * FROM teachers")
        teachers = sqlite_cursor.fetchall()
        
        for teacher in teachers:
            # Create INSERT statement
            columns = ', '.join([col[0] for col in sqlite_cursor.description])
            placeholders = ', '.join(['%s'] * len(teacher))
            
            insert_query = f"""
                INSERT INTO teachers ({columns})
                VALUES ({placeholders})
                ON CONFLICT (email) DO NOTHING
            """
            
            try:
                pg_cursor.execute(insert_query, teacher)
            except Exception as e:
                logger.warning(f"Failed to insert teacher {teacher['email']}: {e}")
        
        pg_conn.commit()
        logger.info(f"✓ Migrated {len(teachers)} teachers")
        
        # Close connections
        sqlite_cursor.close()
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()
        
        logger.info("✓ Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}", exc_info=True)
        return False


def backup_sqlite_databases():
    """Create backup of SQLite databases before migration"""
    logger.info("Creating backups of SQLite databases...")
    
    try:
        backup_dir = Path("backups") / f"pre_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        for db_file in ["teachers.db", "curriculum.db"]:
            if Path(db_file).exists():
                import shutil
                shutil.copy2(db_file, backup_dir / db_file)
                logger.info(f"✓ Backed up {db_file}")
        
        logger.info(f"✓ Backups created in {backup_dir}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Backup failed: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Initialize EduRipple databases")
    parser.add_argument("--migrate-from-sqlite", action="store_true",
                       help="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--backup", action="store_true",
                       help="Create backup of SQLite databases before migration")
    
    args = parser.parse_args()
    
    # Initialize databases
    if not init_databases():
        sys.exit(1)
    
    # Optionally migrate from SQLite
    if args.migrate_from_sqlite:
        if args.backup or True:  # Always backup before migration
            if not backup_sqlite_databases():
                logger.warning("Backup failed but continuing with migration...")
        
        if not migrate_sqlite_to_postgresql():
            sys.exit(1)
    
    logger.info("✓ Database setup completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
