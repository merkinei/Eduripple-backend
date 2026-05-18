"""
Visitor tracking and analytics system for EduRipple.
Logs all page visits to database and provides analytics endpoints.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
import os
from flask import request, g

logger = logging.getLogger(__name__)

# Data directory (same as app)
DATA_DIR = os.getenv("DATA_DIR", ".")
VISITORS_DB = os.path.join(DATA_DIR, "visitors.db")


def init_visitors_db():
    """Initialize visitors database with tracking tables."""
    conn = sqlite3.connect(VISITORS_DB)
    try:
        # Table for page visits
        conn.execute("""
            CREATE TABLE IF NOT EXISTS page_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                path TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                status_code INTEGER,
                referrer TEXT,
                country TEXT,
                city TEXT,
                user_id TEXT,
                session_id TEXT
            )
        """)
        
        # Table for aggregated daily stats
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                total_visits INTEGER DEFAULT 0,
                unique_visitors INTEGER DEFAULT 0,
                unique_ips INTEGER DEFAULT 0,
                top_pages TEXT,
                top_referrers TEXT
            )
        """)
        
        # Create index for faster queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON page_visits(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON page_visits(path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip ON page_visits(ip_address)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_stats(date)")
        
        conn.commit()
        logger.info("✅ Visitors database initialized")
    except Exception as e:
        logger.error(f"❌ Error initializing visitors database: {str(e)}")
    finally:
        conn.close()


def get_client_ip():
    """Get client IP address, accounting for proxies."""
    # Check for IP from shared internet (X-Forwarded-For)
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr or "unknown"
    return ip


def log_visit(path, method="GET", status_code=200, user_id=None, session_id=None):
    """Log a visitor to the database."""
    try:
        conn = sqlite3.connect(VISITORS_DB)
        cursor = conn.cursor()
        
        ip_address = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')[:500]  # Limit length
        referrer = request.headers.get('Referer', '')[:500]
        
        cursor.execute("""
            INSERT INTO page_visits 
            (timestamp, ip_address, user_agent, path, method, status_code, referrer, user_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            ip_address,
            user_agent,
            path,
            method,
            status_code,
            referrer,
            user_id,
            session_id
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Error logging visit: {str(e)}")


def get_visitor_stats(days=30):
    """Get visitor statistics for the last N days."""
    try:
        conn = sqlite3.connect(VISITORS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Total visits
        cursor.execute("""
            SELECT COUNT(*) as total_visits FROM page_visits WHERE timestamp > ?
        """, (cutoff_date,))
        total_visits = dict(cursor.fetchone())['total_visits']
        
        # Unique visitors (by IP)
        cursor.execute("""
            SELECT COUNT(DISTINCT ip_address) as unique_visitors FROM page_visits WHERE timestamp > ?
        """, (cutoff_date,))
        unique_visitors = dict(cursor.fetchone())['unique_visitors']
        
        # Top pages
        cursor.execute("""
            SELECT path, COUNT(*) as count FROM page_visits 
            WHERE timestamp > ? 
            GROUP BY path 
            ORDER BY count DESC 
            LIMIT 10
        """, (cutoff_date,))
        top_pages = [dict(row) for row in cursor.fetchall()]
        
        # Top referrers
        cursor.execute("""
            SELECT referrer, COUNT(*) as count FROM page_visits 
            WHERE timestamp > ? AND referrer != ''
            GROUP BY referrer 
            ORDER BY count DESC 
            LIMIT 10
        """, (cutoff_date,))
        top_referrers = [dict(row) for row in cursor.fetchall()]
        
        # Visits by hour (today)
        cursor.execute("""
            SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, COUNT(*) as count
            FROM page_visits 
            WHERE timestamp > datetime(?, '-' || ? || ' days')
            GROUP BY hour
            ORDER BY hour DESC
        """, (datetime.utcnow().isoformat(), days))
        hourly_data = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "top_pages": top_pages,
            "top_referrers": top_referrers,
            "hourly_data": hourly_data,
            "period_days": days
        }
    except Exception as e:
        logger.error(f"❌ Error getting visitor stats: {str(e)}")
        return {
            "error": str(e),
            "total_visits": 0,
            "unique_visitors": 0,
            "top_pages": [],
            "top_referrers": [],
            "hourly_data": []
        }


def get_daily_stats(date_str=None):
    """Get stats for a specific day."""
    try:
        conn = sqlite3.connect(VISITORS_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if date_str is None:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Visits for the day
        cursor.execute("""
            SELECT COUNT(*) as total FROM page_visits 
            WHERE strftime('%Y-%m-%d', timestamp) = ?
        """, (date_str,))
        total_visits = dict(cursor.fetchone())['total']
        
        # Unique IPs for the day
        cursor.execute("""
            SELECT COUNT(DISTINCT ip_address) as unique_ips FROM page_visits 
            WHERE strftime('%Y-%m-%d', timestamp) = ?
        """, (date_str,))
        unique_ips = dict(cursor.fetchone())['unique_ips']
        
        # Top pages for the day
        cursor.execute("""
            SELECT path, COUNT(*) as count FROM page_visits 
            WHERE strftime('%Y-%m-%d', timestamp) = ?
            GROUP BY path 
            ORDER BY count DESC 
            LIMIT 5
        """, (date_str,))
        top_pages = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "date": date_str,
            "total_visits": total_visits,
            "unique_ips": unique_ips,
            "top_pages": top_pages
        }
    except Exception as e:
        logger.error(f"❌ Error getting daily stats: {str(e)}")
        return {"error": str(e)}


def cleanup_old_visits(days=90):
    """Delete visitor records older than N days (for privacy/storage)."""
    try:
        conn = sqlite3.connect(VISITORS_DB)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cursor.execute("DELETE FROM page_visits WHERE timestamp < ?", (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Cleaned up {deleted_count} visitor records older than {days} days")
        return deleted_count
    except Exception as e:
        logger.error(f"❌ Error cleaning up old visits: {str(e)}")
        return 0
