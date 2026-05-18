# EduRipple Developer Security Guide

## Writing Secure Code for EduRipple

This guide shows developers how to implement security best practices when adding new features.

---

## 1. Database Queries - Always Parameterize

### ✅ CORRECT - Parameterized Query
```python
# Using ? placeholders with tuple of values
email = "user@example.com"
teacher = conn.execute(
    "SELECT * FROM teachers WHERE email = ?",
    (email,)  # Values in tuple
).fetchone()
```

### ❌ WRONG - String Concatenation
```python
# VULNERABLE TO SQL INJECTION
email = "';DROP TABLE teachers;--"
teacher = conn.execute(f"SELECT * FROM teachers WHERE email = '{email}'")
# Executes: SELECT * FROM teachers WHERE email = '';DROP TABLE teachers;--'
# This deletes the teachers table!
```

### ✅ Security Pattern for Complex Queries
```python
def get_teacher_resources(teacher_id, subject=None):
    """Get resources for a teacher, optionally filtered by subject"""
    query = "SELECT id, name, url FROM resources WHERE teacher_id = ?"
    params = [teacher_id]
    
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    
    return conn.execute(query, tuple(params)).fetchall()
```

---

## 2. Input Validation - Always Validate

### ✅ CORRECT - Comprehensive Validation
```python
from security import InputValidator

@app.route("/teacher/update", methods=["POST"])
@login_required_json
def update_teacher():
    data = request.get_json()
    
    # Validate email
    email = data.get('email', '').strip().lower()
    if not InputValidator.is_valid_email(email):
        return jsonify({"error": "Invalid email format"}), 400
    
    # Validate name length
    name = data.get('name', '').strip()
    if len(name) < 2 or len(name) > 100:
        return jsonify({"error": "Name must be 2-100 characters"}), 400
    
    # Sanitize bio (allow HTML, but escape dangerous tags)
    bio = InputValidator.sanitize_string(data.get('bio', ''), max_length=1000)
    
    # Update database with validated inputs
    conn.execute(
        "UPDATE teachers SET email = ?, name = ?, bio = ? WHERE id = ?",
        (email, name, bio, session['teacher_id'])
    )
    
    return jsonify({"success": True})
```

### ❌ WRONG - No Validation
```python
@app.route("/teacher/update", methods=["POST"])
def update_teacher():
    data = request.get_json()
    
    # These could contain malicious data, SQL injection, XSS, etc.
    email = data['email']
    name = data['name']
    bio = data['bio']
    
    # Database update - potentially vulnerable
    conn.execute(f"UPDATE teachers SET email='{email}', name='{name}' WHERE id={session['teacher_id']}")
```

---

## 3. File Uploads - Sanitize Filenames

### ✅ CORRECT
```python
import os
from security import InputValidator

@app.route("/upload", methods=["POST"])
@login_required_json
@limiter.limit("20 per hour")
def upload_file():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file provided"}), 400
    
    # Sanitize filename
    filename = InputValidator.sanitize_filename(file.filename)
    
    # Validate file extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ['.pdf', '.docx', '.txt']:
        return jsonify({"error": "Only PDF, DOCX, TXT allowed"}), 400
    
    # Add timestamp to make filename unique
    import time
    safe_filename = f"{int(time.time())}_{filename}"
    
    # Save to secure location
    filepath = os.path.join(RESOURCE_DIR, safe_filename)
    file.save(filepath)
    
    return jsonify({"success": True, "filename": safe_filename})
```

### ❌ WRONG - Directory Traversal Vulnerability
```python
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get('file')
    
    # Attacker could upload file as: "../../../etc/passwd"
    # This would write to filesystem outside intended directory
    filepath = os.path.join(RESOURCE_DIR, file.filename)
    file.save(filepath)  # VULNERABLE!
```

---

## 4. Authentication - Check Permissions

### ✅ CORRECT - Verify Resource Ownership
```python
@app.route("/resource/<int:resource_id>", methods=["DELETE"])
@login_required_json
def delete_resource(resource_id):
    # Verify the resource exists and belongs to the current user
    resource = conn.execute(
        "SELECT id, teacher_id FROM resources WHERE id = ?",
        (resource_id,)
    ).fetchone()
    
    if not resource:
        return jsonify({"error": "Resource not found"}), 404
    
    # Check ownership
    if resource['teacher_id'] != session['teacher_id']:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Now safe to delete
    conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    return jsonify({"success": True})
```

