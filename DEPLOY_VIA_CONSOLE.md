# Eduripple: Deploy to Google Cloud Run in 5 Minutes (No CLI)

This is the fastest way to deploy using only the Google Cloud Console web interface.

## Step 1: Prepare Your .env File

Create a file named `.env` in your project root with these values:

```env
GEMINI_API_KEY=sk-...your-key...
FLASK_ENV=production
SECRET_KEY=generate-a-random-32-character-string
DEBUG=False
```

**Keep this file locally - do NOT commit to git**

## Step 2: Upload to Google Cloud Storage

1. Go to: https://console.cloud.google.com/storage/browser?project=gen-lang-client-0465317991

2. Click **"Create Bucket"**
   - Name: `eduripple-source-code`
   - Location: `US (Multiple regions)`
   - Click **Create**

3. Upload your entire project:
   - Click on the bucket
   - Click **"Upload Folder"**
   - Select your `c:\Users\Admin\Desktop\eduripple-backend` folder
   - Click **Upload**

## Step 3: Enable Cloud Run API (If Not Done)

1. Go to: https://console.cloud.google.com/run?project=gen-lang-client-0465317991

2. If prompted, click **"Enable Cloud Run API"**

## Step 4: Deploy Using Console

1. In Cloud Run page (from step 3), click **"Create Service"**

2. **Configure container:**
   - Select **"Deploy one-off container"**
   - Container image: Choose **"Container Registry"** or paste image path
   - For first deploy, select **"Edit and create a new service"**

3. **Fill in service details:**
   - Service name: `eduripple`
   - Region: `us-central1`
   - Uncheck **"Require authentication"** (or use JWT if needed)

4. **Container configuration:**
   - Click **"Container"** section
   - Memory: `2 GB`
   - CPU: `2`
   - Timeout: `Max (3600 seconds)`
   - Options:
     ✓ CPU is only allocated during request processing
     ✓ Ingress: Internal and external traffic

5. **Set Environment Variables:**
   - Expand **"Runtime settings"**
   - Under **"Environment variables"**, add:
   
   | Key | Value |
   |-----|-------|
   | GEMINI_API_KEY | sk-...your-key... |
   | FLASK_ENV | production |
   | SECRET_KEY | (32 random chars) |
   | DEBUG | False |

6. **Click "Create"** and wait for deployment (~2-5 minutes)

## Step 5: Test Your Deployment

Once deployed:

1. You'll see a service URL like: `https://eduripple-xxxxx.run.app`

2. Click the URL to open in browser

3. Test it works:
   - `/` → Should show home page or API response
   - `/api/system/health` → Should return `{"status":"ok"}`

## Step 6: Set Custom Domain (Optional)

To use your own domain (like `eduripple.com`):

1. In Cloud Run service page, click **"Manage Custom Domains"**

2. Click **"Add Mapping"**
   - Namespace: `example.com` (your domain)
   - Service: `euripple`
   - Click **"Add"**

3. Google will generate DNS records - add them to your domain registrar

4. SSL certificate auto-generates (10-15 minutes)

---

## Environment Variables Reference

| Variable | Value | Notes |
|----------|-------|-------|
| `GEMINI_API_KEY` | Your API key | Required for AI features |
| `FLASK_ENV` | `production` | Must be `production` for deployed |
| `SECRET_KEY` | Random string | Use `python -c "import secrets; print(secrets.token_hex(16))"` |
| `DEBUG` | `False` | Never `True` in production |
| `DATABASE_URL` | (optional) | If using PostgreSQL instead of SQLite |
| `SESSION_COOKIE_SECURE` | `False` | For proxy-friendly cookies |

## Monitoring Your Deployment

**View Logs:**
- Go to Cloud Run service page
- Click **"Logs"** tab
- See real-time logs of requests and errors

**View Metrics:**
- Click **"Metrics"** tab
- See CPU, memory, request count, latency

**View Revisions:**
- Click **"Revisions"** tab
- See all previous deployments
- Can roll back if needed

---

## Troubleshooting

### "502 Bad Gateway" Error

**Cause:** Application crashed or misconfigured

**Fix:**
1. Check logs for errors
2. Verify all environment variables are set
3. Increase memory to 4GB
4. Check if `main.py` is correctly importing Flask

### "503 Service Unavailable"

**Cause:** Service is starting up (first time) or out of memory

**Fix:**
1. Wait a minute, service still starting
2. If persists, increase memory allocation
3. Check logs for out-of-memory errors

### Requests are Slow

**Cause:** Cold start, low memory, or inefficient code

**Fix:**
1. Increase memory (2GB → 4GB)
2. Increase CPU (2 → 4)
3. Use **"Always on CPU"** if doing background work

### Database Connection Fails

**Cause:** No database configured

**Fix:**
1. If using SQLite: This is fine, SQLite included
2. If need PostgreSQL: Create Cloud SQL instance and set `DATABASE_URL`

---

## Next Steps

After deployment works:

1. **[OPTIONAL] Set up continuous deployment:**
   - Connect GitHub repo to Cloud Run
   - Auto-deploy on every git push
   - https://console.cloud.google.com/run

2. **[OPTIONAL] Set up monitoring:**
   - Create alerts for errors
   - Monitor uptime
   - https://console.cloud.google.com/monitoring

3. **[OPTIONAL] Add custom domain:**
   - Buy domain from GoDaddy, Route53, etc.
   - Add DNS records from step 6 above
   - Google handles SSL automatically

4. **[OPTIONAL] Scale settings:**
   - Auto-scaling: 1-100 instances (default)
   - Max requests per instance: 80 (default)
   - CPU throttling: Yes (default, saves cost)

---

## Cost

**Free Tier Includes:**
- 2,000,000 requests/month (Cloud Run)
- Most APIs free
- First $300 free credit

**Typical monthly cost:** $5-50 (very cheap for production)

---

## Get Help

- **Google Cloud Status:** https://status.cloud.google.com
- **Cloud Run Docs:** https://cloud.google.com/run/docs
- **Support:** Open ticket in GCP Console → Support

---

## Quick Reference URLs

| What | URL |
|------|-----|
| Cloud Run Dashboard | https://console.cloud.google.com/run |
| Service Details | https://console.cloud.google.com/run/detail/us-central1/eduripple |
| Logs | https://console.cloud.google.com/logs |
| Metrics | https://console.cloud.google.com/monitoring |
| Billing | https://console.cloud.google.com/billing |
| IAM | https://console.cloud.google.com/iam-admin |

---

**Status:** ✅ Ready to deploy using Google Cloud Console
**Project:** Eduripple  
**Region:** us-central1
**Estimated deployment time:** 2-5 minutes
