# EduRipple Security Hardening Guide

## Overview

This document outlines all security improvements implemented in the EduRipple backend and best practices for maintaining a secure platform.

---

## 1. Authentication Security

### Password Requirements
All passwords now require:
- **Minimum 8 characters**
- **Uppercase letters** (A-Z)
- **Lowercase letters** (a-z)
- **Numbers** (0-9)
- **Special characters** (@$!%*?&)

**Example:** `SecurePass123!`

### Session Management
- Sessions persist for **7 days** (`PERMANENT_SESSION_LIFETIME`)
- Cookies are **HTTP-only** (`SESSION_COOKIE_HTTPONLY = True`) - prevents JavaScript access
- **SameSite=Lax** policy prevents CSRF attacks while allowing normal cross-site navigation
- Sessions survive proxy/load balancer transitions via `X-Forwarded-Proto` headers

### Rate Limiting on Auth Routes
```
- Sign Up: 5 attempts per hour (prevents account spam)
- Sign In: 10 attempts per hour (prevents brute force)
```

If rate limited, users see HTTP 429 (Too Many Requests) response.

### Password Hashing
- Uses **PBKDF2 with SHA-256** via Werkzeug
- 16-byte cryptographic salt per password
- Resistant to rainbow table attacks

---

## 2. API Endpoint Protection

### Rate Limiting
All resource-intensive endpoints are rate-limited to prevent abuse:

| Endpoint | Limit | Purpose |
|----------|-------|---------|
| `/api/cbc` | 30/hour | Content generation (main endpoint) |
| `/api/generate/audio` | 20/hour | Audio generation (resource-intensive) |
| `/api/generate/video` | 10/hour | Video generation (very resource-intensive) |
| `/api/generate/flashcards` | 20/hour | Flashcard generation |
| `/api/resources` | 100/hour | Resource listing (cheap operation) |

**Fallback:** If storage backend down, Redis limit reverts to in-memory storage

### API Authentication
- All `/api/*` endpoints require `@login_required_json` decorator
- Unauthenticated requests receive `401 Unauthorized` response
- Token/session validation happens before business logic

---

## 3. Security Headers

All responses include security headers:

```
X-Frame-Options: SAMEORIGIN                          # Prevent clickjacking
X-Content-Type-Options: nosniff                       # Prevent MIME sniffing
X-XSS-Protection: 1; mode=block                       # XSS protection
Referrer-Policy: strict-origin-when-cross-origin      # Privacy protection
Strict-Transport-Security: max-age=31536000           # HTTPS enforcement (production only)
Permissions-Policy: accelerometer=(), camera=(), ... # Disable unnecessary features
```

---

## 4. Input Validation & Sanitization

### Email Validation
- Format: `[user]@[domain].[tld]`
- Maximum length: 254 characters (RFC 5321)
- Case-insensitive normalization

### Name Validation
- Minimum length: 2 characters
- Maximum length: 100 characters
- HTML-escaped in output to prevent XSS

### File Upload Protection
- Sanitized filenames (no directory traversal)
- Special characters converted to underscores
- Maximum filename length: 255 characters
- Null byte removal to prevent injection

### SQL Query Protection
- **Parameterized queries** used throughout (? placeholders)
- User input never concatenated into SQL strings
- Connection pooling from `db_utils.DatabasePool`

**Example (Secure):**
```python
conn.execute("SELECT * FROM teachers WHERE email = ?", (email,))
```

---

## 5. CORS Configuration

### Production Configuration
```python
# Only allow trusted origins (set via CORS_ORIGINS env var)
CORS(app, origins=["https://yourdomain.com"], supports_credentials=True)
```

### Development Configuration
```python
CORS(app, origins="*", supports_credentials=True)
```

### How It Works
- Credentials are included in cross-site requests (`cookies`)
- Only whitelisted origins receive CORS headers
- Prevents attackers on different domains from accessing user data

---

## 6. HTTPS & SSL/TLS

### Production Deployment
- **Always use HTTPS** for external access
- Google Cloud Run provides automatic SSL certificates
- Set redirect in Cloud Load Balancer: HTTP → HTTPS (301)

