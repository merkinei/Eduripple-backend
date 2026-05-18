# deploy-to-gcloud.ps1 - PowerShell deployment script for Google Cloud
# Usage: .\deploy-to-gcloud.ps1 -DeploymentType "cloud-run" -Region "us-central1"

param(
    [string]$DeploymentType = "cloud-run",
    [string]$Region = "us-central1"
)

# Color functions
function Write-Success {
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[-] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Yellow
}

# Get project ID
$ProjectID = gcloud config get-value project 2>$null

if ([string]::IsNullOrEmpty($ProjectID)) {
    Write-Error-Custom "No Google Cloud project configured"
    Write-Host "Set your project with: gcloud config set project PROJECT_ID"
    exit 1
}

Write-Host ""
Write-Host "EduRipple Google Cloud Deployment" -ForegroundColor Cyan
Write-Host "Project: $ProjectID"
Write-Host "Region: $Region"
Write-Host "Deployment Type: $DeploymentType"
Write-Host ""

# Validate environment
Write-Info "Validating environment..."

# gcloud is required, docker is optional (Cloud Build handles it)
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error-Custom "gcloud not found. Please install Google Cloud SDK first."
    exit 1
}

$hasDocker = (Get-Command docker -ErrorAction SilentlyContinue) -ne $null
if (-not $hasDocker) {
    Write-Info "Docker not found locally - will use Cloud Build for container build (this is fine!)"
}

$files = @("requirements.txt", "Dockerfile")
foreach ($file in $files) {
    if (-not (Test-Path $file)) {
        Write-Error-Custom "$file not found"
        exit 1
    }
}

Write-Success "Environment validated"
Write-Host ""

# Enable APIs
Write-Info "Enabling Google Cloud APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com container.googleapis.com artifactregistry.googleapis.com --project=$ProjectID
Write-Success "APIs enabled"
Write-Host ""

# Build Docker image
Write-Info "Building Docker image..."
gcloud builds submit `
    --tag "gcr.io/$ProjectID/eduripple-backend:latest" `
    --project=$ProjectID

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Docker build failed"
    exit 1
}
Write-Success "Docker image built and pushed"
Write-Host ""

# Deploy
if ($DeploymentType -eq "cloud-run") {
    Write-Info "Deploying to Cloud Run..."
    
    gcloud run deploy eduripple-backend `
        --image "gcr.io/$ProjectID/eduripple-backend:latest" `
        --region $Region `
        --platform managed `
        --memory 2Gi `
        --cpu 2 `
        --timeout 3600 `
        --allow-unauthenticated `
        --set-env-vars FLASK_ENV=production,PORT=8080 `
        --project=$ProjectID
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Cloud Run deployment failed"
        exit 1
    }
    
    $ServiceURL = gcloud run services describe eduripple-backend `
        --region $Region `
        --format 'value(status.url)' `
        --project=$ProjectID
    
    Write-Success "Deployment successful!"
    Write-Host ""
    Write-Host "Service URL: $ServiceURL" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Configure environment variables:"
    Write-Host "   gcloud run services update eduripple-backend --region $Region --update-env-vars KEY=value"
    Write-Host "2. Test your application:"
    Write-Host "   curl $ServiceURL/api/system/health"
    Write-Host "3. Setup custom domain (optional)"
    
} elseif ($DeploymentType -eq "app-engine") {
    Write-Info "Deploying to App Engine..."
    
    if (-not (Test-Path "app.yaml")) {
        Write-Error-Custom "app.yaml not found"
        exit 1
    }
    
    gcloud app deploy app.yaml `
        --project=$ProjectID `
        --region=$Region
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "App Engine deployment failed"
        exit 1
    }
    
    Write-Success "Deployment successful!"
    Write-Host ""
    Write-Host "App Engine dashboard:" -ForegroundColor Cyan
    Write-Host "https://console.cloud.google.com/appengine?project=$ProjectID"
    
} else {
    Write-Error-Custom "Invalid deployment type: $DeploymentType"
    Write-Host "Valid options: cloud-run, app-engine"
    exit 1
}

Write-Host ""
Write-Success "Deployment complete!"