### ❌ WRONG - No Authorization Check
```python
@app.route("/resource/<int:resource_id>", methods=["DELETE"])
@login_required_json
def delete_resource(resource_id):
    # Just delete without checking ownership!
    # Any logged-in user can delete any resource
    conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    return jsonify({"success": True})
```

---

## 5. API Endpoints - Add Rate Limiting

### ✅ CORRECT - Protected Endpoint
```python
from flask_limiter import Limiter

@app.route("/api/generate/content", methods=["POST"])
@login_required_json
@limiter.limit("30 per hour")  # Prevents abuse
def generate_content():
    # Implementation
    pass
```

### ❌ WRONG - No Rate Limiting
```python
@app.route("/api/generate/content", methods=["POST"])
@login_required_json
def generate_content():
    # Attacker could flood with requests
    # This would:
    # - Use up API quota
    # - Consume server resources
    # - Cause DDoS effect
    pass
```

---

## 6. Sensitive Data - Never Log It

### ✅ CORRECT
```python
import logging
from security import AuditLogger

logger = logging.getLogger(__name__)

@app.route("/teacher/signin", methods=["POST"])
@limiter.limit("10 per hour")
def signin():
    email = request.form.get('email')
    password = request.form.get('password')
    
    teacher = get_teacher_by_email(email)
    ip = request.remote_addr
    
    if not teacher or not check_password_hash(teacher['password_hash'], password):
        # Log the attempt but NOT the password
        AuditLogger.log_authentication(None, email, "failed", ip)
        logger.warning(f"Failed login attempt for {email}")
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Log successful auth with user ID and IP
    AuditLogger.log_authentication(teacher['id'], email, "success", ip)
    session['teacher_id'] = teacher['id']
    
    return jsonify({"success": True})
```

### ❌ WRONG - Logs Password
```python
@app.route("/teacher/signin", methods=["POST"])
def signin():
    email = request.form.get('email')
    password = request.form.get('password')  # Plain text
    
    # SECURITY BREACH: Logging password
    logger.info(f"Login attempt: email={email}, password={password}")
    
    # If logs are compromised, passwords are exposed
```

---

## 7. Error Handling - Be Vague to Users

### ✅ CORRECT - Don't Leak Information
```python
@app.route("/teacher/signin", methods=["POST"])
@limiter.limit("10 per hour")
def signin():
    email = request.form.get('email')
    password = request.form.get('password')
    
    teacher = get_teacher_by_email(email)
    
    # Use same generic message for both cases
    if not teacher or not check_password_hash(teacher['password_hash'], password):
        # Don't say "email doesn't exist" - allows account enumeration
        return jsonify({"error": "Invalid email or password"}), 401
    
    return jsonify({"success": True})
```

### ❌ WRONG - Leaks Information
```python
@app.route("/teacher/signin", methods=["POST"])
def signin():
    email = request.form.get('email')
    password = request.form.get('password')
    
    teacher = get_teacher_by_email(email)
    
    if not teacher:
        # Attacker learns this email isn't registered
        return jsonify({"error": "Email not found"}), 404
    
    if not check_password_hash(teacher['password_hash'], password):
        # Attacker learns email exists but password is wrong
        return jsonify({"error": "Password incorrect"}), 401
    
    # This enables account enumeration attacks
```

---

## 8. Environment Variables - Never Hardcode Secrets

### ✅ CORRECT
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Get from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///default.db")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in environment")
```

### ❌ WRONG - Hardcoded Secret
```python
# NEVER DO THIS
GEMINI_API_KEY = "sk-1234567890abcdefghijklmnopqrst"  # Exposed if committed!
DATABASE_PASSWORD = "my_secure_password_123"  # In plain text!
```

---

## 9. Input Sanitization - Prevent XSS

### ✅ CORRECT
```python
from security import InputValidator

@app.route("/lesson/<lesson_id>", methods=["GET"])
def view_lesson(lesson_id):
    lesson = get_lesson(lesson_id)
    
    # in template, use autoescape (Flask default)
    return render_template("lesson.html", lesson=lesson)

# In template (Jinja2 will auto-escape):
# {{ lesson.title }}            # Automatically HTML-escaped
# {{ lesson.description|safe }}  # HTML not escaped (use for trusted content only)
```

### ❌ WRONG - Vulnerable to XSS
```python
@app.route("/lesson/<lesson_id>", methods=["GET"])
def view_lesson(lesson_id):
    lesson = get_lesson(lesson_id)
    
    # If lesson.title contains: <img src=x onerror="alert('hacked')">
    return f"<h1>{lesson.title}</h1>"  # Not escaped - XSS vulnerability!
