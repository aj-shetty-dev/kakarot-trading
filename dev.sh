#!/bin/bash

# Kakarot Trading Bot - Development Start Script
# Usage: ./dev.sh

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Kakarot Trading Bot...${NC}"

# 1. Check for .env file
if [ ! -f "backend/.env" ]; then
    echo -e "${RED}❌ Error: backend/.env file not found!${NC}"
    echo "Please create backend/.env with your Upstox credentials."
    echo "Example:"
    echo "upstox_api_key=your_key"
    echo "upstox_api_secret=your_secret"
    echo "upstox_access_token=your_token"
    exit 1
fi

# 2. Check for config.json
if [ ! -f "backend/config.json" ]; then
    echo -e "${YELLOW}⚠️  Warning: backend/config.json not found.${NC}"
    echo "Using default configuration."
fi

# 3. Create logs directory if it doesn't exist
mkdir -p backend/logs

# 4. Start Docker Containers
echo -e "${YELLOW}🐳 Starting Docker containers...${NC}"
docker-compose up -d --build

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Application started successfully!${NC}"
    echo ""
    echo "📊 Dashboard: http://localhost:8501"
    echo "📝 Logs:      tail -f backend/logs/$(date +%Y-%m-%d)/trading.log"
    echo ""
    echo "To stop the application, run: docker-compose down"
else
    echo -e "${RED}❌ Failed to start Docker containers.${NC}"
    exit 1
fi
