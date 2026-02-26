# EduRipple Deployment Checklist

## Pre-Deployment Phase

### 1. Environment & Secrets Management
- [ ] Remove API keys from `.env` file (already checked in)
- [ ] Create `.env.example` with template values (✅ DONE)
- [ ] Configure `.gitignore` to exclude `.env` (⚠️ NEEDS UPDATE)
- [ ] Set up secure secret management:
  - [ ] AWS Secrets Manager
  - [ ] Google Cloud Secret Manager
  - [ ] HashiCorp Vault
  - [ ] Or: Heroku Config Vars / Render Environment Variables
- [ ] Rotate all exposed API keys:
  - [ ] Gemini API Key
  - [ ] OpenRouter API Key
  - [ ] OpenAI API Key
  - [ ] YouTube API Key

### 2. Database Migration
- [ ] Migrate from SQLite to PostgreSQL:
  - [ ] Set up PostgreSQL instance (AWS RDS, Google Cloud SQL, Heroku Postgres)
  - [ ] Install `psycopg2-binary` (✅ ALREADY IN requirements.txt)
  - [ ] Create migration scripts
  - [ ] Update `curriculum_db.py` to use PostgreSQL
  - [ ] Update `db_utils.py` for PostgreSQL connection pooling
  - [ ] Test backup/restore with PostgreSQL
- [ ] Configure database backups:
  - [ ] Set up daily automated backups
  - [ ] Test restore procedures
  - [ ] Store backups in cloud storage (AWS S3, Google Cloud Storage)
- [ ] Update connection pooling for PostgreSQL

