#!/usr/bin/env python3
"""
Check and populate PostgreSQL database with initial credentials
"""
import os
import sys

# Set environment to use PostgreSQL
os.environ['USE_POSTGRES'] = 'true'
os.environ['DB_HOST'] = '/cloudsql/formare-ai:europe-west1:bringo-db'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'bringo_auth'
os.environ['DB_USER'] = 'bringo_user'

# Get password from Secret Manager
import subprocess
result = subprocess.run(
    ['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret=bringo-db-password', '--project=formare-ai'],
    capture_output=True,
    text=True
)
os.environ['DB_PASSWORD'] = result.stdout.strip()

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from database import db_adapter as db

def main():
    print("🔍 Checking PostgreSQL database...")
    print(f"Database info: {db.get_database_info()}")
    print()

    # Check existing users
    print("📋 Current users in database:")
    users = db.get_all_users()

    if not users:
        print("   No users found in database")
        print()

        # Add default user from environment
        username = "radan.petrica@yahoo.com"
        password = "AgentAI2025"

        print(f"📝 Adding default user: {username}")
        success = db.save_credentials(username, password)

        if success:
            print(f"   ✅ User added successfully")

            # Trigger initial login to get session
            print()
            print("🔐 Triggering initial login to get session cookie...")
            from services.auth_service import AuthService

            result = AuthService.login(username, password, "carrefour_park_lake")

            if result.get("status") == "success":
                print("   ✅ Login successful!")
                print(f"   Session cookie: {result.get('phpsessid', 'N/A')[:16]}...")
                print(f"   Expiration: {result.get('expires_at', 'N/A')}")
            else:
                print(f"   ❌ Login failed: {result.get('message', 'Unknown error')}")
        else:
            print(f"   ❌ Failed to add user")
    else:
        print(f"   Found {len(users)} user(s):")
        for user in users:
            print(f"   • {user.get('email')}")
            print(f"     - Session: {user.get('session_cookie', 'None')[:16] if user.get('session_cookie') else 'None'}...")
            print(f"     - Expires: {user.get('cookie_expires', 'Not set')}")
            print(f"     - Last login: {user.get('last_login', 'Never')}")
            print()

if __name__ == "__main__":
    main()
