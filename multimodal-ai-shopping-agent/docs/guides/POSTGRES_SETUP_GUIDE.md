# PostgreSQL Multi-Tenant Setup Guide

## Overview

This guide sets up **Cloud SQL PostgreSQL** for your Bringo authentication system with:
- ✅ **Multi-tenancy by email** - Support multiple users
- ✅ **Shared database** - Worker pool and API access the same data
- ✅ **Production-ready** - Managed, reliable, with automatic backups
- ✅ **Cost-effective** - ~$10/month for db-f1-micro instance

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloud SQL PostgreSQL                      │
│                   (Multi-Tenant Database)                    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  credentials table                                    │   │
│  │  ├─ email (PRIMARY KEY, tenant identifier)           │   │
│  │  ├─ password                                          │   │
│  │  ├─ session_cookie (PHPSESSID)                       │   │
│  │  ├─ cookie_expires                                    │   │
│  │  └─ last_login                                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└───────────────────┬───────────────────┬─────────────────────┘
                    │                   │
        ┌───────────▼────────┐  ┌──────▼──────────┐
        │  Worker Pool       │  │   API Service    │
        │  (Keeps sessions   │  │  (Uses sessions) │
        │   alive 24/7)      │  │                  │
        └────────────────────┘  └──────────────────┘
```

## Quick Start (3 Steps)

### Step 1: Create Cloud SQL Instance (~10 minutes)

```bash
cd ai_agents/agent-bringo

# Run setup script
./setup_cloud_sql.sh
```

This script will:
1. Create PostgreSQL instance in Cloud SQL
2. Create `bringo_auth` database
3. Create database user with secure password
4. Save credentials to Secret Manager
5. Grant Cloud Run access to Cloud SQL
6. Generate environment configuration

**Expected output:**
```
🎉 Cloud SQL Setup Complete!

Connection Details:
===================
Instance Connection Name: formare-ai:europe-west1:bringo-db
Database: bringo_auth
User: bringo_user
Password: [auto-generated]
```

### Step 2: Deploy Worker Pool with PostgreSQL

```bash
# Rebuild and deploy worker pool
./deploy_worker_with_postgres.sh
```

This will:
1. Fetch credentials from Secret Manager
2. Rebuild Docker image with PostgreSQL support (psycopg2)
3. Deploy worker pool with Cloud SQL connection
4. Configure environment variables

**Deployment time:** ~3-5 minutes

### Step 3: Update API to Use PostgreSQL

Add to your API deployment configuration:

```yaml
env_variables:
  USE_POSTGRES: "true"
  DB_HOST: "/cloudsql/formare-ai:europe-west1:bringo-db"
  DB_PORT: "5432"
  DB_NAME: "bringo_auth"
  DB_USER: "[from Secret Manager]"
  DB_PASSWORD: "[from Secret Manager]"
```

Or export to .env:

```bash
# Get credentials
DB_USER=$(gcloud secrets versions access latest --secret="bringo-db-user")
DB_PASSWORD=$(gcloud secrets versions access latest --secret="bringo-db-password")
DB_NAME=$(gcloud secrets versions access latest --secret="bringo-db-name")

# Add to .env
echo "USE_POSTGRES=true" >> .env
echo "DB_HOST=/cloudsql/formare-ai:europe-west1:bringo-db" >> .env
echo "DB_PORT=5432" >> .env
echo "DB_NAME=$DB_NAME" >> .env
echo "DB_USER=$DB_USER" >> .env
echo "DB_PASSWORD=$DB_PASSWORD" >> .env
```

## Multi-Tenancy Features

### Adding Multiple Users

The database supports multiple tenants (users) identified by email:

```python
# Add first user
db.save_credentials("user1@example.com", "password123")

# Add second user
db.save_credentials("user2@example.com", "password456")

# Get specific user's session
creds = db.get_credentials("user1@example.com")
```

### Worker Pool Multi-User Support

To manage multiple users with the worker pool, modify `workers/session_keepalive_worker.py`:

```python
def process_all_users(self):
    """Process sessions for ALL users (multi-tenant)"""
    users = db.get_all_users()

    for user in users:
        email = user['email']
        phpsessid = user['session_cookie']
        expires_at = user['cookie_expires']

        logger.info(f"Checking session for: {email}")

        if self.should_refresh_session(expires_at):
            password = self.get_user_password(email)
            self.refresh_session(email, password, settings.BRINGO_STORE)
```

Call this in the main loop instead of `process_sessions()`.

## Database Schema

### credentials table

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| email | VARCHAR(255) | User email (unique, tenant ID) |
| password | TEXT | Encrypted password |
| session_cookie | TEXT | Current PHPSESSID |
| cookie_expires | TIMESTAMP | When session expires |
| last_login | TIMESTAMP | Last successful login |
| created_at | TIMESTAMP | Account created date |
| updated_at | TIMESTAMP | Last update |

### session_history table (audit log)

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Auto-increment primary key |
| email | VARCHAR(255) | User email (FK to credentials) |
| action | VARCHAR(50) | Action type (refresh, validate) |
| session_cookie | TEXT | Session cookie at time of action |
| expires_at | TIMESTAMP | Expiration at time of action |
| created_at | TIMESTAMP | When action occurred |

### stores table

Shared across all tenants for store information.

## Local Development

### Option 1: Cloud SQL Proxy (Recommended)

```bash
# Download Cloud SQL Proxy
wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud_sql_proxy
chmod +x cloud_sql_proxy

# Start proxy
./cloud_sql_proxy -instances=formare-ai:europe-west1:bringo-db=tcp:5432

