# GOOGLE CLOUD DEPLOYMENT GUIDE

## Overview
This guide walks you through migrating EduRipple from Render to Google Cloud Platform (GCP). You have two deployment options:

1. **Cloud Run** (Recommended) - Serverless, auto-scaling, pay-per-use
2. **App Engine** - Fully managed, simpler setup, built-in scaling

---

## Prerequisites

Before you start, ensure you have:

1. **Google Cloud Project** created
2. **gcloud CLI** installed locally
   ```bash
   # Install: https://cloud.google.com/sdk/docs/install
   # Verify:
   gcloud --version
   ```

3. **GitHub repository** (for automated deployments)
4. **API Keys**: Keep these ready
   - `FLASK_SECRET_KEY` (generate a secure key)
   - `GEMINI_API_KEY`
   - `OPENROUTER_API_KEY`
   - `ELEVENLABS_API_KEY`
   - Other service keys as needed

---

## OPTION A: Deploy to Cloud Run (Recommended)

### Step 1: Setup Google Cloud Project

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable container.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### Step 2: Build and Push Docker Image

```bash
# Set your region
export REGION="us-central1"

# Build the Docker image
gcloud builds submit --tag gcr.io/$PROJECT_ID/eduripple-backend:latest

# OR build locally and push
docker build -t gcr.io/$PROJECT_ID/eduripple-backend:latest .
docker push gcr.io/$PROJECT_ID/eduripple-backend:latest
```

### Step 3: Deploy to Cloud Run

```bash
gcloud run deploy eduripple-backend \
  --image gcr.io/$PROJECT_ID/eduripple-backend:latest \
  --region $REGION \
  --platform managed \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --allow-unauthenticated \
  --set-env-vars=FLASK_ENV=production,PORT=8080 \
  --set-cloudsql-instances=$PROJECT_ID:$REGION:eduripple-db \
  --service-account=eduripple-service@$PROJECT_ID.iam.gserviceaccount.com
```

### Step 4: Set Environment Variables

```bash
# Get your Cloud Run service URL
SERVICE_URL=$(gcloud run services describe eduripple-backend \
  --region $REGION \
  --format 'value(status.url)')

echo "Your app is available at: $SERVICE_URL"

# Update environment variables via Cloud Console or CLI:
gcloud run services update eduripple-backend \
  --region $REGION \
  --update-env-vars=FLASK_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))'),GEMINI_API_KEY=your_key_here,OPENROUTER_API_KEY=your_key_here
```

### Step 5: Setup Automatic Deployments (Optional)

Connect your GitHub repository to Cloud Build for automated deployments:

```bash
# Create a build trigger via Cloud Console:
# 1. Go to Cloud Build > Triggers
# 2. Create New Trigger
# 3. Connect your GitHub repository
# 4. Select "cloudbuild.yaml" as the build config file
# 5. Save and activate
```

---

## OPTION B: Deploy to App Engine

### Step 1: Configure App Engine

Ensure you have `app.yaml` in your project root (already created).

### Step 2: Setup App Engine

```bash
# Initialize App Engine
gcloud app create --region=$REGION

# Enable required APIs
gcloud services enable appengine.googleapis.com
gcloud services enable cloud.googleapis.com
gcloud services enable compute.googleapis.com
```

### Step 3: Deploy Application

```bash
# Deploy from your project root
gcloud app deploy

# The deployment will:
# - Build your Docker image
# - Upload to Google Container Registry
# - Deploy to App Engine
# - Automatically handle scaling
```

### Step 4: Set Environment Variables

```bash
# Via gcloud CLI:
gcloud app deploy --set-env-vars FLASK_SECRET_KEY=your_key,GEMINI_API_KEY=your_key

# Or update via Cloud Console:
# App Engine > Settings > Environment variables
```

---

## Configure Database (Cloud SQL - Optional)

For production use, migrate from SQLite to Cloud SQL PostgreSQL:

### Step 1: Create Cloud SQL Instance

```bash
gcloud sql instances create eduripple-db \
  --database-version POSTGRES_15 \
  --tier db-f1-micro \
  --region $REGION \
  --backup \
  --backup-start-time 03:00

# Create database
gcloud sql databases create eduripple \
  --instance=eduripple-db

# Create user
gcloud sql users create eduripple-user \
  --instance=eduripple-db \
  --password=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
```

### Step 2: Update Connection String

```bash
# Get Cloud SQL connection name
gcloud sql instances describe eduripple-db --format='value(connectionName)'

# Set DATABASE_URL environment variable
gcloud run services update eduripple-backend \
  --update-env-vars DATABASE_URL="postgresql://user:password@/eduripple?host=/cloudsql/PROJECT:REGION:INSTANCE"
```

### Step 3: Configure Connection

