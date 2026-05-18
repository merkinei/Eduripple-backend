import sqlite3
import os

DATA_DIR = "."
VISITORS_DB = os.path.join(DATA_DIR, "visitors.db")

conn = sqlite3.connect(VISITORS_DB)

# Create page_visits table
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

# Create daily_stats table
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

# Create indexes
conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON page_visits(timestamp)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON page_visits(path)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_ip ON page_visits(ip_address)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_stats(date)")

conn.commit()
print("✅ Visitors database initialized")
conn.close()
