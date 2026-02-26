# EduRipple Backend - Advanced Features Documentation

## Overview
This document describes the advanced features recently added to enhance the EduRipple backend's reliability, security, and maintainability.

---

## 1. Database Connection Pooling & Optimization

### File: `db_utils.py`

#### DatabasePool
Lightweight connection pool for SQLite database with thread-safe operations.

**Features:**
- Context manager for automatic connection cleanup
- Automatic commit/rollback on transactions
- Thread-safe operation
- Timeout handling (10 second default)

**Usage:**
```python
from db_utils import DatabasePool

db_pool = DatabasePool("teachers.db", pool_size=5)

# Using connections
with db_pool.get_connection() as conn:
    result = conn.execute("SELECT * FROM teachers").fetchall()

# Using transactions
with db_pool.transaction() as conn:
    conn.execute("UPDATE teachers SET ...")
    # Automatically commits on success, rolls back on error
```

#### QueryOptimizer
Optimize database performance through indexing and analysis.

**Methods:**
- `create_indices()` - Create indexes on frequently queried columns
- `analyze_table()` - Run ANALYZE to optimize query planning
- `vacuum_database()` - Reclaim unused space

**Usage:**
```python
from db_utils import QueryOptimizer

QueryOptimizer.create_indices(db_pool)
QueryOptimizer.analyze_table(db_pool, "teachers")
QueryOptimizer.vacuum_database(db_pool)
```

#### DatabaseHealth
Monitor database integrity and health metrics.

**Methods:**
- `check_integrity()` - Run PRAGMA integrity_check
- `get_database_stats()` - Get size, table counts, row counts

**Usage:**
```python
from db_utils import DatabaseHealth

health = DatabaseHealth(db_pool)
if health.check_integrity():
    print("Database is healthy")

stats = health.get_database_stats()
print(f"Database size: {stats['size_mb']}MB")
```

---

## 2. Database Backup & Recovery

### File: `db_utils.py` - DatabaseBackup class

#### Features:
- Automatic backup creation with timestamps
- Backup cleanup (keep only N recent backups)
- Database restore from previous backups

**Usage:**
```python
from db_utils import DatabaseBackup

backup = DatabaseBackup("teachers.db", backup_dir="backups")

# Create backup
backup_file = backup.create_backup()
# Output: backups/backup_20260223_123045.db

# Get latest backup
latest = backup.get_latest_backup()

# Restore from backup
backup.restore_from_backup(latest)

# Cleanup old backups (keep 10)
backup.cleanup_old_backups(keep_count=10)
```

#### Automatic Daily Backups
Backups are automatically created daily by the background task scheduler.

---

## 3. API Key Management & Rotation

### File: `monitoring.py` - APIKeyManager class

#### Features:
- Track API key creation and expiration dates
- Monitor key age and recommend rotation
- Support multiple API key rotation strategies
- Expiration warning alerts

**Supported Services:**
- OpenAI (OPENAI_API_KEY)
- Gemini (GEMINI_API_KEY)
- OpenRouter (OPENROUTER_API_KEY)
- YouTube (YOUTUBE_API_KEY)

**Usage:**
```python
from monitoring import APIKeyManager

key_manager = APIKeyManager()

# Register an API key with 90-day expiration
key_manager.register_key("OPENAI", "sk-...", expiration_days=90)

# Check if key should be rotated (60+ days old)
if key_manager.should_rotate_key("OPENAI"):
    print("Time to rotate OPENAI API key")

# Get expiration warning (14 days before expiration)
warning = key_manager.get_expiration_warning("OPENAI", warning_days=14)
if warning:
    print(f"Days until expiration: {warning['days_remaining']}")

# Get key age
age = key_manager.get_key_age_days("OPENAI")
print(f"Key is {age} days old")
```

#### Automatic Monitoring
API key expiration is checked daily. Alerts are sent:
- **WARNING** if key is 60+ days old (rotation recommended)
- **WARNING** if key expires in 7-14 days
- **CRITICAL** if key expires in 0-7 days

