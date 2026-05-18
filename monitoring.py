"""
API key rotation and monitoring system for EduRipple.
Handles API key management, rotation, and monitoring for rate limit breaches.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class APIKeyStatus(Enum):
    """Status of an API key."""
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APIKeyManager:
    """Manage API keys with rotation and expiration tracking."""
    
    def __init__(self, key_file="api_keys.json"):
        """Initialize API key manager."""
        self.key_file = key_file
        self.keys = self._load_keys()
    
    def _load_keys(self):
        """Load API keys from file."""
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load API keys: {str(e)}")
                return {}
        return {}
    
    def _save_keys(self):
        """Save API keys to file."""
        try:
            with open(self.key_file, 'w') as f:
                json.dump(self.keys, f, indent=2)
            logger.info("API keys saved")
        except Exception as e:
            logger.error(f"Failed to save API keys: {str(e)}")
    
    def register_key(self, service, key, expiration_days=90):
        """Register an API key with expiration."""
        expiration_date = (datetime.utcnow() + timedelta(days=expiration_days)).isoformat()
        
        if service not in self.keys:
            self.keys[service] = {}
        
        self.keys[service][key[:10] + "..."] = {
            "status": APIKeyStatus.ACTIVE.value,
            "created": datetime.utcnow().isoformat(),
            "expiration": expiration_date,
            "rotations": 0,
            "last_rotated": None
        }
        self._save_keys()
        logger.info(f"API key registered for {service}")
    
    def is_key_expired(self, service, key):
        """Check if an API key is expired."""
        if service not in os.environ:
            return False
        
        current_key = os.environ.get(service + "_API_KEY")
        if current_key != key:
            # Key has been rotated
            return False
        
        try:
            expiration = datetime.fromisoformat(
                self.keys.get(service, {}).get(key[:10] + "...", {}).get("expiration")
            )
            return datetime.utcnow() > expiration
        except:
            return False
    
    def get_key_age_days(self, service):
        """Get the age of the current API key in days."""
        if service not in self.keys:
            return None
        
        keys_info = list(self.keys[service].values())
        if not keys_info:
            return None
        
        active_keys = [k for k in keys_info if k.get("status") == APIKeyStatus.ACTIVE.value]
        if not active_keys:
            return None
        
        created = datetime.fromisoformat(active_keys[0]["created"])
        age = (datetime.utcnow() - created).days
        return age
    
    def should_rotate_key(self, service, rotation_age_days=60):
        """Check if a key should be rotated based on age."""
        age = self.get_key_age_days(service)
        return age is not None and age >= rotation_age_days
    
    def get_expiration_warning(self, service, warning_days=14):
        """Check if key is expiring soon."""
        if service not in self.keys:
            return None
        
        keys_info = list(self.keys[service].values())
        active_keys = [k for k in keys_info if k.get("status") == APIKeyStatus.ACTIVE.value]
        
        if not active_keys:
            return None
        
        expiration = datetime.fromisoformat(active_keys[0]["expiration"])
        days_until_expiration = (expiration - datetime.utcnow()).days
        
        if 0 <= days_until_expiration <= warning_days:
            return {
                "service": service,
                "days_remaining": days_until_expiration,
                "expiration_date": expiration.isoformat()
            }
        
        return None


class RateLimitMonitor:
    """Monitor rate limit breaches and alerts."""
    
    def __init__(self, alert_file="rate_limit_alerts.json"):
        """Initialize rate limit monitor."""
        self.alert_file = alert_file
        self.alerts = self._load_alerts()
    
    def _load_alerts(self):
        """Load alerts from file."""
        if os.path.exists(self.alert_file):
            try:
                with open(self.alert_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load alerts: {str(e)}")
                return {}
        return {}
    
    def _save_alerts(self):
        """Save alerts to file."""
        try:
            with open(self.alert_file, 'w') as f:
                json.dump(self.alerts, f, indent=2, default=str)
            logger.info("Rate limit alerts saved")
        except Exception as e:
            logger.error(f"Failed to save alerts: {str(e)}")
    
    def record_breach(self, endpoint, user_id, limit_type="hourly"):
        """Record a rate limit breach."""
        key = f"{endpoint}_{user_id}"
        
        if key not in self.alerts:
            self.alerts[key] = []
        
        breach = {
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": endpoint,
            "user_id": user_id,
            "limit_type": limit_type
        }
        
        self.alerts[key].append(breach)
        self._save_alerts()
        
        logger.warning(f"Rate limit breach recorded: {endpoint} by user {user_id}")
    
    def get_breach_summary(self, hours=24):
        """Get summary of recent rate limit breaches."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        summary = {}
        
        for key, breaches in self.alerts.items():
            recent = [
                b for b in breaches
                if datetime.fromisoformat(b["timestamp"]) > cutoff_time
            ]
            if recent:
                summary[key] = {
                    "count": len(recent),
                    "last_breach": recent[-1]["timestamp"],
                    "details": recent[-3:]  # Last 3 breaches
                }
        
        logger.info(f"Rate limit breach summary: {summary}")
        return summary
    
    def get_top_violators(self, limit=10):
        """Get users/endpoints with most breaches."""
        violation_counts = {}
        
        for key, breaches in self.alerts.items():
            violation_counts[key] = len(breaches)
        
        top_violators = sorted(
            violation_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return {k: v for k, v in top_violators}
    
    def cleanup_old_alerts(self, days=30):
        """Remove old alert records."""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        cleaned = 0
        
        for key in self.alerts:
            self.alerts[key] = [
                b for b in self.alerts[key]
                if datetime.fromisoformat(b["timestamp"]) > cutoff_time
            ]
            if not self.alerts[key]:
                del self.alerts[key]
                cleaned += 1
        
        if cleaned > 0:
            self._save_alerts()
            logger.info(f"Cleaned up {cleaned} old alert records")


class MonitoringAlert:
    """Send alerts for critical events."""
    
    def __init__(self, log_file="monitoring_alerts.log"):
        """Initialize alert system."""
        self.log_file = log_file
    
    def alert(self, severity, title, message, details=None):
        """Log an alert."""
        alert_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,  # CRITICAL, WARNING, INFO
            "title": title,
            "message": message,
            "details": details or {}
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(alert_record) + "\n")
        except Exception as e:
            logger.error(f"Failed to record alert: {str(e)}")
        
        if severity == "CRITICAL":
            logger.critical(f"[ALERT] {title}: {message}")
        elif severity == "WARNING":
            logger.warning(f"[ALERT] {title}: {message}")
        else:
            logger.info(f"[ALERT] {title}: {message}")
    
    def get_recent_alerts(self, severity=None, limit=20):
        """Get recent alerts."""
        if not os.path.exists(self.log_file):
            return []
        
        alerts = []
        try:
            with open(self.log_file, 'r') as f:
                for line in reversed(list(f)):
                    alert = json.loads(line)
                    if severity is None or alert["severity"] == severity:
                        alerts.append(alert)
                    if len(alerts) >= limit:
                        break
        except Exception as e:
            logger.error(f"Failed to read alerts: {str(e)}")
        
        return list(reversed(alerts))
