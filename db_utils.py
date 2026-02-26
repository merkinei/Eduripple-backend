"""
Database utilities for EduRipple with connection pooling and optimization.
Provides efficient database access patterns and connection management.
"""

import sqlite3
import threading
import logging
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabasePool:
    """Lightweight connection pool for SQLite database."""
    
    def __init__(self, db_path, pool_size=5):
        """Initialize database pool."""
        self.db_path = db_path
        self.pool_size = pool_size
        self.conn_local = threading.local()
        self.lock = threading.Lock()
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except sqlite3.OperationalError as e:
            logger.error(f"Database connection error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected database error: {str(e)}")
            raise
        finally:
            try:
                conn.close()
            except:
                pass
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction failed, rolled back: {str(e)}")
                raise


class DatabaseBackup:
    """Handle database backup and recovery operations."""
    
    def __init__(self, db_path, backup_dir="backups"):
        """Initialize backup manager."""
        self.db_path = db_path
        self.backup_dir = backup_dir
        import os
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(self):
        """Create a backup of the database."""
        import os
        import shutil
        from datetime import datetime
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self.backup_dir, f"backup_{timestamp}.db")
            shutil.copy2(self.db_path, backup_file)
            logger.info(f"Database backup created: {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"Backup creation failed: {str(e)}")
            raise
    
    def get_latest_backup(self):
        """Get the path to the latest backup file."""
        import os
        import glob
        
        backups = glob.glob(os.path.join(self.backup_dir, "backup_*.db"))
        if not backups:
            return None
        return max(backups, key=os.path.getctime)
    
    def restore_from_backup(self, backup_file=None):
        """Restore database from backup."""
        import shutil
        import os
        
        if backup_file is None:
            backup_file = self.get_latest_backup()
        
        if not backup_file:
            logger.error("No backup file found")
            return False
        
        try:
            shutil.copy2(backup_file, self.db_path)
            logger.info(f"Database restored from: {backup_file}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {str(e)}")
            raise
    
    def cleanup_old_backups(self, keep_count=10):
        """Remove old backups, keeping only the most recent ones."""
        import os
        import glob
        
        backups = sorted(
            glob.glob(os.path.join(self.backup_dir, "backup_*.db")),
            key=os.path.getctime,
            reverse=True
        )
        
        if len(backups) > keep_count:
            for backup in backups[keep_count:]:
                try:
                    os.remove(backup)
                    logger.info(f"Removed old backup: {backup}")
                except Exception as e:
                    logger.warning(f"Failed to remove backup {backup}: {str(e)}")


class QueryOptimizer:
    """Optimizer for common database queries."""
    
    @staticmethod
    def create_indices(db_pool):
        """Create indices for frequently queried columns."""
        create_index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_teachers_email ON teachers(email)",
            "CREATE INDEX IF NOT EXISTS idx_teachers_school ON teachers(school)",
            "CREATE INDEX IF NOT EXISTS idx_teachers_subject ON teachers(subject_area)",
        ]
        
        try:
            with db_pool.get_connection() as conn:
                for query in create_index_queries:
                    conn.execute(query)
                logger.info("Database indices created successfully")
        except Exception as e:
            logger.error(f"Failed to create indices: {str(e)}")
    
    @staticmethod
    def analyze_table(db_pool, table_name):
        """Run ANALYZE on a table to optimize query planning."""
        try:
            with db_pool.get_connection() as conn:
                conn.execute(f"ANALYZE {table_name}")
                logger.info(f"Table {table_name} analyzed")
        except Exception as e:
            logger.error(f"Failed to analyze table: {str(e)}")
    
    @staticmethod
    def vacuum_database(db_pool):
        """Reclaim unused space in the database."""
        try:
            with db_pool.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuumed successfully")
        except Exception as e:
            logger.error(f"Failed to vacuum database: {str(e)}")


class DatabaseHealth:
    """Monitor database health and integrity."""
    
    def __init__(self, db_pool):
        """Initialize health monitor."""
        self.db_pool = db_pool
    
    def check_integrity(self):
        """Check database integrity."""
        try:
            with self.db_pool.get_connection() as conn:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result[0] == "ok":
                    logger.info("Database integrity check passed")
                    return True
                else:
                    logger.error(f"Database integrity check failed: {result[0]}")
                    return False
        except Exception as e:
            logger.error(f"Integrity check error: {str(e)}")
            return False
    
    def get_database_stats(self):
        """Get database statistics."""
        stats = {}
        try:
            with self.db_pool.get_connection() as conn:
                # Get database size
                page_count = conn.execute("PRAGMA page_count").fetchone()[0]
                page_size = conn.execute("PRAGMA page_size").fetchone()[0]
                stats["size_mb"] = (page_count * page_size) / (1024 * 1024)
                
                # Get table counts
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                stats["tables"] = [t[0] for t in tables]
                
                # Get row counts
                for table in stats["tables"]:
                    try:
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        stats[f"{table}_rows"] = count
                    except:
                        pass
                
                logger.info(f"Database stats: {stats}")
                return stats
        except Exception as e:
            logger.error(f"Stats collection error: {str(e)}")
            return {}
