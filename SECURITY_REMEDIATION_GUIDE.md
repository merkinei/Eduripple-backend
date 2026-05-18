# CRITICAL SECURITY REMEDIATION GUIDE
## Urgent Actions Required Before Deployment

**Prepared:** February 23, 2026
**Status:** 🔴 CRITICAL - Action Required

---

## Executive Summary

Your project's API keys are currently **exposed** in the `.env` file which may be tracked in git history. 

### Immediate Threats
1. ✅ Gemini API Key - **EXPOSED IN .env**
2. ✅ OpenRouter API Key - **EXPOSED IN .env**  
3. ✅ OpenAI API Key - **EXPOSED IN .env**
4. ✅ YouTube API Key - **EXPOSED IN .env**
5. Potential Git history exposure if .env was committed

---

## PHASE 1: Immediate Actions (Next 24 hours)

### Step 1: Secure the .env File (Local)
```powershell
# Create a backup of current .env
Copy-Item .env .env.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')

# Now secure it with restricted permissions (Windows)
icacls .env /inheritance:r /grant:r "%USERNAME%:F" /C
```

### Step 2: Check if .env is in Git History
```powershell
# Install git from: https://git-scm.com/download/win
# After installation, open new PowerShell and run:

# Check if .env is tracked in git
git ls-files | Select-String .env

# Check git history for .env commits
git log --all -- .env

# Search for API keys in all commits
git log -p --all -S "GEMINI_API_KEY\|OPENROUTER_API_KEY\|OPENAI_API_KEY" | head -20
```

### Step 3: Remove .env from Git Tracking
```powershell
# If .env is tracked in git:
git rm --cached .env
git commit -m "chore: remove .env with exposed API keys from git tracking"

# Force push to update remote (use with caution!)
git push origin main --force-with-lease
```

### Step 4: Rotate ALL API Keys IMMEDIATELY

#### 🔴 Gemini API Key
1. Go to: https://aistudio.google.com/app/apikey
2. Delete the old key shown in .env
3. Create a new key
4. Update `.env` with new key

#### 🔴 OpenRouter API Key
1. Go to: https://openrouter.ai/keys
2. Delete/revoke the old key
3. Create a new key
4. Update `.env` with new key

#### 🔴 OpenAI API Key
1. Go to: https://platform.openai.com/api-keys
2. Delete the old key
3. Create a new key
4. Update `.env` with new key

#### 🔴 YouTube API Key
1. Go to: https://console.cloud.google.com/apis/credentials
2. Delete the old key
3. Create a new key
4. Update `.env` with new key

---

## PHASE 2: Verify Security

### Step 5: Update .env File Format
Replace values in `.env` with **rotated keys only**:

```
FLASK_ENV=production
FLASK_SECRET_KEY=<generate-strong-key>
DATABASE_URL=postgresql://user:pass@host:5432/dbname
GEMINI_API_KEY=<NEW-ROTATED-KEY>
OPENROUTER_API_KEY=<NEW-ROTATED-KEY>
OPENAI_API_KEY=<NEW-ROTATED-KEY>
YOUTUBE_API_KEY=<NEW-ROTATED-KEY>
ENVIRONMENT=production
```

Generate strong FLASK_SECRET_KEY:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 6: Verify .gitignore is Correct
Check that .env is properly ignored:
```powershell
# These should all show .env is ignored:
cat .gitignore | Select-String "^\.env$"

# Verify git won't track it
git check-ignore .env
# Should output: ".env"
```

### Step 7: Clean Git History (Complete Removal)

If .env was committed to git history, you need to **completely remove it from history**:

Using **git-filter-branch** (manual method):
```powershell
# WARNING: This rewrites git history for entire repository
git filter-branch --tree-filter 'rm -f .env' HEAD

# Force push to update remote
git push origin --force-all
# Notify team to re-clone repository
```

**Better Option: Use BFG Repo Cleaner** (faster, safer):
1. Download: https://rtyley.github.io/bfg-repo-cleaner/
2. Extract to a folder
3. Run: `java -jar bfg.jar --delete-files .env <repository-path>`
4. Then: `git reflog expire --expire=now --all && git gc --prune=now --aggressive`
5. Force push: `git push origin --force-all`

---

## PHASE 3: Deployment Security Checklist

- [ ] All API keys rotated in their respective platforms
- [ ] New keys added to `.env` file
- [ ] `.env` removed from git history (if previously committed)
- [ ] `.gitignore` verified to exclude `.env`
- [ ] Strong `FLASK_SECRET_KEY` generated and set
- [ ] `.env` file permissions restricted (local machine)
- [ ] `.env.example` is safe (no real secrets)
- [ ] Verified git repo no longer contains API keys
- [ ] Team members notified if git history was rewritten
- [ ] Backup of old .env kept safely for reference

---

