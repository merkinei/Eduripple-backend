# DEPLOYMENT CHECKLIST - IMMEDIATE ACTIONS

## Status: 🔴 CRITICAL - Security Phase Active

**Start Date:** February 23, 2026  
**Target Completion:** Within 24-48 hours

---

## PHASE 1: CRITICAL SECURITY FIXES ⚠️

### ✅ Task 1: Secure .env File Locally
**Priority:** 🔴 CRITICAL - DO FIRST
**Time:** 5 minutes

- [ ] Create backup: `Copy-Item .env .env.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')`
- [ ] Restrict file permissions (Windows):
  ```powershell
  icacls .env /inheritance:r /grant:r "%USERNAME%:F" /C
  ```
- [ ] Verify only your user can read it
- [ ] Move backup to secure location

**Completion:** ____/____/____

---

### ✅ Task 2: Check if .env is in Git History
**Priority:** 🔴 CRITICAL
**Time:** 15 minutes
**Requires:** Git installation

1. [ ] Install Git from: https://git-scm.com/download/win
2. [ ] Open NEW PowerShell window (after Git installation)
3. [ ] Run these commands:
   ```powershell
   cd C:\Users\Admin\Desktop\eduripple-backend
   
   # Check if .env is tracked
   git ls-files | Select-String .env
   
   # Check if .env appears in history
   git log --all -- .env
   
   # Search for API keys in all commits
   git log -p --all -S "GEMINI_API_KEY" | head -50
   ```

**Result:** 
- [ ] .env is NOT in git history (✅ SAFE)
- [ ] .env IS in git history (⚠️ MUST REMOVE - See Task 5)

**Completion:** ____/____/____

---

### ✅ Task 3: Rotate Gemini API Key
**Priority:** 🔴 CRITICAL
**Time:** 10 minutes
**Platform:** Google AI Studio

1. [ ] Go to: https://aistudio.google.com/app/apikey
2. [ ] Note the OLD key from `.env`
3. [ ] Delete/revoke the old key
4. [ ] Create a NEW key
5. [ ] Copy new key
6. [ ] Update in `.env`: `GEMINI_API_KEY=<NEW-KEY>`
7. [ ] Test: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Key loaded' if os.getenv('GEMINI_API_KEY') else 'Key NOT found')"`

**New Key:** ________________  
**Completion:** ____/____/____

---

### ✅ Task 4: Rotate OpenRouter API Key  
**Priority:** 🔴 CRITICAL
**Time:** 10 minutes
**Platform:** OpenRouter

1. [ ] Go to: https://openrouter.ai/keys
2. [ ] Note the OLD key from `.env`
3. [ ] Delete/revoke the old key
4. [ ] Create a NEW key
5. [ ] Copy new key
6. [ ] Update in `.env`: `OPENROUTER_API_KEY=<NEW-KEY>`
7. [ ] Verify backup of old key deleted

**New Key:** ________________  
**Completion:** ____/____/____

---

### ✅ Task 5: Rotate OpenAI API Key
**Priority:** 🔴 CRITICAL
**Time:** 10 minutes
**Platform:** OpenAI Platform

1. [ ] Go to: https://platform.openai.com/api-keys
2. [ ] Note the OLD key from `.env`
3. [ ] Delete the old key
4. [ ] Create a NEW key
5. [ ] Copy new key
6. [ ] Update in `.env`: `OPENAI_API_KEY=<NEW-KEY>`

**New Key:** ________________  
**Completion:** ____/____/____

---

### ✅ Task 6: Rotate YouTube API Key
**Priority:** 🔴 CRITICAL  
**Time:** 10 minutes
**Platform:** Google Cloud Console

1. [ ] Go to: https://console.cloud.google.com/apis/credentials
2. [ ] Note the OLD key from `.env`
3. [ ] Delete the old key
4. [ ] Create a NEW key (API key, not OAuth)
5. [ ] Copy new key
6. [ ] Update in `.env`: `YOUTUBE_API_KEY=<NEW-KEY>`

**New Key:** ________________  
**Completion:** ____/____/____

---

### ✅ Task 7: Generate Strong FLASK_SECRET_KEY
**Priority:** 🟡 HIGH
**Time:** 2 minutes

```powershell
# Run this command and save the output
python -c "import secrets; key=secrets.token_hex(32); print(f'FLASK_SECRET_KEY={key}')"

# Example output: FLASK_SECRET_KEY=a1b2c3d4e5f6...

# Copy the key (not the "FLASK_SECRET_KEY=" part) and update .env
```

**Generated Key:** ________________  
**Added to .env:** [ ]

**Completion:** ____/____/____

---

### ✅ Task 8: Remove .env from Git Tracking (If Present)
**Priority:** 🔴 CRITICAL (conditional)
**Time:** 20 minutes
**Only if:** .env was found in git history from Task 2

**OPTION A: Simple Removal (No History Rewrite)**
```powershell
git rm --cached .env
git commit -m "chore: remove .env with exposed secrets from tracking"
git push origin main --force-with-lease
```

