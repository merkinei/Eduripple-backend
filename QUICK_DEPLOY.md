# Quick Deployment Guide - Google Cloud Run

## Prerequisites ✅ COMPLETE
- [x] Google Cloud SDK installed
- [x] Authenticated as kibetmerkinei@gmail.com
- [x] Project: Eduripple (gen-lang-client-0465317991)
- [x] Billing enabled
- [x] APIs enabled (Cloud Run, Cloud Build, Container Registry)

## Step 1: Configure Environment Variables

Create `.env` file with your API keys:

```powershell
# Copy template
copy .env.example .env

# Edit .env and add:
FLASK_ENV=production
FLASK_SECRET_KEY=<generated-key>
GEMINI_API_KEY=<your-key>
OPENROUTER_API_KEY=<your-key>
ELEVENLABS_API_KEY=<your-key>
CORS_ORIGINS=https://yourdomain.com
```

Generate FLASK_SECRET_KEY:
```powershell
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

## Step 2: Deploy to Cloud Run

```powershell
# Run deployment script (Cloud Build will build Docker image remotely)
.\deploy-to-gcloud.ps1 -DeploymentType 'cloud-run' -Region 'us-central1'
```

The script will:
1. Build Docker image in Google Cloud Build ☁️
2. Push to Container Registry
3. Deploy to Cloud Run
4. Show you the service URL

## Step 3: Set Environment Variables in GCP Console

After deployment completes:

1. Go to https://console.cloud.google.com/run
2. Click on `eduripple-backend` service
3. Click "Edit & Deploy New Revision"
4. Scroll to "Environment variables"
5. Add:
   - `FLASK_SECRET_KEY=<your-key>`
   - `GEMINI_API_KEY=<your-key>`
   - `OPENROUTER_API_KEY=<your-key>`
   - `ELEVENLABS_API_KEY=<your-key>`
   - `FLASK_ENV=production`
6. Click "Deploy"

## Step 4: Test the Service

```powershell
# Test health endpoint (replace URL with your Cloud Run URL)
curl https://eduripple-backend-xxxxx.run.app/api/system/health

# Should return: {"status": "ok", "timestamp": "..."}
```

## Troubleshooting

**API Keys Missing?**
- Service will start but AI features won't work
- Add keys via GCP Console as shown in Step 3

**Build Failed?**
- Check Cloud Build logs: https://console.cloud.google.com/cloud-build
- Common issue: Requirements missing (fixed in requirements.txt)

**Deployment Failed?**
- View logs: `gcloud run logs read eduripple-backend --limit 50`
- Check if port is correct (should be 8080)

## Scaling & Monitoring

View metrics:
```powershell
& "C:\Users\Admin\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" run services describe eduripple-backend --region us-central1
```

Scale settings in GCP Console:
- Min instances: 1 (or 0 for cost savings)
- Max instances: 100
- Memory: 2Gi
- CPU: 2 cores
- Timeout: 3600 seconds

## Database Setup (Optional)

For production with persistent data, upgrade to Cloud SQL PostgreSQL:
- Create Cloud SQL instance
- Update `DATABASE_URL` environment variable
- See GOOGLE_CLOUD_DEPLOYMENT.md for details

## Next Steps

1. Add your API keys to `.env`
2. Run `.\deploy-to-gcloud.ps1 -DeploymentType 'cloud-run' -Region 'us-central1'`
3. Set environment variables in GCP Console
4. Test the service
5. Monitor logs via GCP Console or `gcloud run logs`

**Your EduRipple backend will be live in minutes!** 🚀
