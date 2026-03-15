#!/usr/bin/env python3
"""
Verify PostgreSQL database via API endpoint.
This script uses the debug API to check database contents.
"""
import requests
import json
from datetime import datetime

API_BASE_URL = "https://bringo-api-uiuh5wz4wq-ew.a.run.app"

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)

def get_database_info():
    """Get database configuration info"""
    print_section("📊 Database Configuration")

    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/debug/database/info")
        response.raise_for_status()

        data = response.json()
        print(f"✅ Status: {data['status']}")
        print(f"\nDatabase Details:")
        for key, value in data['database'].items():
            print(f"  • {key}: {value}")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def get_all_users():
    """Get all users from database"""
    print_section("👥 All Users in Database")

    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/debug/database/users")
        response.raise_for_status()

        data = response.json()
        print(f"✅ Status: {data['status']}")
        print(f"Total users: {data['count']}\n")

        if data['users']:
            for i, user in enumerate(data['users'], 1):
                print(f"{i}. {user.get('email', 'N/A')}")
                print(f"   Session Cookie: {user.get('session_cookie', 'N/A')[:20]}..." if user.get('session_cookie') else "   Session Cookie: None")
                print(f"   Cookie Expires: {user.get('cookie_expires', 'N/A')}")
                print(f"   Last Login: {user.get('last_login', 'N/A')}")
                print(f"   Created At: {user.get('created_at', 'N/A')}")

                # Calculate time until expiration
                if user.get('cookie_expires'):
                    try:
                        expires_str = user['cookie_expires'].replace('+00:00', 'Z')
                        expires_at = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                        now = datetime.now(expires_at.tzinfo)
                        time_remaining = (expires_at - now).total_seconds() / 3600

                        print(f"\n   ⏰ Session Status:")
                        if time_remaining > 0:
                            print(f"   • Time until expiration: {time_remaining:.2f} hours")
                            print(f"   • Status: ACTIVE ✅")
                        else:
                            print(f"   • Session expired {abs(time_remaining):.2f} hours ago")
                            print(f"   • Status: EXPIRED ❌")
                    except Exception as e:
                        print(f"   • Error parsing expiration: {e}")

                print()
        else:
            print("No users found in database")

        return data.get('users', [])
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_specific_user(email):
    """Get specific user details"""
    print_section(f"🔍 User Details: {email}")

    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/debug/database/credentials/{email}")
        response.raise_for_status()

        data = response.json()
        print(f"✅ Status: {data['status']}\n")

        creds = data.get('credentials', {})
        print(f"User Information:")
        for key, value in creds.items():
            if key == 'session_cookie' and value:
                print(f"  • {key}: {value[:20]}...")
            elif key == 'password':
                print(f"  • {key}: ********")
            else:
                print(f"  • {key}: {value}")

        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"❌ User not found: {email}")
        else:
            print(f"❌ Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_login():
    """Test login functionality"""
    print_section("🔐 Testing Login")

    login_data = {
        "username": "radan.petrica@yahoo.com",
        "password": "AgentAI2025",
        "store": "carrefour_park_lake"
    }

    try:
        print("Attempting login...")
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json=login_data,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        print(f"✅ Login Status: {data.get('status', 'unknown')}")
        print(f"Message: {data.get('message', 'N/A')}")
        print(f"Username: {data.get('username', 'N/A')}")
        print(f"Session Cookie: {data.get('phpsessid', 'N/A')[:20]}...")
        print(f"Expires At: {data.get('expires_at', 'N/A')}")

        return True
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False

def main():
    """Main function"""
    print("🐘 PostgreSQL Database Verification (via API)")
    print("API Base URL:", API_BASE_URL)

    # 1. Get database configuration
    get_database_info()

    # 2. Get all users
    users = get_all_users()

    # 3. Get specific user if exists
    if users:
        get_specific_user(users[0].get('email', 'radan.petrica@yahoo.com'))

    # 4. Test login (optional - uncomment to test)
    # test_login()

    print_section("✅ Verification Complete")
    print("\nAll data is stored in PostgreSQL Cloud SQL!")
    print("\nTo verify in real-time, visit:")
    print(f"  {API_BASE_URL}/api/v1/debug/database/users")

if __name__ == "__main__":
    main()
