# Manual Google Cloud Deployment Guide

This guide walks through deploying Eduripple to Google Cloud Run manually using the GCP Console.

## Prerequisites

- Google Cloud Project: `Eduripple` (ID: `gen-lang-client-0465317991`)
- Billing Account: Active and linked
- APIs Enabled: Cloud Run, Cloud Build, Container Registry, Artifact Registry
- Local machine: Git, Docker (or use Cloud Build)

## Option 1: Deploy Using Cloud Build (No Local Docker Required)

### Step 1: Prepare Your Code

```bash
cd c:\Users\Admin\Desktop\eduripple-backend
git init
git add .
git commit -m "Initial deployment commit"
```

Or if already in git:

```bash
git push origin main  # Push to your repository
```

### Step 2: Create Service Account

Using GCP Console:

1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click "Create Service Account"
3. Name: `eduripple-deploy`
4. Grant roles:
   - Cloud Run Admin
   - Storage Admin
   - Container Registry Service Agent
5. Click "Create and Continue"
6. Create a key (JSON format)
7. Download and save as `gcloud-key.json`

### Step 3: Authenticate Local Machine

```powershell
# Set the service account key
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\Users\Admin\Desktop\eduripple-backend\gcloud-key.json"

# Set project
gcloud config set project gen-lang-client-0465317991

# Authenticate
gcloud auth activate-service-account --key-file=gcloud-key.json
```

### Step 4: Push Code to Cloud Source Repository

```powershell
gcloud source repos create eduripple
git remote add google https://source.developers.google.com/p/gen-lang-client-0465317991/r/eduripple
git push google main
```

### Step 5: Start Cloud Build

Using PowerShell:

```powershell
# Build the Docker image using Cloud Build
gcloud builds submit `
  --config=cloudbuild.yaml `
  --region=us-central1

# Wait for build to complete - check status at:
# https://console.cloud.google.com/cloud-build/builds
```

### Step 6: Deploy to Cloud Run

Using CloudConsole is easier:

1. Go to: https://console.cloud.google.com/run
2. Click "Deploy Container"
3. Select your image from Container Registry (just built)
4. Service name: `eduripple`
5. Region: `us-central1`
6. Authentication: Allow unauthenticated invocations
7. Set environment variables:
   ```
   GEMINI_API_KEY=your_key_here
   FLASK_ENV=production
   SECRET_KEY=random_32_char_string
   DATABASE_URL=postgresql://user:pass@cloudsql-proxy/db
   ```
8. Click "Deploy"

---

## Option 2: Manual Docker Build and Deploy

### Step 1: Install Docker

Download from: https://docker.com/products/docker-desktop

### Step 2: Build Locally

```powershell
cd c:\Users\Admin\Desktop\eduripple-backend

# Build Docker image
docker build -t eduripple:latest .

# Tag for Container Registry
docker tag eduripple:latest gcr.io/gen-lang-client-0465317991/eduripple:latest

# Push to Container Registry
docker push gcr.io/gen-lang-client-0465317991/eduripple:latest
```

### Step 3: Deploy via gcloud

```powershell
gcloud run deploy eduripple `
  --image gcr.io/gen-lang-client-0465317991/eduripple:latest `
  --region us-central1 `
  --platform managed `
  --memory 2Gi `
  --cpu 2 `
  --timeout 3600 `
  --set-env-vars "GEMINI_API_KEY=$env:GEMINI_API_KEY,FLASK_ENV=production" `
  --allow-unauthenticated
```

---

## Step-by-Step Console Alternative (Easiest)

### Using GCP Console Only (No Command Line)

1. **Go to Cloud Run Dashboard**
   - URL: https://console.cloud.google.com/run?project=gen-lang-client-0465317991

2. **Click "Create Service"**
   - Service name: `eduripple`
   - Region: `us-central1`
   - Authentication: `Allow unauthenticated invocations`

3. **Choose how to deploy**
   - Option A: Container image from Container Registry (if you already built)
   - Option B: Source code from Cloud Source Repository
   - Option C: GitHub (if connected)