## PHASE 4: Production Secrets Management

### Option A: Environment Variables (Recommended for Cloud)

**Heroku:**
```powershell
heroku config:set GEMINI_API_KEY=<new-key>
heroku config:set OPENROUTER_API_KEY=<new-key>
heroku config:set OPENAI_API_KEY=<new-key>
heroku config:set YOUTUBE_API_KEY=<new-key>
heroku config:set FLASK_SECRET_KEY=<strong-key>
```

**AWS Elastic Beanstalk:**
- Use EB Console > Configuration > Environment Properties
- Or use `eb setenv` command

**Google Cloud Run:**
- Set in Cloud Run console or via `gcloud run deploy --set-env-vars`

**DigitalOcean:**
- Set in App Platform dashboard

### Option B: Secrets Manager (Enterprise)

**AWS Secrets Manager:**
```powershell
aws secretsmanager create-secret `
  --name eduripple/prod/api-keys `
  --secret-string '{
    "GEMINI_API_KEY": "...",
    "OPENROUTER_API_KEY": "...",
    "OPENAI_API_KEY": "...",
    "YOUTUBE_API_KEY": "..."
  }'
```

**Google Cloud Secret Manager:**
```powershell
gcloud secrets create gemini-api-key --data-file=- <<< "your-key"
gcloud secrets create openrouter-api-key --data-file=- <<< "your-key"
# etc...
```

**HashiCorp Vault:**
- Enterprise-grade secret management
- See: https://www.vaultproject.io/

---

## PHASE 5: Ongoing Security

### Monthly Tasks
- [ ] Check API key age: `GEMINI_API_KEY` (check creation date in console)
- [ ] Review API usage in console
- [ ] Verify .env is not accidentally committed

### Quarterly Tasks  
- [ ] Rotate API keys (security best practice)
- [ ] Audit git history for any secrets
- [ ] Update dependencies
- [ ] Security audit

### Annual Tasks
- [ ] Full security assessment
- [ ] Penetration testing
- [ ] Compliance review

---

## Verification Commands

### Before Deployment - Run These:

```powershell
# 1. Verify .env is ignored
git status
# Should NOT show .env in output

# 2. Verify no API keys in git history
git log -p | Select-String "GEMINI_API_KEY|OpenAI|OpenRouter"
# Should have NO matches

# 3. Check current .env is secure
Test-Path .env
# Should show True

# 4. Verify .env.example is safe
cat .env.example | Select-String "sk-"
# Should have NO matches (no actual keys)

# 5. Test Flask app starts correctly
python main.py.py
# Should show: "Running on http://localhost:5000"
```

---

## Incident Response - If Keys Were Exposed Online

1. **Immediately (within minutes):**
   - [ ] Rotate all exposed API keys
   - [ ] Revoke old keys in each provider
   - [ ] Check for unauthorized usage/charges

2. **Short-term (within hours):**
   - [ ] Remove .env from git history
   - [ ] Force push updated code
   - [ ] Notify team members
   - [ ] Update deployment with new keys

3. **Medium-term (within days):**
   - [ ] Review API usage logs for suspicious activity
   - [ ] Check git access logs
   - [ ] Update security procedures
   - [ ] Consider security audit

4. **Long-term (ongoing):**
   - [ ] Implement automated key rotation
   - [ ] Deploy centralized secret management
   - [ ] Train team on security best practices

---

## Key Resources

| Resource | URL |
|----------|-----|
| Git Installation | https://git-scm.com/download/win |
| BFG Repo Cleaner | https://rtyley.github.io/bfg-repo-cleaner/ |
| Gemini API | https://aistudio.google.com/app/apikey |
| OpenRouter | https://openrouter.ai/keys |
| OpenAI | https://platform.openai.com/api-keys |
| YouTube API | https://console.cloud.google.com/apis/credentials |

---

## Deployment Checklists by Platform

### ✅ Heroku
- [x] Create app with PostgreSQL addon
- [ ] Set environment variables for all API keys
- [ ] Deploy with `git push heroku main`
- [ ] Run `heroku run python setup_db.py`
- [ ] Test health endpoint

### ✅ AWS Elastic Beanstalk  
- [x] Create EB application
- [x] Create environment with RDS PostgreSQL
- [ ] Configure environment variables
- [ ] Deploy application
- [ ] Initialize database

### ✅ Google Cloud Run
- [x] Build Docker image
- [ ] Deploy to Cloud Run
- [ ] Attach Cloud SQL (PostgreSQL)
- [ ] Set environment variables
- [ ] Test deployment

---

## Sign-Off

**Completed by:** _____________
**Date:** February 23, 2026
**Next Review:** _____________

---

⚠️ **DO NOT PROCEED WITH DEPLOYMENT UNTIL ALL CRITICAL SECURITY FIXES ARE COMPLETE**
