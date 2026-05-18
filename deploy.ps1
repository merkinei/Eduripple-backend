# Deploy EduRipple Backend to Google Cloud Run
# This is the fastest way to get started

Write-Host "EduRipple Deployment" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[!] .env file not found" -ForegroundColor Yellow
    Write-Host "Creating from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[+] .env created. Please edit it with your API keys." -ForegroundColor Green
    Write-Host ""
    Write-Host "Edit .env and add:" -ForegroundColor Cyan
    Write-Host "  - FLASK_SECRET_KEY (generate: python3 -c 'import secrets; print(secrets.token_hex(32))')" -ForegroundColor Gray
    Write-Host "  - GEMINI_API_KEY" -ForegroundColor Gray
    Write-Host "  - OPENROUTER_API_KEY" -ForegroundColor Gray
    Write-Host "  - ELEVENLABS_API_KEY" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Then run: .\deploy.ps1" -ForegroundColor Green
    exit 0
}

Write-Host "[+] Configuration found" -ForegroundColor Green
Write-Host ""
Write-Host "Starting deployment to Google Cloud Run..." -ForegroundColor Cyan
Write-Host "Region: us-central1" -ForegroundColor Gray
Write-Host ""

# Run deployment
& .\deploy-to-gcloud.ps1 -DeploymentType 'cloud-run' -Region 'us-central1'

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Deployment successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Go to https://console.cloud.google.com/run" -ForegroundColor Gray
    Write-Host "2. Click 'eduripple-backend'" -ForegroundColor Gray
    Write-Host "3. Set environment variables (if not done during deployment)" -ForegroundColor Gray
    Write-Host "4. Test the endpoint: curl https://[your-service-url]/api/system/health" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
    Write-Host "Check the output above for errors" -ForegroundColor Red
    exit 1
}
