# Database Layer

This folder contains all database-related code and scripts for the Bringo session management system.

## Files

### Core Database Modules

- **`postgres_db.py`** - PostgreSQL database adapter with multi-tenancy support
  - Multi-tenant by email
  - Connection pooling
  - Session history tracking
  - Store management

- **`db_adapter.py`** - Smart database adapter
  - Automatically switches between SQLite and PostgreSQL
  - Based on `USE_POSTGRES` environment variable
  - Unified API for both database types

### Setup & Deployment Scripts

- **`setup_cloud_sql.sh`** - Creates Cloud SQL PostgreSQL instance
  - Sets up database and user
  - Configures permissions
  - Saves credentials to Secret Manager
  - **Run this first for PostgreSQL setup**

- **`deploy_worker_with_postgres.sh`** - Deploys worker pool with PostgreSQL
  - Rebuilds Docker image with PostgreSQL support
  - Configures Cloud SQL connection
  - Sets environment variables
  - **Run this after `setup_cloud_sql.sh`**

## Quick Start

### For PostgreSQL Multi-Tenant Setup

```bash
# 1. Create Cloud SQL instance (10 min)
cd database
./setup_cloud_sql.sh

# 2. Deploy worker pool with PostgreSQL (5 min)
./deploy_worker_with_postgres.sh

# 3. Update your code to use the database adapter
from database.db_adapter import (
    save_credentials,
    get_credentials,
    update_session,
    get_all_users
)

# The adapter will automatically use PostgreSQL if USE_POSTGRES=true
```

### For SQLite (Single-Tenant, Local)

The existing `services/db.py` continues to work as before.

```python
# Old code still works
from services import db

db.save_credentials(username, password)
creds = db.get_credentials()
```

## Usage Examples

### Using the Database Adapter

```python
import os
os.environ['USE_POSTGRES'] = 'true'  # or 'false' for SQLite

from database.db_adapter import (
    save_credentials,
    get_credentials,
    update_session,
    get_all_users,
    get_database_info
)

# Save credentials (works with both databases)
save_credentials("user@example.com", "password123", "session_cookie_value")

# Get credentials
creds = get_credentials("user@example.com")
print(f"Session: {creds['session_cookie']}")

# Update session
update_session("user@example.com", "new_session_cookie", "2026-02-01T18:00:00")

# Get all users (PostgreSQL only, returns single user for SQLite)
users = get_all_users()
for user in users:
    print(f"{user['email']}: {user['cookie_expires']}")

# Check database type
db_info = get_database_info()
print(f"Using {db_info['type']} database")
```

### Multi-Tenant Operations (PostgreSQL Only)

```python
# Add multiple users
save_credentials("user1@example.com", "pass1")
save_credentials("user2@example.com", "pass2")
save_credentials("user3@example.com", "pass3")

# Get all users
all_users = get_all_users()
print(f"Managing {len(all_users)} users")

# Process each user's session
for user in all_users:
    email = user['email']
    session = user['session_cookie']
    expires = user['cookie_expires']

    if needs_refresh(expires):
        refresh_session(email, password, session)
```

## Environment Variables

### PostgreSQL Configuration

```bash
USE_POSTGRES=true
DB_HOST=/cloudsql/formare-ai:europe-west1:bringo-db  # Unix socket
DB_PORT=5432
DB_NAME=bringo_auth
DB_USER=bringo_user
DB_PASSWORD=[from Secret Manager]
```

### SQLite Configuration (Default)

```bash
USE_POSTGRES=false
# No additional variables needed
# Database file: data/credentials.db
```

## Database Schema

### PostgreSQL

#### credentials table
```sql
CREATE TABLE credentials (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password TEXT NOT NULL,
    session_cookie TEXT,
    cookie_expires TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

#### session_history table
```sql
CREATE TABLE session_history (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,
    session_cookie TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (email) REFERENCES credentials(email) ON DELETE CASCADE
);
```

### SQLite

See `services/db.py` for SQLite schema.

## Migration

To migrate from SQLite to PostgreSQL:

```python
# migration.py
from services import db as sqlite_db
from database import postgres_db
import os

os.environ['USE_POSTGRES'] = 'true'

# Read from SQLite
sqlite_creds = sqlite_db.get_credentials()

if sqlite_creds:
    # Write to PostgreSQL
    postgres_db.save_credentials(
        email=sqlite_creds['username'],
        password=sqlite_creds['password'],
        session_cookie=sqlite_creds['session_cookie']
    )

    if sqlite_creds.get('cookie_expires'):
        postgres_db.update_session(
            email=sqlite_creds['username'],
            session_cookie=sqlite_creds['session_cookie'],
            expires=sqlite_creds['cookie_expires']
        )

    print("✅ Migration complete!")
```

## Troubleshooting

### Connection Issues

```bash
# Test PostgreSQL connection
gcloud sql connect bringo-db --user=bringo_user

# Check Cloud SQL status
gcloud sql instances describe bringo-db --project=formare-ai

# Verify environment variables
echo $USE_POSTGRES
echo $DB_HOST
echo $DB_NAME
```

### Import Errors

If you get import errors after moving files:

```python
# Update imports in your code
# Old:
from services import db

# New:
from database.db_adapter import save_credentials, get_credentials
```

## Cost

- **SQLite**: Free (local file)
- **PostgreSQL (db-f1-micro)**: ~$10/month
  - 1 shared vCPU
  - 0.6 GB RAM
  - 10 GB storage
  - Automatic backups

## Support

For detailed setup instructions, see:
- [../POSTGRES_SETUP_GUIDE.md](../POSTGRES_SETUP_GUIDE.md) - Complete PostgreSQL guide
- [../COMPLETE_SOLUTION_SUMMARY.md](../COMPLETE_SOLUTION_SUMMARY.md) - Overall solution summary

## Summary

✅ **Organized Structure**: All database code in one place
✅ **Flexible**: Switch between SQLite and PostgreSQL with one env variable
✅ **Multi-Tenant**: Support multiple users with PostgreSQL
✅ **Production-Ready**: Connection pooling, error handling, audit logging

---

**Quick Reference:**
- Setup PostgreSQL: `./setup_cloud_sql.sh`
- Deploy worker: `./deploy_worker_with_postgres.sh`
- Use in code: `from database.db_adapter import *`
