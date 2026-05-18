#!/bin/bash
# deploy-to-gcloud.sh - Quick deployment script for Google Cloud
# Usage: ./deploy-to-gcloud.sh [cloud-run|app-engine] [region]

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_TYPE="${1:-cloud-run}"
REGION="${2:-us-central1}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No Google Cloud project configured.${NC}"
    echo "Set your project with: gcloud config set project PROJECT_ID"
    exit 1
fi

echo -e "${GREEN}EduRipple Google Cloud Deployment${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Deployment Type: $DEPLOYMENT_TYPE"
echo ""

# Step 1: Validate environment
echo -e "${YELLOW}Validating environment...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not installed${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker not installed${NC}"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: requirements.txt not found${NC}"
    exit 1
fi

if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Error: Dockerfile not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment validated${NC}"
echo ""

# Step 2: Enable required APIs
echo -e "${YELLOW}Enabling Google Cloud APIs...${NC}"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com container.googleapis.com artifactregistry.googleapis.com --project=$PROJECT_ID
echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Step 3: Build Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/eduripple-backend:latest \
    --project=$PROJECT_ID
echo -e "${GREEN}✓ Docker image built and pushed${NC}"
echo ""

# Step 4: Deploy based on type
if [ "$DEPLOYMENT_TYPE" = "cloud-run" ]; then
    echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
    
    gcloud run deploy eduripple-backend \
        --image gcr.io/$PROJECT_ID/eduripple-backend:latest \
        --region $REGION \
        --platform managed \
        --memory 2Gi \
        --cpu 2 \
        --timeout 3600 \
        --allow-unauthenticated \
        --set-env-vars FLASK_ENV=production,PORT=8080 \
        --project=$PROJECT_ID
    
    SERVICE_URL=$(gcloud run services describe eduripple-backend \
        --region $REGION \
        --format 'value(status.url)' \
        --project=$PROJECT_ID)
    
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo ""
    echo -e "Service URL: ${GREEN}$SERVICE_URL${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure environment variables:"
    echo "   gcloud run services update eduripple-backend --region $REGION --update-env-vars KEY=value"
    echo "2. Test your application:"
    echo "   curl $SERVICE_URL/api/system/health"
    echo "3. Setup custom domain (optional)"
    
elif [ "$DEPLOYMENT_TYPE" = "app-engine" ]; then
    echo -e "${YELLOW}Deploying to App Engine...${NC}"
    
    if [ ! -f "app.yaml" ]; then
        echo -e "${RED}Error: app.yaml not found${NC}"
        exit 1
    fi
    
    gcloud app deploy app.yaml \
        --project=$PROJECT_ID \
        --region=$REGION
    
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo ""
    echo "App Engine dashboard:"
    echo "https://console.cloud.google.com/appengine?project=$PROJECT_ID"
    
else
    echo -e "${RED}Error: Invalid deployment type '${DEPLOYMENT_TYPE}'${NC}"
    echo "Valid options: cloud-run, app-engine"
    exit 1
fi

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
