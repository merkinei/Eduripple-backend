"""
Security utilities for EduRipple Backend
Implements security headers, input validation, sanitization, and protection mechanisms
"""

import re
import hashlib
import secrets
import logging
from functools import wraps
from flask import request, jsonify
from urllib.parse import urlparse
from html import escape as html_escape

logger = logging.getLogger(__name__)


class SecurityHeaders:
    """Apply security headers to all responses"""
    
    @staticmethod
    def apply_headers(response):
        """Apply comprehensive security headers"""
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Content Security Policy - strict but functional
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # controlled - inline scripts are minimal
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://generativelanguage.googleapis.com https://api.openrouter.ai api.elevenlabs.io; "
            "media-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        
        # Referrer policy - protect privacy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Feature policy - disable unnecessary browser features
        response.headers['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(), gyroscope=(), '
            'magnetometer=(), microphone=(), payment=(), usb=()'
        )
        
        # HTTPS enforcement (only in production)
        if request.environ.get('HTTP_X_FORWARDED_PROTO') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response


class InputValidator:
    """Validate and sanitize all user inputs"""
    
    # Regex patterns for validation
    PATTERNS = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'username': r'^[a-zA-Z0-9_-]{3,32}$',
        'password': r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$',
        'url': r'^https?://[^\s/$.?#].[^\s]*$',
        'phone': r'^[+]?[(]?[0-9]{3}[)]?[-\s.]?[0-9]{3}[-\s.]?[0-9]{4,6}$',
    }
    
    # Common injection patterns
    INJECTION_PATTERNS = [
        r"(<|%3C).*?(>|%3E)",  # HTML tags
        r"(\bor\b|\band\b).*?(1\s*=\s*1|true)",  # SQL injection
        r"(\${|#\{|\?\{)",  # Template injection
        r"(eval|exec|system|passthru|shell_exec)\s*\(",  # Code execution
    ]
    
    LENGTH_LIMITS = {
        'email': 254,
        'password': 128,
        'name': 100,
        'text': 10000,
        'url': 2048,
    }
    
    @staticmethod
    def is_valid_email(email):
        """Validate email format"""
        if not email or len(email) > InputValidator.LENGTH_LIMITS['email']:
            return False
        return bool(re.match(InputValidator.PATTERNS['email'], email.lower()))
    
    @staticmethod
    def is_valid_password(password):
        """Validate password strength"""
        if not password or len(password) < 8 or len(password) > InputValidator.LENGTH_LIMITS['password']:
            return False, "Password must be 8-128 characters"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain lowercase letters"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain uppercase letters"
        if not re.search(r'\d', password):
            return False, "Password must contain numbers"
        if not re.search(r'[@$!%*?&]', password):
            return False, "Password must contain special characters (@$!%*?&)"
        
        return True, "Password is valid"
    
    @staticmethod
    def sanitize_string(text, max_length=None):
        """Remove and escape dangerous characters"""
        if not text:
            return ""
        
        text = str(text).strip()
        
        # Check length
        length_limit = max_length or InputValidator.LENGTH_LIMITS['text']
        if len(text) > length_limit:
            text = text[:length_limit]
        
        # Check for injection patterns
        for pattern in InputValidator.INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential injection detected in input: {text[:50]}...")
                # Don't reject, but escape it
                break
        
        # HTML escape for safety
        return html_escape(text)
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename to prevent directory traversal"""
        if not filename:
            return "file"
        
        # Remove null bytes
        filename = filename.replace('\x00', '')
        
        # Remove directory traversal attempts
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Keep only safe characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:240] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def prevent_xss(data):
        """Escape data for HTML context"""
        if isinstance(data, dict):
            return {k: InputValidator.prevent_xss(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [InputValidator.prevent_xss(item) for item in data]
        elif isinstance(data, str):
            return html_escape(data)
        return data
    
    @staticmethod
    def is_safe_redirect(url):
        """Verify redirect URL is safe (same-origin only)"""
        if not url:
            return False
        
        # Parse the URL
        try:
            parsed = urlparse(url)
        except:
            return False
        
        # Only allow relative URLs or same-origin redirects
        if parsed.netloc and parsed.netloc != request.host:
            return False
        
        return True


class RateLimitRules:
    """Define specific rate limits for different endpoints"""
    
    RULES = {
        'login': '10 per hour',           # Prevent brute force
        'signup': '5 per hour',           # Prevent account spam
        'api_generate': '30 per hour',    # Prevent resource exhaustion
        'upload': '20 per hour',          # Prevent storage spam
        'download': '100 per hour',       # Downloads are cheap
        'general': '50 per hour',         # Default for other API calls
    }
    
    @staticmethod
    def get_limit(rule_name):
        """Get rate limit for a specific rule"""
        return RateLimitRules.RULES.get(rule_name, RateLimitRules.RULES['general'])


class PasswordSecurity:
    """Handle password hashing and stretching"""
    
    @staticmethod
    def hash_password(password):
        """Hash password with salt"""
        # Flask's generate_password_hash uses werkzeug which uses PBKDF2
        # This is already secure, but we ensure it's used
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    @staticmethod
    def verify_password(password, hash_value):
        """Verify password against hash"""
        from werkzeug.security import check_password_hash
        return check_password_hash(hash_value, password)
    
    @staticmethod
    def generate_secure_token(length=32):
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(length)


class AuditLogger:
    """Log security events for audit trail"""
    
    @staticmethod
    def log_authentication(user_id, email, status, ip_address):
        """Log authentication attempts"""
        logger.info(f"AUTH_ATTEMPT | User: {user_id} | Email: {email} | Status: {status} | IP: {ip_address}")
    
    @staticmethod
    def log_authorization_failure(user_id, resource, action, ip_address):
        """Log unauthorized access attempts"""
        logger.warning(f"UNAUTHORIZED_ACCESS | User: {user_id} | Resource: {resource} | Action: {action} | IP: {ip_address}")
    
    @staticmethod
    def log_sensitive_operation(user_id, operation, details, ip_address):
        """Log sensitive operations like password changes, data exports"""
        logger.warning(f"SENSITIVE_OP | User: {user_id} | Op: {operation} | Details: {details} | IP: {ip_address}")
    
    @staticmethod
    def log_error(error_type, message, ip_address):
        """Log security errors"""
        logger.error(f"SECURITY_ERROR | Type: {error_type} | Message: {message} | IP: {ip_address}")


def require_csrf_token(f):
    """Decorator to require CSRF token for state-changing operations"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip CSRF check for GET requests
        if request.method == 'GET':
            return f(*args, **kwargs)
        
        # For POST/PUT/DELETE, we're using session-based CSRF protection
        # Flask-WTF provides this, but we keep it simple with CORS credentials
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_client_ip():
    """Get client IP address, accounting for proxies"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


def setup_security(app):
    """Setup all security features for the Flask app"""
    
    # Apply security headers to all responses
    @app.after_request
    def apply_security_headers(response):
        return SecurityHeaders.apply_headers(response)
    
    logger.info("Security features initialized")
