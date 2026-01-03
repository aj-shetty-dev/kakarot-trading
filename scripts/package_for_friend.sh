#!/bin/bash

# Package Project for Distribution
# This script creates a 'dist' folder with everything needed to run the bot on another machine.

DIST_DIR="dist"
IMAGE_NAME="shetta20/upstox-bot"
VERSION="v1"

echo "🧹 Cleaning old dist folder..."
rm -rf $DIST_DIR
mkdir -p $DIST_DIR/logs

# 1. Build and Export Docker Image
echo "📦 Building Docker image..."
docker build -t $IMAGE_NAME:$VERSION ./backend

echo "💾 Exporting Docker image (this may take a minute)..."
docker save $IMAGE_NAME:$VERSION | gzip > $DIST_DIR/upstox-bot-image.tar.gz

# 2. Copy Docker Compose
echo "📄 Copying Docker Compose configuration..."
cp docker-compose.dist.yml $DIST_DIR/docker-compose.yml

# 3. Create a clean .env template
echo "📝 Creating .env template..."
cat > $DIST_DIR/.env << EOF
# Upstox API Credentials
UPSTOX_API_KEY=
UPSTOX_API_SECRET=
UPSTOX_ACCESS_TOKEN=
UPSTOX_CLIENT_CODE=

# Database Configuration
POSTGRES_USER=upstox_user
POSTGRES_PASSWORD=upstox_password
POSTGRES_DB=upstox_trading

# Application Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_NOTIFICATIONS=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EOF

# 4. Create a simplified start script for the friend
echo "🚀 Creating start script..."
cat > $DIST_DIR/start.sh << 'EOF'
#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Initializing Upstox Trading Bot...${NC}"

# 1. Check if image is loaded
if [[ "$(docker images -q shetta20/upstox-bot:v1 2> /dev/null)" == "" ]]; then
    echo -e "${YELLOW}📦 Loading Docker image from tarball...${NC}"
    docker load < upstox-bot-image.tar.gz
fi

# 2. Check for .env
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found!${NC}"
    echo "Please fill in your credentials in the .env file."
    exit 1
fi

# 3. Create logs dir
mkdir -p logs

# 4. Start
echo -e "${YELLOW}🐳 Starting containers...${NC}"
docker-compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Application started successfully!${NC}"
    echo "📊 Dashboard: http://localhost:8501"
    echo "To stop: docker-compose down"
else
    echo -e "${RED}❌ Failed to start.${NC}"
fi
EOF

chmod +x $DIST_DIR/start.sh

# 5. Create README
echo "📖 Creating README..."
cat > $DIST_DIR/README.md << EOF
# Upstox Trading Bot - Installation Guide

## Prerequisites
- Docker and Docker Compose installed.

## Setup Instructions
1. **Extract** this folder.
2. **Edit the \`.env\` file** and add your Upstox API credentials and Telegram details.
3. **Run the start script**:
   \`\`\`bash
   ./start.sh
   \`\`\`
4. **Access the Dashboard**:
   Open [http://localhost:8501](http://localhost:8501) in your browser.

## Troubleshooting
- If the start script fails, ensure Docker is running.
- Check logs in the \`logs/\` folder.
EOF

echo "✅ Done! Everything is packaged in the '$DIST_DIR' folder."
echo "   You can now zip the '$DIST_DIR' folder and share it with your friend."
