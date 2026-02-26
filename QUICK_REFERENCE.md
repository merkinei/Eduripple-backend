# QUICK REFERENCE - Critical Security Fixes

## 🚨 EMERGENCY: Do These First (In Order)

### 1️⃣ SECURE YOUR LOCAL .env FILE (5 minutes)
```powershell
# Windows - Restrict file access
icacls .env /inheritance:r /grant:r "%USERNAME%:F" /C
```

### 2️⃣ INSTALL GIT (2 minutes)
Download & install: https://git-scm.com/download/win  
**Then RESTART PowerShell**

### 3️⃣ CHECK IF .env IS IN GIT (5 minutes)
```powershell
git log --all -- .env
git log -p --all -S "GEMINI_API_KEY" | head -20
```
- If nothing appears → ✅ SAFE, go to Task 5
- If results appear → 🔴 CRITICAL, do Task 4

### 4️⃣ REMOVE FROM GIT HISTORY (if needed)
```powershell
# Option A: Simple (keeps commit history)
git rm --cached .env
git commit -m "Remove .env"
git push origin main

# Option B: Complete (rewrites history - RECOMMENDED)
# Use BFG Repo Cleaner: https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files .env .
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force-all
```

### 5️⃣ ROTATE EACH API KEY (45 minutes total)

**Gemini:** https://aistudio.google.com/app/apikey
- [ ] Delete old key
- [ ] Create new key
- [ ] Update `.env`

**OpenRouter:** https://openrouter.ai/keys
- [ ] Delete old key
- [ ] Create new key
- [ ] Update `.env`

**OpenAI:** https://platform.openai.com/api-keys
- [ ] Delete old key
- [ ] Create new key
- [ ] Update `.env`

**YouTube:** https://console.cloud.google.com/apis/credentials
- [ ] Delete old key
- [ ] Create new key
- [ ] Update `.env`

### 6️⃣ UPDATE .env WITH NEW VALUES
```
FLASK_ENV=production
FLASK_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
GEMINI_API_KEY=<new-key>
OPENROUTER_API_KEY=<new-key>
OPENAI_API_KEY=<new-key>
YOUTUBE_API_KEY=<new-key>
DATABASE_URL=postgresql://user:pass@host:5432/db
ENVIRONMENT=production
```

### 7️⃣ VERIFY SECURITY (10 minutes)
```powershell
# No .env in git
git status
git check-ignore .env

# .env.example is safe
cat .env.example | Select-String "sk-"

# App starts
python main.py.py
# Press CTRL+C to stop
```

### 8️⃣ CHOOSE DEPLOYMENT PLATFORM (2 minutes)

| Platform | Time | Link | Recommended |
|----------|------|------|-------------|
| Docker Compose (Local) | 30 min | `docker-compose up -d` | Testing |
| Heroku | 45 min | [Guide](DEPLOYMENT_GUIDE.md#option-a-heroku-deployment) | ⭐ Fastest |
| AWS | 2 hrs | [Guide](DEPLOYMENT_GUIDE.md#option-b-aws-elastic-beanstalk) | Enterprise |
| Google Cloud Run | 1.5 hrs | [Guide](DEPLOYMENT_GUIDE.md#option-c-google-cloud-run) | Serverless |

---

## ✅ Verification Checklist

Before deployment verify:

```powershell
# 1. Config files exist
Test-Path requirements.txt           # ✅ Should show True
Test-Path config.py                  # ✅ Should show True  
Test-Path wsgi.py                    # ✅ Should show True
Test-Path Procfile                   # ✅ Should show True
Test-Path Dockerfile                 # ✅ Should show True
Test-Path docker-compose.yml         # ✅ Should show True

# 2. .env is secure
Test-Path .env                       # ✅ Should show True (but not in git!)
git check-ignore .env                # ✅ Should output: .env

# 3. .env.example is safe (no real keys)
Select-String "sk-" .env.example     # ✅ Should have NO matches
Select-String "AIza" .env.example    # ✅ Should have NO matches

# 4. App starts
python main.py.py                    # ✅ Should show running on http://localhost:5000
# Ctrl+C to stop

# 5. All new keys in .env
cat .env | Select-String "GEMINI_API_KEY"    # ✅ Should show new key
cat .env | Select-String "OPENROUTER_API_KEY" # ✅ Should show new key
```

---

## 📋 Files You Have

```
✅ requirements.txt ............. Python dependencies
✅ config.py .................... Environment config
✅ wsgi.py ...................... Production entry
✅ setup_db.py .................. Database setup
✅ Procfile ..................... Heroku
✅ Dockerfile ................... Container
✅ docker-compose.yml ........... Local dev
✅ .env.example ................. Safe template
🔄 .env ......................... UPDATE WITH NEW KEYS
✅ .gitignore ................... Git ignore rules
✅ DEPLOYMENT_CHECKLIST.md ...... Full checklist
✅ DEPLOYMENT_GUIDE.md .......... Platform guides
✅ SECURITY_REMEDIATION_GUIDE.md Security details
✅ IMMEDIATE_ACTION_CHECKLIST.md This guide (detailed)
```

---

## 🚀 Deployment Paths

### Path A: Local Testing First (Recommended)
1. ✅ Secure .env
2. ✅ Rotate API keys
3. ✅ `docker-compose up -d` (test locally)
4. ✅ Choose platform
5. ✅ Deploy

### Path B: Straight to Production
1. ✅ Secure .env
2. ✅ Rotate API keys
3. ✅ Choose platform (Heroku easiest)
4. ✅ Follow platform guide
5. ✅ Deploy

---

## ⏱️ Time Estimates

| Task | Time |
|------|------|
| Secure .env | 5 min |
| Git setup & verify | 20 min |
| Rotate 4 API keys | 45 min |
| Generate new secret | 2 min |
| Update .env | 5 min |
| Verify security | 10 min |
| **TOTAL SECURITY PHASE** | **~90 min** |
| Local test (Docker) | 30 min |
| Heroku deployment | 45 min |
| AWS deployment | 2 hrs |
| GCP deployment | 1.5 hrs |

---

## 🆘 Troubleshooting

### Git not recognized
```powershell
# Restart PowerShell after installing git
# Try in new window/tab
```

### Can't generate FLASK_SECRET_KEY
```powershell
# Make sure Python is in PATH
python --version  # Should show Python 3.x

# Alternative way to generate
python -m secrets -c "import secrets; print(secrets.token_hex(32))"
```

### .env permissions error
```powershell
# Try different approach
takeown /F .env /A
icacls .env /grant "%USERNAME%:F"
```

### Docker not working locally
```powershell
# Install Docker Desktop: https://www.docker.com/products/docker-desktop
# Restart computer
# Try: docker ps
```

---

## 📞 Support Resources

| Issue | Resource |
|-------|----------|
| Git help | https://git-scm.com/ |
| History removal | https://rtyley.github.io/bfg-repo-cleaner/ |
| Heroku deploy | [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#option-a-heroku-deployment) |
| Docker help | https://docs.docker.com/ |
| Security questions | [SECURITY_REMEDIATION_GUIDE.md](SECURITY_REMEDIATION_GUIDE.md) |

---

**Status:** 🚨 AWAITING YOUR ACTION
**Next Step:** Follow checklist items 1-8 above in order
**Target Completion:** 24 hours
**Then:** Choose deployment platform and follow guide