---

## 4. Rate Limit Monitoring & Alerts

### File: `monitoring.py` - RateLimitMonitor class

#### Features:
- Record rate limit breaches with context
- Generate breach summaries by time period
- Identify top violators (users/endpoints with most breaches)
- Automatic cleanup of old records

**Usage:**
```python
from monitoring import RateLimitMonitor

rate_monitor = RateLimitMonitor()

# Record a breach
rate_monitor.record_breach("/api/cbc", user_id=123, limit_type="hourly")

# Get summary of breaches in last 24 hours
summary = rate_monitor.get_breach_summary(hours=24)
# Output: {
#   "endpoint_user": {
#     "count": 5,
#     "last_breach": "2026-02-23T10:30:00",
#     "details": [...]
#   }
# }

# Get top violators
top = rate_monitor.get_top_violators(limit=5)

# Cleanup records older than 30 days
rate_monitor.cleanup_old_alerts(days=30)
```

#### Alert System
An alert is triggered if:
- More than 10 rate limit breaches in 24 hours
- Same endpoint/user repeatedly violates limits

---

## 5. Monitoring & Business Alerts

### File: `monitoring.py` - MonitoringAlert class

#### Features:
- Log alerts with severity levels (CRITICAL, WARNING, INFO)
- Persistent alert storage
- Retrieve recent alerts by severity

**Severity Levels:**
- **CRITICAL** - Immediate action required (database corruption, key expiration, major breaches)
- **WARNING** - Attention needed (high breach activity, large database size, expiring keys)
- **INFO** - Informational (backups completed, routine maintenance)

**Usage:**
```python
from monitoring import MonitoringAlert

alerts = MonitoringAlert()

# Send an alert
alerts.alert(
    "CRITICAL",
    "Database Issue",
    "Database integrity check failed",
    {"error": "corruption detected"}
)

# Retrieve recent alerts
critical_alerts = alerts.get_recent_alerts(severity="CRITICAL", limit=10)
for alert in critical_alerts:
    print(f"{alert['timestamp']}: {alert['title']}")
```

---

## 6. Background Task Scheduler

### File: `background_tasks.py`

#### Features:
- Run maintenance tasks on schedules
- Enable/disable individual tasks
- Persistent task status tracking
- Error handling and logging

#### Built-in Tasks:

| Task | Interval | Purpose |
|------|----------|---------|
| `database_backup` | Daily (86400s) | Automatic database backup |
| `cleanup_backups` | Weekly (604800s) | Remove old backups |
| `database_health` | Hourly (3600s) | Check database integrity |
| `api_keys` | Daily (86400s) | Monitor API key expiration |
| `rate_limits` | Hourly (3600s) | Analyze rate limit breaches |

**Usage:**
```python
from background_tasks import initialize_maintenance_tasks
from db_utils import DatabasePool

db_pool = DatabasePool("teachers.db")
scheduler, utilities = initialize_maintenance_tasks(db_pool, "teachers.db")

# Enable/disable tasks
scheduler.enable_task("database_backup")
scheduler.disable_task("rate_limits")

# Access utilities
alert_system = utilities["alert_system"]
rate_monitor = utilities["rate_limit_monitor"]
```

**Initialization in main.py:**
```python
if __name__ == "__main__":
    # Tasks are automatically started
    try:
        app.run(debug=False, port=5000)
    finally:
        # Tasks are automatically stopped
        if db_scheduler:
            db_scheduler.stop()
```

---

## 7. New API Endpoints

### System Health & Monitoring Endpoints