# In another terminal, use localhost:5432
# Connection string: postgresql://bringo_user:password@localhost:5432/bringo_auth
```

### Option 2: Direct Connection (requires whitelisting)

Whitelist your IP in Cloud SQL:

```bash
gcloud sql instances patch bringo-db \
  --authorized-networks=YOUR_IP_ADDRESS \
  --project=formare-ai
```

Then connect directly:

```bash
# Connection
psql -h [INSTANCE_IP] -U bringo_user -d bringo_auth
```

## Migration from SQLite to PostgreSQL

Migrate existing data:

```python
# migration_script.py
import sqlite3
import psycopg2

# Read from SQLite
sqlite_conn = sqlite3.connect('data/credentials.db')
sqlite_cursor = sqlite_conn.cursor()
sqlite_cursor.execute("SELECT * FROM credentials")
rows = sqlite_cursor.fetchall()

# Write to PostgreSQL
pg_conn = psycopg2.connect(
    host="/cloudsql/formare-ai:europe-west1:bringo-db",
    port=5432,
    database="bringo_auth",
    user="bringo_user",
    password="[password]"
)
pg_cursor = pg_conn.cursor()

for row in rows:
    pg_cursor.execute("""
        INSERT INTO credentials (email, password, session_cookie, cookie_expires, last_login)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
            password = EXCLUDED.password,
            session_cookie = EXCLUDED.session_cookie
    """, (row['username'], row['password'], row['session_cookie'],
          row['cookie_expires'], row['last_login']))

pg_conn.commit()
print("✅ Migration complete!")
```

## Monitoring

### Check Database Status

```bash
# Instance status
gcloud sql instances describe bringo-db --project=formare-ai

# View active connections
gcloud sql operations list --instance=bringo-db --project=formare-ai

# Check logs
gcloud sql operations logs list bringo-db --project=formare-ai
```

### Query Database

```bash
# Connect to database
gcloud sql connect bringo-db --user=bringo_user --database=bringo_auth

# Run queries
SELECT email, last_login, cookie_expires FROM credentials;
SELECT * FROM session_history ORDER BY created_at DESC LIMIT 10;
```

## Cost Analysis

### Cloud SQL db-f1-micro (smallest)

- **vCPUs**: 1 shared core
- **RAM**: 0.6 GB
- **Storage**: 10 GB SSD
- **Cost**: ~$9.37/month
- **Plus backups**: ~$0.08/GB/month
- **Total**: ~$10-12/month

### Scaling Options

As you grow:

| Instance Type | vCPUs | RAM | Cost/Month | Use Case |
|--------------|-------|-----|------------|----------|
| db-f1-micro | 1 shared | 0.6GB | $9.37 | 1-10 users |
| db-g1-small | 1 shared | 1.7GB | $24.75 | 10-50 users |
| db-n1-standard-1 | 1 | 3.75GB | $46.55 | 50-200 users |
| db-n1-standard-2 | 2 | 7.5GB | $93.10 | 200+ users |

## Troubleshooting

### Connection Issues

```bash
# Test connection from Cloud Run
gcloud run services list
gcloud run revisions describe [REVISION] --format="get(spec.containers[0].env)"

# Verify Cloud SQL proxy permissions
gcloud projects get-iam-policy formare-ai \
  --flatten="bindings[].members" \
  --filter="bindings.members:formare-ai@appspot.gserviceaccount.com"
```

### Database Queries

```sql
-- Check all users
SELECT email, last_login FROM credentials;

-- Check session history
SELECT email, action, created_at
FROM session_history
WHERE email = 'your@email.com'
ORDER BY created_at DESC
LIMIT 10;

-- Find expired sessions
SELECT email, cookie_expires
FROM credentials
WHERE cookie_expires < NOW();
```

## Security Best Practices

1. **Passwords in Secret Manager** - Never commit database passwords
2. **Connection via Unix Socket** - More secure than TCP for Cloud Run
3. **Automated Backups** - Configured in setup script (daily at 3 AM)
4. **Regular Updates** - Keep PostgreSQL version updated
5. **Audit Logging** - session_history table tracks all actions

## Next Steps

After setup:

1. ✅ Run `./setup_cloud_sql.sh`
2. ✅ Run `./deploy_worker_with_postgres.sh`
3. ✅ Update API deployment with PostgreSQL config
4. ⏳ Test with one user
5. ⏳ Add more users as needed
6. ⏳ Monitor logs and costs

## FAQ

**Q: Can I use the free tier?**
A: db-f1-micro is the cheapest (~$10/month), but there's no free tier for Cloud SQL.

**Q: What about Firestore instead?**
A: Firestore has a free tier and would work, but PostgreSQL is better for relational data and complex queries.

**Q: How do I backup?**
A: Automatic daily backups are configured. Manual: `gcloud sql backups create --instance=bringo-db`

**Q: Can I pause the database when not in use?**
A: No auto-pause, but you can manually stop/start: `gcloud sql instances patch bringo-db --activation-policy=NEVER`

**Q: What if I need to reset everything?**
A: Delete instance: `gcloud sql instances delete bringo-db --project=formare-ai` (then re-run setup)

## Summary

✅ **Benefits of PostgreSQL Multi-Tenant Setup**:
- Shared database between worker and API
- Support for multiple users (tenants)
- Production-ready with automatic backups
- SQL queries for analytics and debugging
- Audit trail with session_history table

🎯 **Total Setup Time**: ~15 minutes
💰 **Monthly Cost**: ~$10-12
🚀 **Ready for Production**: Yes!

---

Need help? Check the logs or run the diagnostic commands above!
