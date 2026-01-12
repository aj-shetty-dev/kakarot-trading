#!/bin/bash

# Kakarot Trading Bot - Production Wrapper
# Use this to manage your data collection bot

# Colors for better visibility
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 Kakarot Data Collection Bot${NC}"
echo "=============================="

# Check for .env file
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found.${NC}"
    if [ -f .env.example ]; then
        echo "Creating .env from template. Please edit it with your credentials."
        cp .env.example .env
        echo -e "${RED}Please edit the .env file and run this script again.${NC}"
        exit 1
    else
        echo -e "${RED}❌ Error: No .env or .env.example found.${NC}"
        exit 1
    fi
fi

# Function to show status
show_status() {
    echo -e "\n${BLUE}📊 Current Service Status:${NC}"
    docker compose ps
    echo -e "\n${GREEN}🔗 Access Points:${NC}"
    echo "  - Dashboard: http://localhost:8502"
    echo "  - API Docs: http://localhost:8001/docs"
}

case "$1" in
    start)
        echo -e "${GREEN}Starting Kakarot services...${NC}"
        docker compose pull
        docker compose up -d
        echo -e "${YELLOW}Waiting for database health check...${NC}"
        sleep 5
        show_status
        ;;
    stop)
        echo -e "${YELLOW}Stopping Kakarot services...${NC}"
        docker compose stop
        ;;
    down)
        echo -e "${RED}Removing Kakarot containers and network...${NC}"
        docker compose down
        ;;
    logs)
        docker compose logs -f app
        ;;
    restart)
        echo -e "${GREEN}Restarting Kakarot services...${NC}"
        docker compose restart
        show_status
        ;;
    *)
        echo "Usage: ./kakarot.sh {start|stop|restart|down|logs}"
        echo ""
        echo "  start   : Pull latest images and start services"
        echo "  stop    : Stop running containers"
        echo "  restart : Restart services to apply .env changes"
        echo "  down    : Stop and remove containers completely"
        echo "  logs    : View live bot logs"
        exit 1
        ;;
esac