### Configuration
```python
# Production only
if os.getenv("FLASK_ENV") == "production":
    SESSION_COOKIE_SECURE = True  # Only send over HTTPS
    HSTS_ENABLED = True           # Strict Transport Security
```

---

## 7. Environment Variables & Secrets

### Critical Secrets
Never commit these to version control:

```bash
FLASK_SECRET_KEY              # Session encryption key (generate: python -c 'import secrets; print(secrets.token_hex(32))')
GEMINI_API_KEY                # Google Gemini API key
OPENROUTER_API_KEY            # OpenRouter API key
ELEVENLABS_API_KEY            # ElevenLabs API key
OPENAI_API_KEY                # OpenAI API key (optional)
DATABASE_URL                  # PostgreSQL connection string (production)
FLASK_ENV                     # Set to 'production' in production
CORS_ORIGINS                  # Comma-separated allowed origins
RATELIMIT_STORAGE_URL         # Redis URL for rate limiting (optional)
```

### Setup Steps
1. **Generate FLASK_SECRET_KEY:**
   ```bash
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   ```

2. **Set in Google Cloud Console:**
   - GCP Console → Cloud Run/App Engine → Environment variables
   - Or use gcloud CLI:
     ```bash
     gcloud run services update eduripple-backend \
       --update-env-vars FLASK_SECRET_KEY=<generated_key>
     ```

3. **.env file (Development Only):**
   ```
   FLASK_ENV=development
   FLASK_SECRET_KEY=your_dev_key_here
   GEMINI_API_KEY=your_key
   OPENROUTER_API_KEY=your_key
   ELEVENLABS_API_KEY=your_key
   ```

4. **Add `.env` to `.gitignore`:**
   ```bash
   echo ".env" >> .gitignore
   ```

---

## 8. Database Security

### SQLite (Development)
- File-based database with OS-level file permissions
- Suitable for single-instance deployments
- **No network exposure** - access only from app process

### PostgreSQL (Production Recommended)
- Use Google Cloud SQL PostgreSQL
- Enable Cloud SQL Proxy for encrypted connections
- Connection string in `DATABASE_URL` environment variable

### Backup Security
- Background task runs daily backups (via `background_tasks.py`)
- Encrypted backups stored securely
- Automatic retention policy (120 days)

### Connection Pool
```python
db_pool = DatabasePool(TEACHERS_DB, pool_size=5)
# Prevents connection exhaustion attacks
```

---

## 9. Logging & Monitoring

### Security Event Logging
The `AuditLogger` class in `security.py` logs:

```python
# Authentication attempts
AuditLogger.log_authentication(user_id, email, status, ip_address)

# Unauthorized access attempts  
AuditLogger.log_authorization_failure(user_id, resource, action, ip_address)

# Sensitive operations (password changes, exports)
AuditLogger.log_sensitive_operation(user_id, operation, details, ip_address)

# Security errors
AuditLogger.log_error(error_type, message, ip_address)
```

### Log Location
- Local: `logs/app.log` (rotated at 10MB, 5 backups)
- Production: Google Cloud Logging (via `app.logger`)

### Monitoring Alerts
Set up alerts in Google Cloud for:
- Multiple failed login attempts (>5 in 5 minutes)
- Rate limit exceeded (429 responses)
- Database connection errors
- Unhandled exceptions

---

## 10. File Upload Security

### Current Implementation
Users can upload files to `/resources/` directory:

```python
RESOURCE_DIR = "resources"  # Local storage

# In production Cloud Run, files don't persist.
# Recommended: Use Google Cloud Storage instead
```

### Hardening Steps

**Option 1: Google Cloud Storage (Recommended)**
```python
from google.cloud import storage

client = storage.Client()
bucket = client.bucket('eduripple-files')
blob = bucket.blob(sanitized_filename)
blob.upload_from_filename(local_path)
```

**Option 2: File Type Validation**
```python
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.jpg', '.png', '.mp3', '.mp4'}

def is_allowed_file(filename):
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS
```

**Option 3: Virus Scanning**
```python
import clamd  # ClamAV virus scanner

def scan_uploaded_file(filepath):
    clam = clamd.ClamD()
    result = clam.scan_file(filepath)
    if result is None:
        return True  # Clean
    return False  # Infected
```

---

## 11. Dependency Vulnerability Scanning

