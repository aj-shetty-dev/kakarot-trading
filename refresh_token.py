#!/usr/bin/env python3
"""
Quick script to refresh Upstox access token
"""
import requests
import json
from datetime import datetime

# Get these from your Upstox app
API_KEY = input("Enter API Key: ").strip()
API_SECRET = input("Enter API Secret: ").strip()
AUTH_CODE = input("Enter Auth Code from redirect URL: ").strip()

print("\n🔄 Refreshing Upstox access token...\n")

# Step 1: Exchange auth code for token
url = "https://api.upstox.com/v2/login/authorization/token"
headers = {"Accept": "application/json"}
data = {
    "code": AUTH_CODE,
    "client_id": API_KEY,
    "client_secret": API_SECRET,
    "redirect_uri": "https://localhost:8000/callback",
    "grant_type": "authorization_code"
}

try:
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    if response.status_code == 200 and "access_token" in result:
        access_token = result["access_token"]
        
        print("✅ Token refreshed successfully!\n")
        print("=" * 80)
        print(f"ACCESS_TOKEN: {access_token}")
        print("=" * 80)
        print("\nUpdate your .env file with:")
        print(f"UPSTOX_ACCESS_TOKEN={access_token}")
        print("\nThen restart the container:")
        print("docker-compose restart app")
        
    else:
        print(f"❌ Error: {result}")
        print(f"Status: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

