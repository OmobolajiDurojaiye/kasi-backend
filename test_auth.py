import requests

BASE_URL = "http://127.0.0.1:5001/api/auth"

def test_register():
    print("Testing Registration...")
    response = requests.post(f"{BASE_URL}/register", json={
        "business_name": "Test Biz",
        "email": "test@test.com",
        "password": "password123"
    })
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code in [201, 400] # 400 if already exists

def test_login():
    print("\nTesting Login...")
    response = requests.post(f"{BASE_URL}/login", json={
        "email": "test@test.com",
        "password": "password123"
    })
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    if response.status_code == 200:
        return response.json()['access_token']
    return None

def test_me(token):
    print("\nTesting Me Endpoint...")
    response = requests.get(f"{BASE_URL}/me", headers={
        "Authorization": f"Bearer {token}"
    })
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    if test_register():
        token = test_login()
        if token:
            test_me(token)