### Check for Vulnerabilities
```bash
pip install safety
safety check

# Or use pip-audit
pip install pip-audit
pip-audit --desc
```

### Regular Updates
```bash
# Update all packages
pip install --upgrade -r requirements.txt

# Update a specific package
pip install --upgrade Flask
```

### Current Dependencies
All dependencies in `requirements.txt` are pinned to specific versions for reproducibility. Review changelog:
- Flask 3.1.1 (latest stable)
- Werkzeug 3.1.3 (secure password hashing)
- cryptography 42.0.7 (encryption primitives)
- bleach 6.1.0 (HTML sanitization)

---

## 12. Testing Security

### Unit Tests for Validation
```python
# tests/test_security.py
from security import InputValidator

def test_password_validation():
    # Too short
    assert not InputValidator.is_valid_password("Short1!")[0]
    
    # Missing uppercase
    assert not InputValidator.is_valid_password("lowercase123!")[0]
    
    # Valid
    assert InputValidator.is_valid_password("ValidPass123!")[0]

def test_email_validation():
    assert InputValidator.is_valid_email("user@example.com")
    assert not InputValidator.is_valid_email("invalid.email")

def test_sql_injection_prevention():
    # Parameterized queries prevent this
    email = "'; DROP TABLE teachers; --"
    teacher = get_teacher_by_email(email)  # Safe - no SQL injection
```

### Security Testing Tools
```bash
# OWASP Dependency Check
pip install pip-audit

# Static security analysis
pip install bandit
bandit -r . -ll  # Report low severity and higher

# Dynamic security testing
pip install safety
safety check
```

---

## 13. Deployment Checklist

Before deploying to production:

- [ ] **FLASK_SECRET_KEY** is set (generate new key)
- [ ] **FLASK_ENV** is set to "production"
- [ ] **HTTPS only** - Load balancer redirects HTTP → HTTPS
- [ ] **API keys** are set for all services (Gemini, OpenRouter, ElevenLabs)
- [ ] **CORS_ORIGINS** is set to your domain(s) only
- [ ] **Database** is backed up and monitored
- [ ] **Rate limiting** is enabled (Redis or in-memory)
- [ ] **Monitoring/alerts** configured in GCP
- [ ] **Logs** are captured and retained
- [ ] **SSL certificate** is valid (auto-renewed by GCP)
- [ ] **Dependencies** are up-to-date (run `pip-audit`)
- [ ] **Security headers** are verified with `curl`:
  ```bash
  curl -I https://your-api.com/api/system/health
  # Should show X-Frame-Options, X-Content-Type-Options, etc.
  ```

---

## 14. Incident Response

### If Compromised
1. **Immediately** revoke all API keys:
   - FLASK_SECRET_KEY → regenerate
   - GEMINI_API_KEY, OPENROUTER_API_KEY, ELEVENLABS_API_KEY → rotate
   
2. **Force all users to re-authenticate:**
   ```python
   # Clear all sessions
   conn.execute("DELETE FROM sessions")  # If using database sessions
   ```

3. **Review logs** for unauthorized access:
   ```bash
   grep "UNAUTHORIZED_ACCESS" logs/app.log
   ```

4. **Disable suspicious accounts:**
   ```python
   conn.execute("UPDATE teachers SET disabled=1 WHERE email=?", (suspicious_email,))
   ```

5. **Deploy security patch** and restart

---

## 15. Continuous Security

### Monthly Reviews
- Check for new security advisories in dependencies
- Review authentication logs for anomalies
- Update packages to latest versions

### Quarterly Audits
- Run full security vulnerability scan
- Penetration test critical endpoints
- Review CORS, headers, rate limits

### Annual Security Assessment
- Third-party security audit
- Compliance check (GDPR, educational privacy laws)
- Infrastructure security review

---

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Documentation](https://flask.palletsprojects.com/en/latest/security/)
- [Google Cloud Security Best Practices](https://cloud.google.com/security/best-practices)
- [CWE Top 25](https://cwe.mitre.org/top25/)

---

## Support

For security concerns or vulnerability reports:

1. **Do NOT** create public GitHub issues for security bugs
2. Email: security@[yourdomain.com] with details
3. Provide steps to reproduce (if possible)
4. Allow time for a fix before public disclosure
