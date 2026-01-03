#!/bin/bash

# Upstox Trading Bot - Setup Script
# This script sets up the entire environment for local development and testing

set -e

echo "🚀 Upstox Trading Bot - Setup Script"
echo "===================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Docker is installed"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

echo "✅ Docker Compose is installed"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

echo "📦 Building Docker images..."
docker-compose build

echo ""
echo "🗄️  Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

echo ""
echo "✅ Services started!"
echo ""
echo "📊 Service Status:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo "  - API: http://localhost:8000"
echo ""
echo "📚 Documentation:"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - ReDoc: http://localhost:8000/redoc"
echo ""
echo "🔧 Useful Commands:"
echo "  - View logs: docker-compose logs -f app"
echo "  - Stop services: docker-compose down"
echo "  - Database shell: docker-compose exec postgres psql -U upstox_user -d upstox_trading"
echo ""
echo "✨ Setup complete! Happy trading! 🎯"
