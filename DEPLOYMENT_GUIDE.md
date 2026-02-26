# Deployment Guide - EduRipple Backend

## Overview
This guide provides step-by-step instructions for deploying the EduRipple backend to production.

## Prerequisites
- PostgreSQL database (production)
- Python 3.8+
- Redis (optional, for caching)
- Hosting platform account (Heroku, AWS, GCP, etc.)
- SSL certificate domain configured
- All API keys configured

## Quick Start Deployment

### 1. Prepare Environment
```bash
# Clone repository
git clone <repository-url>
cd eduripple-backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environments
```bash
# Copy template to actual .env (DO NOT COMMIT)
cp .env.example .env

# Edit .env with production values
# - Set FLASK_ENV=production
# - Add all API keys
# - Configure database URL
# - Set strong FLASK_SECRET_KEY
```

### 3. Initialize Database
```bash
# Initialize fresh databases
python setup_db.py

# If migrating from SQLite to PostgreSQL:
python setup_db.py --migrate-from-sqlite --backup
```

### 4. Run Tests
```bash
# Run all tests
pytest tests/ -v

# Or run specific tests
python test_admin_api.py
python test_ai_initialization.py
```

### 5. Deploy to Production

#### Option A: Heroku Deployment
```bash
# Install Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:standard-0

# Set environment variables
heroku config:set FLASK_ENV=production
heroku config:set FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
heroku config:set GEMINI_API_KEY=your-key
heroku config:set OPENROUTER_API_KEY=your-key
heroku config:set OPENAI_API_KEY=your-key
heroku config:set YOUTUBE_API_KEY=your-key

# Deploy
git push heroku main

# Initialize database
heroku run python setup_db.py

# View logs
heroku logs --tail
```

#### Option B: AWS Elastic Beanstalk
```bash
# Install EB CLI
# https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3-install.html

# Initialize EB application
eb init -p python-3.11 eduripple --region us-east-1

# Create environment
eb create production --instance-type t3.medium --database --db-engine postgres

# Configure environment variables
# Via: EB Console > Configuration > Updates and deployments > Environment properties

# Deploy
eb deploy

# Create database
eb ssh
python setup_db.py

# View logs
eb logs
```

#### Option C: Google Cloud Run
```bash
# Build Docker image
gcloud builds submit --tag gcr.io/PROJECT_ID/eduripple

# Deploy to Cloud Run
gcloud run deploy eduripple \
  --image gcr.io/PROJECT_ID/eduripple \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --set-env-vars FLASK_ENV=production,FLASK_SECRET_KEY=...

# Set up Cloud SQL Proxy for PostgreSQL
# https://cloud.google.com/sql/docs/postgres/cloud-sql-proxy
```

#### Option D: DigitalOcean App Platform
```bash
# Deploy via DigitalOcean App Platform
# 1. Push code to GitHub
# 2. Connect GitHub repository to DigitalOcean
# 3. Configure build & run commands:
#    - Build: pip install -r requirements.txt
#    - Run: gunicorn -w 4 -b 0.0.0.0:8080 wsgi:app

# 4. Set environment variables in App Platform dashboard
# 5. Attach PostgreSQL database
# 6. Deploy
```

### 6. Verify Deployment
```bash
# Check health endpoint
curl https://your-app-domain.com/api/system/health

# Expected response:
# {
#   "status": "healthy",
#   "services": {
#     "database": "operational",
#     "cache": "operational",
#     "ai_service": "gemini"
#   }
# }

# Check recent logs
# Platform-specific: heroku logs, eb logs, gcloud logging, etc.

# Test critical endpoints
curl -X POST https://your-app-domain.com/api/gemini/activities \
  -H "Content-Type: application/json" \
  -d '{"topic": "test", "grade": "10", "subject": "Science"}'
```

## Database Migration Steps

### From SQLite to PostgreSQL
1. **Backup existing data**
   ```bash
   python setup_db.py --backup
   ```

2. **Set up PostgreSQL database**
   - Create database on hosting platform
   - Note connection string

3. **Update DATABASE_URL in .env**
   ```
   DATABASE_URL=postgresql://user:password@host:port/dbname
   ```

4. **Run migration**
   ```bash
   python setup_db.py --migrate-from-sqlite
   ```

5. **Verify migration**
   ```bash
   # Check data in PostgreSQL
   psql $DATABASE_URL
   \dt  # List tables
   SELECT COUNT(*) FROM teachers;
   ```

## Environment Variables

### Required for Production
```
FLASK_ENV=production
FLASK_SECRET_KEY=<strong-random-32-char-key>
DATABASE_URL=postgresql://user:password@host:port/db
GEMINI_API_KEY=<your-key>
OPENROUTER_API_KEY=<your-key>
OPENAI_API_KEY=<your-key>
YOUTUBE_API_KEY=<your-key>
```

### Optional
```
CACHE_TYPE=redis
REDIS_URL=redis://user:password@host:port/0
LOG_LEVEL=INFO
ADMIN_EMAIL=admin@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=app-password
```

## Monitoring & Maintenance

### Set Up Monitoring
1. **Application Performance**
   - New Relic, DataDog, or similar
   - Monitor CPU, memory, response times

2. **Error Tracking**
   - Integrate Sentry
   - Monitor API errors

3. **Database Monitoring**
   - Monitor query performance
   - Set up backup alerts
   - Monitor disk space

### Regular Maintenance
```bash
# Update dependencies (monthly)
pip list --outdated
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --upgrade

# Database maintenance (weekly)
VACUUM;  # SQLite
VACUUM ANALYZE;  # PostgreSQL

# Check health
curl https://your-app/api/system/health

# Rotate API keys (quarterly)
# Follow API provider instructions
```

## Troubleshooting

### Issue: Database Connection Error
```
Error: psycopg2.OperationalError: FATAL:  password authentication failed
```

**Fix:**
- Verify DATABASE_URL is correct
- Check username/password
- Ensure database user has proper privileges
- Test connection: `psql $DATABASE_URL`

### Issue: API Keys Not Working
**Fix:**
- Verify keys are set in environment variables
- Check key expiration dates
- Test with simple API call
- Check rate limits not exceeded

### Issue: High Memory Usage
**Fix:**
- Check active connections: `SELECT * FROM pg_stat_activity;`
- Increase database pool connection timeout
- Implement query caching
- Scale up instance size

### Issue: Slow Response Times
**Fix:**
- Check database query performance
- Enable Redis caching
- Optimize slow queries
- Check AI service response times
- Review rate limiting configuration

## Rollback Procedure

### If deployment fails:
```bash
# Heroku
heroku releases
heroku rollback v123

# EB
eb abort

# Manual rollback
git revert <commit-hash>
git push
# Re-deploy
```

### Data Rollback
```bash
# Restore from backup
# Platform-specific restore procedures

# Or restore manually
psql $DATABASE_URL < backup.sql
```

## Security Checklist

- [ ] All secrets removed from repository
- [ ] .env file listed in .gitignore
- [ ] HTTPS/SSL enabled
- [ ] CORS origins restricted
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] CSRF protection enabled
- [ ] SQL injection protections in place
- [ ] XSS protections enabled
- [ ] API keys rotated

## Support & Documentation

- API Documentation: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- Features Documentation: [FEATURES_DOCUMENTATION.md](FEATURES_DOCUMENTATION.md)
- Implementation Summary: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- Deployment Checklist: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

## Contact

For deployment issues:
1. Check this guide first
2. Review platform-specific documentation
3. Check application logs
4. Contact DevOps team
