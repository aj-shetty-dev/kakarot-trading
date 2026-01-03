#!/bin/bash

# Define paths
PROJECT_ROOT=$(pwd)
DIST_DIR="$PROJECT_ROOT/dist"
PACKAGE_NAME="upstox-trading-bot"
PACKAGE_DIR="$DIST_DIR/$PACKAGE_NAME"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}📦 Creating distribution package...${NC}"

# 1. Clean and Create Directories
rm -rf "$DIST_DIR"
mkdir -p "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR/logs"

# 2. Copy Docker Compose (Using the Docker Hub version)
echo "   Creating Docker Compose configuration..."
cat > "$PACKAGE_DIR/docker-compose.yml" << 'INNER_EOF'
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: upstox_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-upstox_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-upstox_password}
      POSTGRES_DB: ${POSTGRES_DB:-upstox_trading}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-upstox_user} -d ${POSTGRES_DB:-upstox_trading}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - upstox_network

  redis:
    image: redis:7-alpine
    container_name: upstox_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - upstox_network

  app:
    image: shetta20/upstox-bot:latest
    container_name: upstox_trading_bot
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-upstox_user}:${POSTGRES_PASSWORD:-upstox_password}@postgres:5432/${POSTGRES_DB:-upstox_trading}
      REDIS_URL: redis://redis:6379
      TZ: Asia/Kolkata
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - upstox_network

  dashboard:
    image: shetta20/upstox-bot:latest
    container_name: upstox_dashboard
    env_file:
      - .env
    environment:
      API_URL: http://app:8000/api/v1/monitoring
      TZ: Asia/Kolkata
    ports:
      - "8501:8501"
    depends_on:
      - app
    volumes:
      - ./logs:/app/logs
    command: streamlit run src/monitoring/dashboard.py --server.port 8501 --server.address 0.0.0.0
    networks:
      - upstox_network

volumes:
  postgres_data:
  redis_data:

networks:
  upstox_network:
    driver: bridge
INNER_EOF

# 3. Create env.template (Visible file)
echo "   Creating configuration templates..."
cat > "$PACKAGE_DIR/env.template" << 'INNER_EOF'
# ==========================================
# UPSTOX TRADING BOT CONFIGURATION
# ==========================================

# 1. UPSTOX API CREDENTIALS
UPSTOX_API_KEY=your_api_key_here
UPSTOX_API_SECRET=your_api_secret_here
UPSTOX_ACCESS_TOKEN=your_daily_access_token_here
UPSTOX_CLIENT_CODE=your_client_code_here

# 2. DATABASE SETTINGS
POSTGRES_USER=upstox_user
POSTGRES_PASSWORD=upstox_password
POSTGRES_DB=upstox_trading

# 3. APPLICATION SETTINGS
ENVIRONMENT=production
LOG_LEVEL=INFO
AUTO_START_STOP=true

# 4. NOTIFICATIONS
ENABLE_NOTIFICATIONS=true
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
INNER_EOF

# 4. Create Start Script
echo "   Creating start script..."
cat > "$PACKAGE_DIR/start.sh" << 'INNER_EOF'
#!/bin/bash
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting Upstox Trading Bot...${NC}"

# Check for .env, if missing try to create from template
if [ ! -f ".env" ]; then
    if [ -f "env.template" ]; then
        echo "📝 Creating .env from template..."
        cp env.template .env
        echo -e "${RED}⚠️  Please edit the '.env' file with your credentials and run this script again.${NC}"
        exit 1
    else
        echo -e "${RED}❌ Error: Neither .env nor env.template found!${NC}"
        exit 1
    fi
fi

# Check if user actually filled in the credentials
if grep -q "your_api_key_here" ".env"; then
    echo -e "${RED}⚠️  Please edit '.env' and add your Upstox API credentials first!${NC}"
    exit 1
fi

# Create logs directory if missing
mkdir -p logs

# Pull latest images and start
echo -e "${GREEN}📡 Pulling latest images from Docker Hub...${NC}"
docker compose pull

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to pull images. Please check your internet connection.${NC}"
    exit 1
fi

echo -e "${GREEN}🐳 Starting containers...${NC}"
docker compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Bot is running!${NC}"
    echo "   📊 Dashboard: http://localhost:8501"
    echo "   📝 Logs:      docker compose logs -f app"
else
    echo -e "${RED}❌ Error: Failed to start containers.${NC}"
    exit 1
fi
INNER_EOF
chmod +x "$PACKAGE_DIR/start.sh"

# 5. Create README
cat > "$PACKAGE_DIR/README.md" << 'INNER_EOF'
# Upstox Trading Bot

## Installation
1. **Install Docker Desktop**: Ensure Docker is installed and running.
2. **Configure**: 
   - You will see a file named `env.template`.
   - Rename it to `.env` (or just run `./start.sh` and it will create it for you).
   - Open `.env` and paste your Upstox API Key, Secret, and Access Token.
3. **Run**: Execute the start script:
   ```bash
   ./start.sh
   ```

## Access
- **Dashboard**: [http://localhost:8501](http://localhost:8501)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
INNER_EOF

# 6. Zip the package
echo "   Zipping package..."
cd "$DIST_DIR"
zip -r "$PACKAGE_NAME.zip" "$PACKAGE_NAME" > /dev/null
cd "$PROJECT_ROOT"

echo -e "${GREEN}✅ Distribution package created at: dist/$PACKAGE_NAME.zip${NC}"
echo "   You can send this zip file to your friend."