In your code (main.py.py), the DATABASE_URL is already used if set:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///curriculum.db")
```

---

## Storage Configuration (Google Cloud Storage - Optional)

For persistent file storage (replacing local `/data` directory):

### Step 1: Create Storage Bucket

```bash
gsutil mb -p $PROJECT_ID -l $REGION gs://$PROJECT_ID-eduripple-files/
```

### Step 2: Update Application Code

Create a storage helper (e.g., `gcs_storage.py`):

```python
from google.cloud import storage

def upload_to_gcs(local_path, bucket_name, destination_blob_name):
    """Upload file to Google Cloud Storage"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_path)
    return blob.public_url

def download_from_gcs(bucket_name, source_blob_name, local_path):
    """Download file from Google Cloud Storage"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(local_path)
```

---

## Monitoring & Logging

### View Logs

```bash
# Cloud Run logs
gcloud beta run logs read eduripple-backend --region $REGION --limit 50

# App Engine logs
gcloud app logs read

# Or use Cloud Logging in Console
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=eduripple-backend" \
  --limit 50 --format json
```

### Setup Alerts

```bash
# View error rate
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="eduripple-backend"'

# Set up error notification in Cloud Console
# Monitoring > Alerting Policies > Create Policy
```

### Check Health

```bash
# Cloud Run
curl $(gcloud run services describe eduripple-backend --region $REGION --format 'value(status.url)')/api/system/health

# App Engine
curl https://your-app-id.appspot.com/api/system/health
```

---

## Scaling Configuration

### Cloud Run Automatic Scaling

Settings are configured in cloudbuild.yaml. To adjust:

```bash
gcloud run services update eduripple-backend \
  --region $REGION \
  --min-instances 1 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 80
```

### App Engine Automatic Scaling

Configured in app.yaml. To adjust:

```yaml
automatic_scaling:
  min_instances: 2
  max_instances: 20
  min_pending_latency: 30ms
  max_pending_latency: 60ms
```

---

## Comparison: Render vs Google Cloud

| Feature | Render | Cloud Run | App Engine |
|---------|--------|-----------|-----------|
| **Pricing** | Free tier (limited) | Pay-per-use | Monthly fixed + usage |
| **Startup** | Quick | Cold starts ~1-2s | Warm all time |
| **Scaling** | Manual | Automatic | Automatic |
| **Databases** | PostgreSQL add-on | Cloud SQL | Cloud SQL |
| **Storage** | File system | Cloud Storage | Cloud Storage |
| **Maintenance** | Minimal | Minimal | Minimal |
| **Cost at scale** | Higher | Lower | Medium |
| **Best for** | Simple hobbyist | Production serverless | Medium-scale apps |

---

## Troubleshooting

### Cloud Run: "Container failed to start"

```bash
# Check logs
gcloud beta run logs read eduripple-backend --region $REGION --limit 100

# Possible causes:
# - Missing environment variables
# - Python dependencies not installed (check requirements.txt)
# - Port not set to 8080 (Cloud Run requires this)
```

### Cloud Run: "Permission denied" errors

```bash
# Grant service account permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:eduripple-service@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/storage.admin
```

### Deployment Fails

```bash
# Check gcloud quotas
gcloud compute project-info describe --project=$PROJECT_ID

# View build logs
gcloud builds log

# Rebuild with debug
gcloud builds submit --config=cloudbuild.yaml --substitutions=_DEBUG=true
```

---

## Final Steps

1. **Test your application**
   ```bash
   curl https://your-service-url/api/system/health
   ```

2. **Configure custom domain**
   - Cloud Run: Run > Services > Select service > Details tab > Set up custom domain
   - App Engine: Settings > Custom domains

3. **Setup SSL certificate** (automatic with custom domain)

4. **Monitor costs**
   ```bash
   gcloud billing budgets create \
     --billing-account=BILLING_ACCOUNT_ID \
     --display-name="EduRipple Budget" \
     --budget-amount=50
   ```

5. **Enable VPC for private networking** (if needed)

---

## Migration Checklist

- [ ] Google Cloud project created
- [ ] gcloud CLI installed and configured
- [ ] Docker image builds successfully locally
- [ ] Environment variables configured in GCP
- [ ] Database migrated (if using Cloud SQL)
- [ ] Static files configured
- [ ] Custom domain configured
- [ ] SSL certificate configured
- [ ] Logs and monitoring setup
- [ ] Backups configured
- [ ] Team members added with appropriate permissions
- [ ] DNS pointing to new service
- [ ] Render service deactivated

---

## Getting Help

- **Google Cloud Documentation**: https://cloud.google.com/docs
- **Cloud Run**: https://cloud.google.com/run/docs
- **App Engine**: https://cloud.google.com/appengine/docs
- **Cloud Logging**: https://cloud.google.com/logging/docs
- **Cloud Build**: https://cloud.google.com/build/docs