```

---

## 10. Testing Security

### Security Test Cases
```python
# tests/test_security.py

def test_sql_injection_prevention():
    """Verify SQL injection is prevented"""
    malicious_email = "'; DROP TABLE teachers; --"
    teacher = get_teacher_by_email(malicious_email)
    
    # Should return None, not execute DROP
    assert teacher is None

def test_xss_prevention():
    """Verify HTML is escaped"""
    malicious_name = "<script>alert('xss')</script>"
    sanitized = InputValidator.sanitize_string(malicious_name)
    
    # Should escape the script tags
    assert "<script>" not in sanitized
    assert "&lt;script&gt;" in sanitized

def test_authentication_required():
    """Verify protected endpoints require auth"""
    response = client.get("/teacher/dashboard")
    
    # Should redirect to signin if not authenticated
    assert response.status_code == 302

def test_rate_limiting():
    """Verify rate limiting works"""
    for i in range(11):
        response = client.post("/teacher/signin", data={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        
    # After 10 attempts, should get rate limited
    assert response.status_code == 429

def test_password_strength():
    """Verify weak passwords are rejected"""
    weak_passwords = [
        "short",           # Too short
        "nouppercase1!",   # No uppercase
        "NOLOWERCASE1!",   # No lowercase
        "NoNumbers!",      # No numbers
        "NoSpecial123",    # No special chars
    ]
    
    for pwd in weak_passwords:
        is_valid, _ = InputValidator.is_valid_password(pwd)
        assert not is_valid
```

---

## 11. Code Review Checklist

When reviewing pull requests:

- [ ] All database queries use parameterized queries (?)
- [ ] All user inputs are validated
- [ ] Sensitive data is never logged
- [ ] File uploads are sanitized
- [ ] Protected endpoints check permissions
- [ ] Rate limiting applied to resource-intensive endpoints
- [ ] Secrets are not hardcoded
- [ ] Error messages don't leak information
- [ ] HTML output is escaped (auto-escaped by Jinja2)
- [ ] CSRF tokens are used for state-changing operations

---

## 12. Quick Reference - Security Functions

```python
# Input validation
from security import InputValidator

InputValidator.is_valid_email(email)           # Validate email
InputValidator.is_valid_password(pwd)          # Check password strength
InputValidator.sanitize_string(text, max_len)  # Remove malicious content
InputValidator.sanitize_filename(filename)     # Safe filename
InputValidator.prevent_xss(data)               # Escape HTML

# Rate limiting
@limiter.limit("10 per hour")
def my_endpoint():
    pass

# Audit logging
from security import AuditLogger

AuditLogger.log_authentication(user_id, email, status, ip)
AuditLogger.log_authorization_failure(user_id, resource, action, ip)
AuditLogger.log_sensitive_operation(user_id, op, details, ip)

# Password hashing
from security import PasswordSecurity

hashed = PasswordSecurity.hash_password(password)
is_valid = PasswordSecurity.verify_password(password, hash)
token = PasswordSecurity.generate_secure_token()
```

---

## Common Security Mistakes to Avoid

1. ❌ Trusting user input - Always validate
2. ❌ String concatenation in SQL - Always parameterize
3. ❌ Hardcoding secrets - Always use env vars
4. ❌ Logging passwords - Never log sensitive data
5. ❌ Detailed error messages - Be vague to users
6. ❌ No rate limiting - Add limits to expensive operations
7. ❌ Skipping authentication checks - Always verify permissions
8. ❌ No file validation - Always check filenames
9. ❌ HTTP instead of HTTPS - Always use HTTPS
10. ❌ Using old dependencies - Update regularly

---

## Security Incident Response

If you find a vulnerability:

1. **Do NOT** commit the fix to main branch
2. **Create** a private security branch
3. **Test** the fix thoroughly
4. **Request** security review before merging
5. **Plan** a deployment with security team

---

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security](https://flask.palletsprojects.com/en/latest/security/)
- [Python Security Best Practices](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [CWE Top 25](https://cwe.mitre.org/top25/)

---

## Questions?

See SECURITY_HARDENING_GUIDE.md for comprehensive reference.
