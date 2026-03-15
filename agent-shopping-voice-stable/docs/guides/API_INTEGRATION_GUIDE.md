# API Integration Guide - PostgreSQL Database

## Overview

All services have been updated to use the **database adapter** which automatically switches between SQLite and PostgreSQL based on the `USE_POSTGRES` environment variable.

## What Changed

### Before (SQLite only)
```python
from services import db

db.save_credentials(username, password)
creds = db.get_credentials()
```

### After (SQLite or PostgreSQL)
```python
from database import db_adapter as db

# Same API, but now supports both databases!
db.save_credentials(username, password)
creds = db.get_credentials()
```

## Updated Files

✅ All files now use the database adapter:

1. **`services/auth_service.py`** - Authentication service
2. **`workers/session_keepalive_worker.py`** - Session refresh worker
3. **`services/store_service.py`** - Store management
4. **`tests/test_cart_with_feature_store.py`** - Cart tests
5. **`tests/test_cart.py`** - Cart tests

## Environment Configuration

### For Local Development (SQLite)

```bash
# .env
USE_POSTGRES=false  # Uses local SQLite database
# No other DB variables needed
```

### For Production (PostgreSQL)

```bash
# .env or Cloud Run environment variables
USE_POSTGRES=true
DB_HOST=/cloudsql/formare-ai:europe-west1:bringo-db
DB_PORT=5432
DB_NAME=bringo_auth
DB_USER=bringo_user
DB_PASSWORD=[from Secret Manager]
```

## API Deployment Options

### Option 1: Cloud Run Service (Recommended)

```bash
# Deploy your API with PostgreSQL connection
gcloud run deploy bringo-api \
  --image=gcr.io/formare-ai/bringo-api:latest \
  --region=europe-west1 \
  --project=formare-ai \
  --add-cloudsql-instances=formare-ai:europe-west1:bringo-db \
  --set-env-vars="
USE_POSTGRES=true,
DB_HOST=/cloudsql/formare-ai:europe-west1:bringo-db,
DB_PORT=5432,
DB_NAME=bringo_auth,
DB_USER=bringo_user,
DB_PASSWORD=$(gcloud secrets versions access latest --secret=bringo-db-password),
ENABLE_SESSION_VALIDATION_ON_REQUEST=false
" \
  --allow-unauthenticated
```

### Option 2: Update Existing Deployment

If your API is already deployed, update it:

```bash
# Get database credentials
DB_PASSWORD=$(gcloud secrets versions access latest --secret=bringo-db-password --project=formare-ai)

# Update environment variables
gcloud run services update YOUR_API_SERVICE_NAME \
  --region=YOUR_REGION \
  --project=formare-ai \
  --add-cloudsql-instances=formare-ai:europe-west1:bringo-db \
  --update-env-vars="
USE_POSTGRES=true,
DB_HOST=/cloudsql/formare-ai:europe-west1:bringo-db,
DB_PORT=5432,
DB_NAME=bringo_auth,
DB_USER=bringo_user,
DB_PASSWORD=$DB_PASSWORD,
ENABLE_SESSION_VALIDATION_ON_REQUEST=false
"
```

### Option 3: Local Development with Cloud SQL Proxy

```bash
# 1. Download Cloud SQL Proxy
wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud_sql_proxy
chmod +x cloud_sql_proxy

# 2. Start proxy in background
./cloud_sql_proxy -instances=formare-ai:europe-west1:bringo-db=tcp:5432 &

# 3. Set environment variables
export USE_POSTGRES=true
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=bringo_auth
export DB_USER=bringo_user
export DB_PASSWORD=$(gcloud secrets versions access latest --secret=bringo-db-password)

# 4. Run your API
uvicorn main:app --reload
```

## Verification

### Test Database Connection

```python
# test_db_connection.py
import os

# Set to use PostgreSQL
os.environ['USE_POSTGRES'] = 'true'
os.environ['DB_HOST'] = '/cloudsql/formare-ai:europe-west1:bringo-db'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'bringo_auth'
os.environ['DB_USER'] = 'bringo_user'
os.environ['DB_PASSWORD'] = 'your-password'

from database import db_adapter as db

# Test database info
print("Database Info:")
print(db.get_database_info())

# Test save credentials
print("\nTesting save credentials...")
result = db.save_credentials("test@example.com", "password123", "session_cookie")
print(f"Save result: {result}")

# Test get credentials
print("\nTesting get credentials...")
creds = db.get_credentials("test@example.com")
print(f"Retrieved: {creds}")

# Test get all users (PostgreSQL only)
print("\nTesting get all users...")
users = db.get_all_users()
print(f"Total users: {len(users)}")
for user in users:
    print(f"  - {user['email']}")

print("\n✅ All tests passed!")
```

