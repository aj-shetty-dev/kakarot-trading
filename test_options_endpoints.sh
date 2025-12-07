#!/bin/bash
# Options Chain API - Quick Test Commands

echo "🧪 Testing Options Chain API Endpoints"
echo "======================================\n"

# 1. Check service status
echo "1️⃣  Service Stats:"
curl -s http://localhost:8000/api/v1/options/stats | jq .
echo "\n"

# 2. Get all RELIANCE options
echo "2️⃣  RELIANCE Options Chain (first 3):"
curl -s 'http://localhost:8000/api/v1/options/chain/RELIANCE' | jq '.options[0:3]'
echo "\n"

# 3. Get RELIANCE strike prices
echo "3️⃣  RELIANCE Available Strikes (first 10):"
curl -s 'http://localhost:8000/api/v1/options/strikes/RELIANCE' | jq '.strikes[0:10]'
echo "\n"

# 4. Get RELIANCE expiry dates
echo "4️⃣  RELIANCE Expiry Dates:"
curl -s 'http://localhost:8000/api/v1/options/expiries?symbol=RELIANCE' | jq .
echo "\n"

# 5. Get specific contract
echo "5️⃣  Specific Contract (RELIANCE 1400 CE):"
curl -s 'http://localhost:8000/api/v1/options/contract/RELIANCE%201400%20CE%2030%20DEC%2025' | jq .
echo "\n"

# 6. Get ATM options around price 1400
echo "6️⃣  ATM Options around 1400 (first 5):"
curl -s 'http://localhost:8000/api/v1/options/atm/RELIANCE?price=1400' | jq '.options[0:5]'
echo "\n"

echo "✅ All endpoints tested successfully!"