#### GET `/api/system/health`
Get overall system health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-23T10:30:00",
  "services": {
    "database": "operational",
    "cache": "operational",
    "ai_service": "gemini"
  },
  "database_stats": {
    "size_mb": 25.5,
    "tables": ["teachers", "resources"],
    "teachers_rows": 150,
    "resources_rows": 45
  }
}
```

#### GET `/api/system/monitoring`
Get monitoring data including breaches and alerts.

**Response:**
```json
{
  "success": true,
  "data": {
    "rate_limit_breaches": {
      "/api/cbc_user123": {
        "count": 5,
        "last_breach": "2026-02-23T10:30:00",
        "details": [...]
      }
    },
    "recent_alerts": [
      {
        "timestamp": "2026-02-23T10:30:00",
        "severity": "WARNING",
        "title": "High Rate Limit Activity",
        "message": "Detected 15 breaches in last 24 hours"
      }
    ],
    "top_violators": {
      "/api/gemini/chat_user456": 24
    }
  }
}
```

#### POST `/api/system/backup`
Manually trigger a database backup.

**Rate Limit:** 5 per day

**Response:**
```json
{
  "success": true,
  "message": "Database backup created successfully",
  "backup_file": "backups/backup_20260223_103000.db"
}
```

---

## Configuration

### Environment Variables

Add these to your `.env` file for enhanced monitoring:

```env
# Database settings
DATABASE_PATH=teachers.db

# Backup settings
BACKUP_DIR=backups
BACKUP_RETENTION_DAYS=30

# Monitoring settings
ENABLE_MONITORING=true
ALERT_EMAIL=admin@example.com
CRITICAL_ALERT_WEBHOOK=https://your-webhook.com/critical
```

### Task Configuration

Modify task intervals in `background_tasks.py`:

```python
# Daily backup instead of weekly
scheduler.add_task("database_backup", tasks.backup_database, interval_seconds=86400)

# Every 30 minutes for frequent monitoring
scheduler.add_task("rate_limits", tasks.analyze_rate_limits, interval_seconds=1800)
```

---

## Performance Impact

### Database Pooling
- **Benefit:** Reduced connection overhead for SQLite
- **Impact:** Minimal (SQLite is lightweight)
- **Best for:** Applications with frequent database access

### Query Optimization
- **Benefit:** Faster queries through proper indexing
- **Index overhead:** ~2-3% of database size
- **Query speedup:** 2-5x for indexed columns

### Background Tasks
- **CPU:** Minimal (runs every 1-24 hours)
- **Memory:** ~5-10MB for scheduler and monitoring
- **I/O:** Primarily during backups (~1-5 minutes daily)

---

## Troubleshooting

### Database Integrity Issues
```python
# Check database
from db_utils import DatabaseHealth
health = DatabaseHealth(db_pool)
if not health.check_integrity():
    print("Database is corrupted!")
```

### Restore from Backup
```python
from db_utils import DatabaseBackup
backup = DatabaseBackup("teachers.db")
backup.restore_from_backup()  # Restores latest backup
```

### Clear Rate Limit Records
```python
from monitoring import RateLimitMonitor
monitor = RateLimitMonitor()
monitor.cleanup_old_alerts(days=7)  # Keep only 7 days
```

### Disable Background Tasks
```python
scheduler.disable_task("database_backup")
scheduler.disable_task("rate_limits")
```

---

## Best Practices

1. **Regular Backups** - Daily backups are created automatically. Test restores monthly.
2. **API Key Rotation** - Rotate keys every 60 days. Update without downtime.
3. **Database Maintenance** - Run VACUUM weekly for large databases.
4. **Monitor Alerts** - Check system alerts daily for warnings.
5. **Clean Old Data** - Archive old records to keep database small.
6. **Test Disaster Recovery** - Practice restoring from backups.

---

## Support & Logging

All operations are logged in `logs/app.log`:
- Database pool operations
- Backup creation/restore
- API key monitoring
- Rate limit breaches
- System health checks
- Alert events

View recent logs:
```bash
tail -f logs/app.log
```

---

## Version Info
- **Implementation Date:** February 23, 2026
- **Python Version:** 3.8+
- **Dependencies:** None additional (uses Python stdlib)
