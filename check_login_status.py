import requests
import json

def check_login_status():
    """Check current login status"""
    try:
        # Check auth status
        response = requests.get('http://localhost:8000/api/auth/check')
        print(f"Auth check response: {response.status_code}")

        if response.status_code == 200:
            auth_data = response.json()
            print(f"Auth status: {json.dumps(auth_data, indent=2, ensure_ascii=False)}")
        else:
            print(f"Auth check failed: {response.text}")

        # Check session cookie
        session = requests.Session()
        response = session.get('http://localhost:8000/api/auth/check')
        print(f"\nWith session - Auth check response: {response.status_code}")

        if response.status_code == 200:
            auth_data = response.json()
            print(f"Session auth status: {json.dumps(auth_data, indent=2, ensure_ascii=False)}")
        else:
            print(f"Session auth check failed: {response.text}")

        # Check cookies
        print(f"\nCookies in session: {dict(session.cookies)}")

        # Try accessing a protected API
        print("\n" + "="*50)
        print("TESTING PROTECTED API ACCESS")
        print("="*50)

        response = session.get('http://localhost:8000/api/global-master-templates')
        print(f"Templates API response: {response.status_code}")

        if response.status_code == 200:
            templates = response.json()
            print(f"Successfully got {len(templates)} templates")
        else:
            print(f"Failed to get templates: {response.text}")

        # Try accessing another protected endpoint
        response = session.get('http://localhost:8000/api/user/profile')
        print(f"\nUser profile API response: {response.status_code}")

        if response.status_code == 200:
            profile = response.json()
            print(f"User profile: {json.dumps(profile, indent=2, ensure_ascii=False)}")
        else:
            print(f"Failed to get user profile: {response.text}")

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_login_status()
