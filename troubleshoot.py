#!/usr/bin/env python3
"""
Troubleshooting script for ERP Sync
"""
import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv()


def check_env():
    """Check environment variables"""
    print("Checking environment variables...")

    required_vars = [
        'CLOUD_ERP_URL',
        'CLOUD_API_KEY',
        'CLOUD_API_SECRET',
        'LOCAL_ERP_URL',
        'LOCAL_API_KEY',
        'LOCAL_API_SECRET',
        'WEBHOOK_SECRET'
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or 'your_' in value or 'change_this' in value:
            missing.append(var)
            print(f"  [FAIL] {var}: Not configured")
        else:
            # Mask secrets
            if 'SECRET' in var or 'KEY' in var:
                masked = value[:4] + '****' + value[-4:]
                print(f"  [OK] {var}: {masked}")
            else:
                print(f"  [OK] {var}: {value}")

    if missing:
        print(f"\nERROR: Missing configuration: {', '.join(missing)}")
        print("   Please edit .env file with your credentials")
        return False

    return True


def check_network(url):
    """Check network connectivity"""
    try:
        response = requests.get(url, timeout=5)
        return True
    except requests.exceptions.Timeout:
        print(f"  [FAIL] Timeout connecting to {url}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"  [FAIL] Cannot connect to {url}")
        return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def check_frappe_api(url, api_key, api_secret, name):
    """Check Frappe API access"""
    print(f"\nChecking {name} ERP API...")

    # Test basic connectivity
    if not check_network(url):
        return False

    # Test API authentication
    try:
        headers = {
            'Authorization': f'token {api_key}:{api_secret}'
        }
        response = requests.get(
            f'{url}/api/method/frappe.auth.get_logged_user',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            user = response.json().get('message')
            print(f"  [OK] API authentication successful")
            print(f"  [OK] Logged in as: {user}")
            return True
        elif response.status_code == 401:
            print(f"  [FAIL] Authentication failed - check API credentials")
            return False
        else:
            print(f"  [FAIL] Unexpected response: {response.status_code}")
            return False

    except Exception as e:
        print(f"  [FAIL] API test failed: {e}")
        return False


def check_database():
    """Check database"""
    print("\nChecking database...")

    if not os.path.exists('sync_state.db'):
        print("  [FAIL] Database not initialized")
        print("    Run: python main.py init")
        return False

    try:
        from models import get_db, SyncRecord
        db = get_db()
        count = db.query(SyncRecord).count()
        db.close()
        print(f"  [OK] Database initialized ({count} sync records)")
        return True
    except Exception as e:
        print(f"  [FAIL] Database error: {e}")
        return False


def check_webhook_server():
    """Check if webhook server is running"""
    print("\nChecking webhook server...")

    webhook_port = int(os.getenv('WEBHOOK_PORT', 5000))

    try:
        response = requests.get(f'http://localhost:{webhook_port}/health', timeout=2)
        if response.status_code == 200:
            print(f"  [OK] Webhook server is running on port {webhook_port}")
            return True
    except:
        print(f"  [FAIL] Webhook server is not running on port {webhook_port}")
        print(f"    Start with: python main.py webhook")
        return False


def main():
    print("="*60)
    print("    ERP Sync - Troubleshooting")
    print("="*60)

    all_ok = True

    # Check environment
    if not check_env():
        all_ok = False

    # Check database
    if not check_database():
        all_ok = False

    # Check cloud ERP
    if not check_frappe_api(
        os.getenv('CLOUD_ERP_URL'),
        os.getenv('CLOUD_API_KEY'),
        os.getenv('CLOUD_API_SECRET'),
        'Cloud'
    ):
        all_ok = False

    # Check local ERP
    if not check_frappe_api(
        os.getenv('LOCAL_ERP_URL'),
        os.getenv('LOCAL_API_KEY'),
        os.getenv('LOCAL_API_SECRET'),
        'Local'
    ):
        all_ok = False

    # Check webhook server (optional)
    check_webhook_server()

    print("\n" + "="*60)
    if all_ok:
        print("SUCCESS: All checks passed! Your setup looks good.")
        print("\nYou can now:")
        print("  - Run sync: python main.py sync")
        print("  - Start webhook server: python main.py webhook")
    else:
        print("ERROR: Some checks failed. Please fix the issues above.")
        print("\nCommon solutions:")
        print("  - Edit .env file with correct credentials")
        print("  - Check ERPs are running and accessible")
        print("  - Run: python main.py init (to initialize database)")
    print("="*60)


if __name__ == '__main__':
    main()
