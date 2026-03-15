#!/bin/bash
# Setup Cloud SQL PostgreSQL for Bringo Multi-Tenant Authentication
# This creates a shared database accessible by both worker pool and API

set -e

PROJECT_ID=${GCP_PROJECT_ID:-"formare-ai"}
REGION=${GCP_REGION:-"europe-west1"}
INSTANCE_NAME="bringo-db"
DATABASE_NAME="bringo_auth"
DB_USER="bringo_user"

echo "🚀 Setting up Cloud SQL PostgreSQL..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Instance: $INSTANCE_NAME"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Create Cloud SQL instance
echo -e "${YELLOW}📦 Creating Cloud SQL PostgreSQL instance...${NC}"
echo "This may take 5-10 minutes..."

gcloud sql instances create $INSTANCE_NAME \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --project=$PROJECT_ID \
  --root-password=$(openssl rand -base64 32) \
  --storage-type=SSD \
  --storage-size=10GB \
  --backup \
  --backup-start-time=03:00 \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=04 \
  || echo "Instance may already exist, continuing..."

echo -e "${GREEN}✅ Cloud SQL instance created${NC}"

# Step 2: Create database
echo -e "${YELLOW}📊 Creating database: $DATABASE_NAME${NC}"

gcloud sql databases create $DATABASE_NAME \
  --instance=$INSTANCE_NAME \
  --project=$PROJECT_ID \
  || echo "Database may already exist, continuing..."

echo -e "${GREEN}✅ Database created${NC}"

# Step 3: Create user with password
echo -e "${YELLOW}👤 Creating database user: $DB_USER${NC}"

DB_PASSWORD=$(openssl rand -base64 32)

gcloud sql users create $DB_USER \
  --instance=$INSTANCE_NAME \
  --password="$DB_PASSWORD" \
  --project=$PROJECT_ID \
  || echo "User may already exist, continuing..."

echo -e "${GREEN}✅ Database user created${NC}"

# Step 4: Get connection details
echo ""
echo -e "${GREEN}🎉 Cloud SQL Setup Complete!${NC}"
echo ""
echo "Connection Details:"
echo "==================="
echo "Instance Connection Name: $PROJECT_ID:$REGION:$INSTANCE_NAME"
echo "Database: $DATABASE_NAME"
echo "User: $DB_USER"
echo "Password: $DB_PASSWORD"
echo ""
echo "Unix Socket (for Cloud Run): /cloudsql/$PROJECT_ID:$REGION:$INSTANCE_NAME"
echo ""

# Step 5: Save credentials to Secret Manager
echo -e "${YELLOW}🔐 Saving credentials to Secret Manager...${NC}"

# Create secrets
echo -n "$DB_PASSWORD" | gcloud secrets create bringo-db-password \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID \
  || gcloud secrets versions add bringo-db-password \
  --data-file=- \
  --project=$PROJECT_ID <<< "$DB_PASSWORD"

echo -n "$DB_USER" | gcloud secrets create bringo-db-user \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID \
  || gcloud secrets versions add bringo-db-user \
  --data-file=- \
  --project=$PROJECT_ID <<< "$DB_USER"

echo -n "$DATABASE_NAME" | gcloud secrets create bringo-db-name \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID \
  || gcloud secrets versions add bringo-db-name \
  --data-file=- \
  --project=$PROJECT_ID <<< "$DATABASE_NAME"

echo -n "$PROJECT_ID:$REGION:$INSTANCE_NAME" | gcloud secrets create bringo-db-connection-name \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID \
  || gcloud secrets versions add bringo-db-connection-name \
  --data-file=- \
  --project=$PROJECT_ID <<< "$PROJECT_ID:$REGION:$INSTANCE_NAME"

echo -e "${GREEN}✅ Credentials saved to Secret Manager${NC}"

# Step 6: Grant Cloud Run service account access to Cloud SQL
echo -e "${YELLOW}🔑 Granting Cloud Run access to Cloud SQL...${NC}"

# Get the default Cloud Run service account
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/cloudsql.client" \
  --project=$PROJECT_ID

echo -e "${GREEN}✅ Permissions granted${NC}"

# Step 7: Display environment variables
echo ""
echo "Environment Variables for Cloud Run:"
echo "====================================="
echo "DB_HOST=/cloudsql/$PROJECT_ID:$REGION:$INSTANCE_NAME"
echo "DB_PORT=5432"
echo "DB_NAME=$DATABASE_NAME"
echo "DB_USER=$DB_USER"
echo "DB_PASSWORD=$DB_PASSWORD"
echo ""

# Step 8: Create .env.postgres for local development
cat > .env.postgres <<EOF
# PostgreSQL Configuration (for local development with Cloud SQL Proxy)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=$DATABASE_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# Cloud SQL Connection Name
CLOUD_SQL_CONNECTION_NAME=$PROJECT_ID:$REGION:$INSTANCE_NAME
EOF

echo -e "${GREEN}✅ Created .env.postgres for local development${NC}"
echo ""

echo "Next Steps:"
echo "==========="
echo "1. For local development, start Cloud SQL Proxy:"
echo "   ./cloud_sql_proxy -instances=$PROJECT_ID:$REGION:$INSTANCE_NAME=tcp:5432"
echo ""
echo "2. Deploy worker pool with Cloud SQL:"
echo "   ./deploy_worker_with_postgres.sh"
echo ""
echo "3. Deploy API with Cloud SQL:"
echo "   Update your API deployment to use the same environment variables"
echo ""
echo -e "${GREEN}🎉 All done!${NC}"
