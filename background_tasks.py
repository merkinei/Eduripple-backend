"""
Background tasks and scheduling for EduRipple.
Handles database backups, API key monitoring, and health checks.
"""

import logging
import threading
from datetime import datetime, timedelta
from db_utils import DatabaseBackup, DatabaseHealth
from monitoring import APIKeyManager, RateLimitMonitor, MonitoringAlert

logger = logging.getLogger(__name__)


class BackgroundTaskScheduler:
    """Schedule and run background maintenance tasks."""
    
    def __init__(self):
        """Initialize task scheduler."""
        self.tasks = {}
        self.running = False
        self.monitor_thread = None
    
    def add_task(self, task_name, task_func, interval_seconds=3600):
        """Register a background task."""
        self.tasks[task_name] = {
            "func": task_func,
            "interval": interval_seconds,
            "last_run": None,
            "enabled": True
        }
        logger.info(f"Task registered: {task_name} (runs every {interval_seconds}s)")
    
    def enable_task(self, task_name):
        """Enable a task."""
        if task_name in self.tasks:
            self.tasks[task_name]["enabled"] = True
            logger.info(f"Task enabled: {task_name}")
    
    def disable_task(self, task_name):
        """Disable a task."""
        if task_name in self.tasks:
            self.tasks[task_name]["enabled"] = False
            logger.info(f"Task disabled: {task_name}")
    
    def start(self):
        """Start the task scheduler."""
        if self.running:
            logger.warning("Task scheduler already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Task scheduler started")
    
    def stop(self):
        """Stop the task scheduler."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Task scheduler stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                for task_name, task_info in self.tasks.items():
                    if not task_info["enabled"]:
                        continue
                    
                    last_run = task_info["last_run"]
                    if last_run is None or \
                       (datetime.utcnow() - last_run).total_seconds() >= task_info["interval"]:
                        try:
                            logger.info(f"Running task: {task_name}")
                            task_info["func"]()
                            task_info["last_run"] = datetime.utcnow()
                            logger.info(f"Task completed: {task_name}")
                        except Exception as e:
                            logger.error(f"Task failed: {task_name}: {str(e)}")
                
                # Check every minute
                import time
                time.sleep(60)
            except Exception as e:
                logger.error(f"Monitor loop error: {str(e)}")


class MaintenanceTasks:
    """Collection of maintenance tasks."""
    
    def __init__(self, db_backup, db_health, api_key_manager, rate_limit_monitor, alert_system):
        """Initialize maintenance tasks."""
        self.db_backup = db_backup
        self.db_health = db_health
        self.api_key_manager = api_key_manager
        self.rate_limit_monitor = rate_limit_monitor
        self.alert_system = alert_system
    
    def backup_database(self):
        """Create database backup."""
        try:
            backup_file = self.db_backup.create_backup()
            self.alert_system.alert(
                "INFO",
                "Database Backup",
                f"Database backup created successfully: {backup_file}"
            )
        except Exception as e:
            self.alert_system.alert(
                "CRITICAL",
                "Database Backup Failed",
                f"Failed to backup database: {str(e)}",
                {"error": str(e)}
            )
    
    def cleanup_old_backups(self):
        """Remove old backup files."""
        try:
            self.db_backup.cleanup_old_backups(keep_count=10)
        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")
    
    def check_database_health(self):
        """Check database integrity and health."""
        try:
            # Check integrity
            if not self.db_health.check_integrity():
                self.alert_system.alert(
                    "CRITICAL",
                    "Database Integrity Check Failed",
                    "Database integrity check did not pass. Manual intervention may be required."
                )
            
            # Get stats
            stats = self.db_health.get_database_stats()
            
            # Alert if database is too large
            if stats.get("size_mb", 0) > 1000:  # >1GB
                self.alert_system.alert(
                    "WARNING",
                    "Large Database",
                    f"Database size is {stats['size_mb']:.2f}MB. Consider archiving old data.",
                    {"size_mb": stats["size_mb"]}
                )
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
    
    def check_api_keys(self):
        """Check API key expiration and rotation needs."""
        services = ["OPENAI", "GEMINI", "OPENROUTER", "YOUTUBE"]
        
        for service in services:
            # Check if key should be rotated
            if self.api_key_manager.should_rotate_key(service):
                self.alert_system.alert(
                    "WARNING",
                    f"{service} API Key Rotation Recommended",
                    f"The {service} API key is {self.api_key_manager.get_key_age_days(service)} days old. Consider rotating it."
                )
            
            # Check expiration
            expiration_warning = self.api_key_manager.get_expiration_warning(service)
            if expiration_warning:
                self.alert_system.alert(
                    "WARNING" if expiration_warning["days_remaining"] > 7 else "CRITICAL",
                    f"{service} API Key Expiring Soon",
                    f"The {service} API key expires in {expiration_warning['days_remaining']} days",
                    {"expiration_date": expiration_warning["expiration_date"]}
                )
    
    def analyze_rate_limits(self):
        """Analyze rate limit breaches."""
        try:
            summary = self.rate_limit_monitor.get_breach_summary(hours=24)
            if summary:
                # Alert if there are multiple breaches
                total_breaches = sum(s["count"] for s in summary.values())
                if total_breaches > 10:
                    self.alert_system.alert(
                        "WARNING",
                        "High Rate Limit Breach Activity",
                        f"Detected {total_breaches} rate limit breaches in the last 24 hours",
                        {"summary": summary}
                    )
                
                # Get top violators
                top_violators = self.rate_limit_monitor.get_top_violators(limit=5)
                if top_violators:
                    logger.info(f"Top rate limit violators: {top_violators}")
            
            # Cleanup old alerts
            self.rate_limit_monitor.cleanup_old_alerts(days=30)
        except Exception as e:
            logger.error(f"Rate limit analysis failed: {str(e)}")
    
    def vacuum_database(self):
        """Optimize database by removing unused space."""
        try:
            from db_utils import QueryOptimizer
            # This would need db_pool passed, keeping it simple for now
            logger.info("Database optimization scheduled")
        except Exception as e:
            logger.error(f"Database optimization failed: {str(e)}")


def initialize_maintenance_tasks(db_pool, db_path="teachers.db"):
    """Initialize and start all maintenance tasks."""
    
    # Initialize utilities
    db_backup = DatabaseBackup(db_path)
    db_health = DatabaseHealth(db_pool)
    api_key_manager = APIKeyManager()
    rate_limit_monitor = RateLimitMonitor()
    alert_system = MonitoringAlert()
    
    # Create maintenance tasks
    tasks = MaintenanceTasks(
        db_backup,
        db_health,
        api_key_manager,
        rate_limit_monitor,
        alert_system
    )
    
    # Create scheduler
    scheduler = BackgroundTaskScheduler()
    
    # Register tasks
    scheduler.add_task("database_backup", tasks.backup_database, interval_seconds=86400)  # Daily
    scheduler.add_task("cleanup_backups", tasks.cleanup_old_backups, interval_seconds=604800)  # Weekly
    scheduler.add_task("database_health", tasks.check_database_health, interval_seconds=3600)  # Hourly
    scheduler.add_task("api_keys", tasks.check_api_keys, interval_seconds=86400)  # Daily
    scheduler.add_task("rate_limits", tasks.analyze_rate_limits, interval_seconds=3600)  # Hourly
    
    # Start scheduler
    scheduler.start()
    
    logger.info("Maintenance tasks initialized")
    
    return scheduler, {
        "api_key_manager": api_key_manager,
        "rate_limit_monitor": rate_limit_monitor,
        "alert_system": alert_system,
        "db_backup": db_backup,
        "db_health": db_health
    }