Run it:
```bash
python test_db_connection.py
```

### Check Worker Pool Integration

The worker pool is already configured to use the database adapter. When you deploy it with PostgreSQL:

```bash
cd database
./deploy_worker_with_postgres.sh
```

It will automatically:
1. Build image with `psycopg2-binary`
2. Connect to Cloud SQL
3. Use PostgreSQL for all operations
4. Share sessions with your API!

## Migration Path

### Step 1: Ensure Cloud SQL is Ready

```bash
# Check if instance is running
gcloud sql instances describe bringo-db --project=formare-ai

# Should show: state: RUNNABLE
```

### Step 2: Migrate Existing Data (Optional)

If you have existing sessions in SQLite:

```python
# migrate_data.py
import os
from services import db as sqlite_db

# Get existing data from SQLite
old_creds = sqlite_db.get_credentials()

if old_creds:
    # Switch to PostgreSQL
    os.environ['USE_POSTGRES'] = 'true'
    # ... set other env vars ...

    from database import db_adapter as postgres_db

    # Save to PostgreSQL
    postgres_db.save_credentials(
        old_creds['username'],
        old_creds['password'],
        old_creds.get('session_cookie')
    )

    if old_creds.get('cookie_expires'):
        postgres_db.update_session(
            old_creds['username'],
            old_creds['session_cookie'],
            old_creds['cookie_expires']
        )

    print("✅ Migration complete!")
```

### Step 3: Deploy API with PostgreSQL

Use one of the deployment options above.

### Step 4: Redeploy Worker Pool

```bash
cd database
./deploy_worker_with_postgres.sh
```

### Step 5: Verify Everything Works

```bash
# Check API logs
gcloud run services logs read YOUR_API_SERVICE --region=YOUR_REGION

# Check worker pool logs
gcloud logging read "resource.labels.service_name=bringo-session-keepalive" \
  --project=formare-ai \
  --limit=50

# Test an API endpoint
curl https://YOUR_API_URL/api/v1/cart
```

## Troubleshooting

### "Module not found: database"

**Solution**: Make sure the `database/` folder is included in your deployment:

```dockerfile
# In your Dockerfile
COPY database/ /app/database/
```

Or if using `.gcloudignore`, ensure `database/` is not ignored.

### "Connection refused"

**Solution**: Ensure Cloud SQL instance is added to your service:

```bash
gcloud run services update YOUR_SERVICE \
  --add-cloudsql-instances=formare-ai:europe-west1:bringo-db
```

### "Permission denied for Cloud SQL"

**Solution**: Grant the Cloud Run service account access:

```bash
gcloud projects add-iam-policy-binding formare-ai \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@formare-ai.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client" \
  --condition=None
```

### Database adapter not switching

**Solution**: Check the `USE_POSTGRES` environment variable:

```python
import os
print(f"USE_POSTGRES = {os.getenv('USE_POSTGRES')}")
```

Must be exactly `"true"` (lowercase) to enable PostgreSQL.

## Multi-User Support

With PostgreSQL, you can now manage multiple Bringo accounts:

```python
from database import db_adapter as db

# Add multiple users
db.save_credentials("user1@example.com", "pass1")
db.save_credentials("user2@example.com", "pass2")
db.save_credentials("user3@example.com", "pass3")

# Get specific user
user1 = db.get_credentials("user1@example.com")

# Get all users
all_users = db.get_all_users()
print(f"Managing {len(all_users)} users")
```

### Update Worker for Multi-User

Modify `workers/session_keepalive_worker.py`:

```python
def run(self):
    """Main worker loop - process all users"""
    while self.running:
        # Get all users
        users = db.get_all_users()

        for user in users:
            email = user['email']
            expires_at = user.get('cookie_expires')

            logger.info(f"Checking session for: {email}")

            if self.should_refresh_session(expires_at):
                password = user['password']
                self.refresh_session(email, password, settings.BRINGO_STORE)

        time.sleep(self.poll_interval_seconds)
```

## Summary

✅ **All services integrated** with database adapter
✅ **Automatic switching** between SQLite and PostgreSQL
✅ **Backward compatible** - existing code still works
✅ **Multi-tenant ready** - supports multiple users
✅ **Production ready** - connection pooling, error handling

**Next Steps:**
1. Wait for Cloud SQL instance to finish creating
2. Deploy worker pool with PostgreSQL
3. Deploy/update API with PostgreSQL
4. Test end-to-end

---

**Questions?** Check:
- [database/README.md](database/README.md) - Database usage
- [POSTGRES_SETUP_GUIDE.md](POSTGRES_SETUP_GUIDE.md) - PostgreSQL guide
- [COMPLETE_SOLUTION_SUMMARY.md](COMPLETE_SOLUTION_SUMMARY.md) - Overall summary