**OPTION B: Complete History Cleansing (RECOMMENDED)**
1. [ ] Download BFG Repo Cleaner: https://rtyley.github.io/bfg-repo-cleaner/
2. [ ] Extract to: `C:\tools\bfg\`
3. [ ] Run: `java -jar C:\tools\bfg\bfg.jar --delete-files .env .`
4. [ ] Cleanup: `git reflog expire --expire=now --all && git gc --prune=now --aggressive`
5. [ ] Force push: `git push origin --force-all`
6. [ ] Notify team to re-clone repository

**Status:** [ ] Not needed (not in git) | [ ] Simple removal | [ ] Full history cleansing  
**Completion:** ____/____/____

---

## PHASE 2: VERIFICATION ✅

### ✅ Task 9: Verify .env Security
**Priority:** 🟡 HIGH
**Time:** 10 minutes

Run these verification steps:

```powershell
# 1. Check .env is NOT in git
git status
# Result should NOT mention .env

# 2. Check .env is in .gitignore
cat .gitignore | Select-String "^\.env$"
# Should output: .env

# 3. Check Git will ignore it
git check-ignore .env
# Should output: .env

# 4. Verify .env.example has NO real keys
cat .env.example | Select-String "sk-|AIza|AIzaSy"
# Should have NO matches

# 5. Verify current .env keys are NEW
cat .env | Select-String "GEMINI_API_KEY|OPENROUTER_API_KEY"
# Verify these are your NEW keys, not the exposed ones
```

**Results:**
- [ ] .env not in git status: ✅ PASS
- [ ] .env in .gitignore: ✅ PASS
- [ ] Git will ignore .env: ✅ PASS
- [ ] .env.example is safe: ✅ PASS
- [ ] New keys are in .env: ✅ PASS

**Completion:** ____/____/____

---

### ✅ Task 10: Test Application Startup
**Priority:** 🟡 HIGH
**Time:** 5 minutes

```powershell
# Activate venv
& C:\Users\Admin\Desktop\eduripple-backend\.venv\Scripts\Activate.ps1

# Test Flask app starts
python main.py.py

# Expected output:
# * Running on http://localhost:5000
# * Press CTRL+C to quit
```

**Results:**
- [ ] App started successfully
- [ ] No API key errors
- [ ] No configuration errors

**Completion:** ____/____/____

---

## PHASE 3: DOCUMENTATION & SIGN-OFF

### ✅ Task 11: Complete Documentation
**Priority:** 🟢 NORMAL
**Time:** 5 minutes

- [ ] Read [SECURITY_REMEDIATION_GUIDE.md](SECURITY_REMEDIATION_GUIDE.md)
- [ ] Review deployment platform choice
- [ ] Document any questions or issues
- [ ] Plan deployment timeline

**Key Decisions Made:**
1. Deployment Platform: ____________________
2. Database: ____________________
3. Monitoring Service: ____________________

**Completion:** ____/____/____

---

### ✅ Task 12: Final Security Review
**Priority:** 🔴 CRITICAL
**Time:** 10 minutes

Final checklist BEFORE deployment:

- [ ] All 4 API keys rotated (Gemini, OpenRouter, OpenAI, YouTube)
- [ ] New keys in `.env`
- [ ] `.env` removed from git (if it was there)
- [ ] `.gitignore` includes `.env`
- [ ] `.env.example` is safe (no real secrets)
- [ ] Strong `FLASK_SECRET_KEY` generated and set
- [ ] Application starts without errors
- [ ] Git status shows no `.env`
- [ ] .env file permissions restricted

**Status:** 
- [ ] ✅ PASS - Ready for deployment
- [ ] 🟡 PARTIAL - Some tasks incomplete
- [ ] 🔴 FAIL - Critical issues remain

**Completion:** ____/____/____

---

## NEXT: After Security Phase Complete → Pick Deployment Platform

Once all security tasks are complete, proceed with ONE of these:

1. **Quick Local Test** → Docker Compose
   - Estimated time: 30 minutes
   - Command: `docker-compose up -d`

2. **Heroku Deployment** (Fastest Cloud)
   - Estimated time: 45 minutes
   - Follow: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#option-a-heroku-deployment)

3. **AWS Deployment** (Enterprise)
   - Estimated time: 2 hours
   - Follow: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#option-b-aws-elastic-beanstalk)

4. **Google Cloud Run** (Serverless)
   - Estimated time: 1.5 hours
   - Follow: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#option-c-google-cloud-run)

---

## Summary of Files Created

| File | Purpose | Status |
|------|---------|--------|
| requirements.txt | Python dependencies | ✅ Ready |
| config.py | Environment configuration | ✅ Ready |
| wsgi.py | Production entry point | ✅ Ready |
| setup_db.py | Database initialization | ✅ Ready |
| Procfile | Heroku deployment | ✅ Ready |
| Dockerfile | Docker container | ✅ Ready |
| docker-compose.yml | Local Docker setup | ✅ Ready |
| .env.example | Template (safe) | ✅ Ready |
| .env | Secrets (KEEP SECURE!) | 🔄 Update required |
| DEPLOYMENT_CHECKLIST.md | Full checklist | ✅ Ready |
| DEPLOYMENT_GUIDE.md | Platform guides | ✅ Ready |
| SECURITY_REMEDIATION_GUIDE.md | Security fixes | ✅ Ready |

---

## Sign-Off

**Project:** EduRipple Backend  
**Security Review Completed:** [ ] Yes [ ] No  
**Authorized by:** _________________________  
**Date:** ____/____/____  
**Next Phase:** _________________________  

---

⚠️ **DO NOT DEPLOY UNTIL PHASE 1 & 2 ARE COMPLETE** ⚠️