### 3. Application Configuration
- [ ] Create `config.py` with environment-based configs (✅ DONE)
- [ ] Update `main.py.py` to use config factory
- [ ] Configure separate dev/test/prod environments
- [ ] Set `FLASK_SECRET_KEY` to a strong random value
- [ ] Disable Flask debugger in production
- [ ] Enable HTTPS/SSL:
  - [ ] Obtain SSL certificate (Let's Encrypt, AWS Certificate Manager)
  - [ ] Configure HTTPS redirect
  - [ ] Set secure cookie flags

### 4. Dependency Management
- [ ] Generate `requirements.txt` (✅ DONE)
- [ ] Pin all versions for reproducibility
- [ ] Test requirements on clean environment
- [ ] Remove development-only dependencies
- [ ] Add production dependencies:
  - [ ] `gunicorn` (✅ ALREADY ADDED)
  - [ ] `psycopg2-binary` for PostgreSQL (✅ ALREADY ADDED)
  - [ ] `redis` for caching/sessions
  - [ ] `celery` for async tasks (optional)

### 5. Deployment Configuration
- [ ] Create `Procfile` for Heroku/similar (✅ DONE)
- [ ] Create `wsgi.py` entry point for gunicorn
- [ ] Create deployment scripts:
  - [ ] `setup_db.py` - database initialization
  - [ ] `migrate_db.py` - migration from SQLite to PostgreSQL
  - [ ] `seed_data.py` - initial data loading
- [ ] Create Docker setup (optional):
  - [ ] `Dockerfile`
  - [ ] `docker-compose.yml`

### 6. Logging & Monitoring
- [ ] Set up centralized logging:
  - [ ] Move logs from local files to cloud service
  - [ ] Integrate with Datadog, ELK Stack, or Splunk
  - [ ] Configure log levels per environment
- [ ] Set up error tracking:
  - [ ] Integrate Sentry
  - [ ] Configure error alerts
  - [ ] Set up PagerDuty alerts for critical errors
- [ ] Enable performance monitoring:
  - [ ] New Relic
  - [ ] DataDog APM
  - [ ] Google Cloud Trace

### 7. File Storage
- [ ] Migrate file uploads from local storage to cloud:
  - [ ] AWS S3
  - [ ] Google Cloud Storage
  - [ ] Azure Blob Storage
  - [ ] Cloudinary (for images)
- [ ] Configure CDN for static assets
- [ ] Set up backup strategy for uploaded files

### 8. Security Hardening
- [ ] Update security headers:
  - [ ] Content-Security-Policy
  - [ ] X-Frame-Options
  - [ ] X-Content-Type-Options
  - [ ] Strict-Transport-Security (HSTS)
- [ ] Configure CORS properly:
  - [ ] Restrict allowed origins
  - [ ] Remove debugging origins
- [ ] Enable rate limiting for production (already configured)
- [ ] Set up CSRF protection
- [ ] Implement authentication hardening:
  - [ ] Multi-factor authentication (optional)
  - [ ] Password complexity requirements (✅ ALREADY DONE)
  - [ ] Session timeout configuration
- [ ] Regular security audits
- [ ] Implement WAF rules (if using AWS/similar)

### 9. Performance Optimization
- [ ] Set up Redis for caching:
  - [ ] Cache API responses
  - [ ] Cache database queries
  - [ ] Session storage
- [ ] Enable gzip compression
- [ ] Minify CSS/JavaScript
- [ ] Optimize database queries
- [ ] Configure connection pooling (✅ ALREADY DONE)
- [ ] Set up CDN for static content

### 10. Testing
- [ ] Run full test suite
- [ ] Load testing:
  - [ ] Apache JMeter
  - [ ] Locust
  - [ ] K6
- [ ] Security testing:
  - [ ] OWASP Top 10 vulnerability check
  - [ ] SQL injection testing
  - [ ] XSS testing
- [ ] Integration testing with production-like environment
- [ ] User acceptance testing (UAT)

---

## Deployment Phase

### 11. Infrastructure Setup
- [ ] Choose hosting platform:
  - [ ] Heroku
  - [ ] AWS (EC2, ECS, Elastic Beanstalk)
  - [ ] Google Cloud Platform (App Engine, Cloud Run)
  - [ ] Azure (App Service)
  - [ ] DigitalOcean
  - [ ] Render
- [ ] Configure domain and DNS
- [ ] Set up CI/CD pipeline:
  - [ ] GitHub Actions
  - [ ] GitLab CI
  - [ ] Jenkins
  - [ ] CircleCI

### 12. Data Migration
- [ ] Backup production data before migration
- [ ] Migrate curriculum data from SQLite to PostgreSQL
- [ ] Migrate teachers database
- [ ] Verify data integrity
- [ ] Test all functionality with production data

### 13. Deployment
- [ ] Set environment variables on production
- [ ] Deploy application:
  - [ ] Deploy to staging first
  - [ ] Run smoke tests on staging
  - [ ] Deploy to production
- [ ] Verify all endpoints are working
- [ ] Check health endpoint: `/api/system/health`
- [ ] Verify AI services are available
- [ ] Test critical user flows

### 14. Monitoring & Alerts
- [ ] Set up monitoring dashboards
- [ ] Configure alerts for:
  - [ ] CPU > 80%
  - [ ] Memory > 85%
  - [ ] Database connection issues
  - [ ] API errors > threshold
  - [ ] Response time > threshold
  - [ ] Disk space > 90%
- [ ] Set up backup alerts
- [ ] Configure on-call schedules

---

## Post-Deployment Phase

### 15. Verification
- [ ] Verify all health checks pass
- [ ] Monitor error rates (should be < 0.1%)
- [ ] Monitor response times
- [ ] Verify background tasks are running
- [ ] Check database backups are working
- [ ] Verify API key rotation monitoring
- [ ] Test rate limiting in production

### 16. Documentation
- [ ] Document deployment architecture
- [ ] Document rollback procedures
- [ ] Create runbooks for common issues
- [ ] Document incident response procedures
- [ ] Update API documentation if needed

### 17. Maintenance Planning
- [ ] Schedule regular security updates
- [ ] Plan database maintenance windows
- [ ] Set up dependency update schedule (Dependabot)
- [ ] Schedule performance review
- [ ] Plan capacity planning reviews

---

## Environment-Specific Checklists

### Development
- [x] Setup virtual environment
- [x] Install dependencies
- [x] Configure `.env` for development
- [x] Initialize databases
- [x] Run tests

### Staging
- [ ] Deploy from main branch
- [ ] Use production-like database (PostgreSQL)
- [ ] Use production-like configurations
- [ ] Run full test suite
- [ ] Performance test
- [ ] Security test
- [ ] User acceptance testing

### Production
- [ ] Use strong `FLASK_SECRET_KEY`
- [ ] Enable HTTPS/SSL
- [ ] Use PostgreSQL
- [ ] Enable monitoring
- [ ] Enable error tracking
- [ ] Use centralized logging
- [ ] Use cloud file storage
- [ ] Configure automated backups
- [ ] Set up WAF if applicable
- [ ] Enable rate limiting
- [ ] Configure CDN

---

## Critical Files to Verify

- [x] `.env` - Contains secrets (⚠️ NEEDS REMEDIATION)
- [x] `.gitignore` - Should exclude `.env` (⚠️ NEEDS UPDATE)
- [x] `requirements.txt` - All dependencies listed (✅ DONE)
- [x] `config.py` - Environment-based configuration (✅ DONE)
- [x] `Procfile` - Deployment instructions (✅ DONE)
- [ ] `.env.example` - Template without secrets (✅ DONE)
- [ ] `wsgi.py` - WSGI entry point (⚠️ NEEDS CREATION)
- [ ] `setup_db.py` - Database initialization (⚠️ NEEDS CREATION)
- [ ] Database migration scripts (⚠️ NEEDS CREATION)

---

## Deployment to Specific Platforms

### Heroku
```bash
heroku create <app-name>
heroku config:set FLASK_ENV=production
heroku config:set FLASK_SECRET_KEY=<strong-random-key>
heroku addons:create heroku-postgresql:standard-0
git push heroku main
heroku logs --tail
```

### Google Cloud Run
```bash
gcloud run deploy eduripple --source . --platform managed --region us-central1
# Set environment variables via Cloud Run console
```

### AWS Elastic Beanstalk
```bash
eb create educaton-prod
eb setenv FLASK_ENV=production
eb deploy
eb logs
```

---

## Rollback Plan
- [ ] Keep previous version deployed in parallel
- [ ] Quick rollback command documented
- [ ] Data rollback procedure
- [ ] Communication procedure

---

## Sign-Off
- [ ] Project Owner: _______________
- [ ] DevOps Lead: _______________
- [ ] Security Officer: _______________
- [ ] QA Lead: _______________

**Deployment Date:** _______________