4. **Set Compute Configuration**
   - Memory: 2 GB
   - CPU: 2 vCPUs
   - Timeout: 3600 seconds

5. **Set Environment Variables**
   - Under "Runtime settings" → "Environment variables"
   - Add all variables from `.env` file

6. **Click "Create"** and wait for deployment

---

## Verification After Deployment

### Test the Service

```powershell
# Get service URL
$serviceUrl = gcloud run services describe eduripple --region us-central1 --format 'value(status.url)'
Write-Host "Service deployed at: $serviceUrl"

# Test health endpoint
curl "$serviceUrl/api/system/health"

# Expected response: {"status":"ok"}
```

### Check Logs

```powershell
gcloud run logs read eduripple --limit 50 --region us-central1
```

### Monitor Performance

Go to: https://console.cloud.google.com/run/detail/us-central1/eduripple/metrics

---

## Networking Setup for Domain

### Add Custom Domain (if using custom domain)

1. Go to Cloud Run service details
2. Click "Manage Custom Domains"
3. Add your domain
4. Follow DNS configuration steps
5. SSL certificate auto-generates (takes ~15 minutes)

---

## Database Configuration

### If Using Cloud SQL

1. Create Cloud SQL instance (PostgreSQL 15):
   - Name: `eduripple-db`
   - Region: `us-central1`
   - Machine type: `db-f1-micro` (dev) or `db-g1-small` (prod)

2. Create database: `eduripple`

3. Create user: `eduripple_app`

4. Get connection string:
   ```
   postgresql://eduripple_app:PASSWORD@CLOUD_SQL_IP:5432/eduripple
   ```

5. Set CONNECTION_NAME in Cloud Run environment:
   ```
   CLOUDSQL_CONNECTION_NAME=<project>:<region>:<instance>
   ```

---

## Rollback if Issues

```powershell
# Get previous revision
gcloud run revisions list --service=eduripple --region=us-central1

# Traffic to specific revision
gcloud run services update-traffic eduripple `
  --to-revisions REVISION_NAME=100 `
  --region us-central1
```

---

## Environment File Template

Create `.env` in project root:

```env
# API Keys
GEMINI_API_KEY=your_key_here

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=generate_random_32_char_string_here
DEBUG=False

# Database
DATABASE_URL=postgresql://user:pass@host:5432/eduripple
SQLALCHEMY_TRACK_MODIFICATIONS=False

# Security
SESSION_COOKIE_SECURE=False
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_HTTPONLY=True

# Cloud SQL (if using Cloud SQL)
CLOUDSQL_CONNECTION_NAME=project:region:instance

# App Configuration
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=52428800
```

---

## Cost Estimates

**Monthly cost for typical usage:**

- **Cloud Run**: $0.00 (Always Free Tier includes 2M requests/month)
- **Cloud SQL**: ~$45/month (db-f1-micro)
- **Storage**: ~$5/month (if using Cloud Storage)
- **APIs**: Free (most GCP APIs free tier is generous)

**Total estimated**: $50-60/month for production-grade hosting

---

## Support & Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check logs, verify SECRET_KEY set, check memory/timeout |
| 403 Forbidden | Verify service account has permissions, check CORS |
| Timeout errors | Increase timeout (max 3600s), optimize code |
| Out of memory | Increase memory allocation to 4GB |
| Database connection fails | Verify connection string, check Cloud SQL proxy |

### Get Help

1. Check logs: `gcloud run logs read eduripple`
2. Google Cloud docs: https://cloud.google.com/run/docs
3. Flask deployment: https://flask.palletsprojects.com/en/3.0.x/deploying/

---

## Next Steps After Deployment

1. ✅ Test all endpoints
2. ✅ Configure custom domain
3. ✅ Set up monitoring & alerts
4. ✅ Enable logging
5. ✅ Configure backup strategy for database
6. ✅ Set up CI/CD for future deployments

---

Generated: $(date)
Project: Eduripple
Environment: Production
