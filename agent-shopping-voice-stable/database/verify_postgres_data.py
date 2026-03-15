#!/usr/bin/env python3
"""
Verify PostgreSQL database contains the expected user data.
This script connects directly to Cloud SQL PostgreSQL and checks the data.
"""
import psycopg2
import sys
from datetime import datetime

# Database connection parameters
DB_CONFIG = {
    'host': '/cloudsql/formare-ai:europe-west1:bringo-db',
    'port': '5432',
    'database': 'bringo_auth',
    'user': 'bringo_user',
    'password': 'bringo_pass'
}

def connect_to_database():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Successfully connected to PostgreSQL database")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

def check_user_data(conn, email="radan.petrica@yahoo.com"):
    """Check if user data exists in the database"""
    cursor = conn.cursor()

    try:
        # Check if user exists in credentials table
        print(f"\n🔍 Checking user: {email}")
        print("="*60)

        cursor.execute("""
            SELECT
                email,
                session_cookie,
                cookie_expires,
                last_login,
                created_at,
                updated_at
            FROM credentials
            WHERE email = %s
        """, (email,))

        result = cursor.fetchone()

        if result:
            print("✅ User found in database!")
            print(f"\n📋 User Details:")
            print(f"  • Email: {result[0]}")
            print(f"  • Session Cookie: {result[1][:20]}..." if result[1] else "  • Session Cookie: None")
            print(f"  • Cookie Expires: {result[2]}")
            print(f"  • Last Login: {result[3]}")
            print(f"  • Created At: {result[4]}")
            print(f"  • Updated At: {result[5]}")

            # Calculate time until expiration
            if result[2]:
                expires_at = result[2]
                now = datetime.now(expires_at.tzinfo)
                time_remaining = (expires_at - now).total_seconds() / 3600
                print(f"\n⏰ Session Status:")
                if time_remaining > 0:
                    print(f"  • Time until expiration: {time_remaining:.2f} hours")
                    print(f"  • Status: ACTIVE ✅")
                else:
                    print(f"  • Session expired {abs(time_remaining):.2f} hours ago")
                    print(f"  • Status: EXPIRED ❌")
        else:
            print(f"❌ User {email} not found in database")
            return False

        # Check session history
        print(f"\n📊 Recent Session History:")
        print("-"*60)
        cursor.execute("""
            SELECT
                action,
                session_cookie,
                expires_at,
                created_at
            FROM session_history
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (email,))

        history = cursor.fetchall()
        if history:
            for i, record in enumerate(history, 1):
                action, session, expires, created = record
                print(f"{i}. {action.upper()}")
                print(f"   Session: {session[:20] if session else 'N/A'}...")
                print(f"   Expires: {expires}")
                print(f"   Created: {created}")
                print()
        else:
            print("  No session history found")

        return True

    except Exception as e:
        print(f"❌ Error checking user data: {e}")
        return False
    finally:
        cursor.close()

def get_all_users(conn):
    """Get all users from the database"""
    cursor = conn.cursor()

    try:
        print(f"\n👥 All Users in Database:")
        print("="*60)

        cursor.execute("""
            SELECT
                email,
                session_cookie,
                cookie_expires,
                last_login
            FROM credentials
            ORDER BY last_login DESC
        """)

        users = cursor.fetchall()

        if users:
            print(f"Total users: {len(users)}\n")
            for i, user in enumerate(users, 1):
                email, session, expires, last_login = user
                print(f"{i}. {email}")
                print(f"   Session: {session[:20] if session else 'N/A'}...")
                print(f"   Expires: {expires}")
                print(f"   Last Login: {last_login}")
                print()
        else:
            print("No users found in database")

    except Exception as e:
        print(f"❌ Error getting all users: {e}")
    finally:
        cursor.close()

def main():
    """Main function"""
    print("🐘 PostgreSQL Database Verification Script")
    print("="*60)
    print(f"Database: {DB_CONFIG['database']}")
    print(f"Host: {DB_CONFIG['host']}")
    print(f"User: {DB_CONFIG['user']}")
    print()

    # Connect to database
    conn = connect_to_database()

    try:
        # Check specific user
        check_user_data(conn, "radan.petrica@yahoo.com")

        # Get all users
        get_all_users(conn)

        print("\n" + "="*60)
        print("✅ Database verification complete!")

    finally:
        conn.close()
        print("🔒 Database connection closed")

if __name__ == "__main__":
    main()
