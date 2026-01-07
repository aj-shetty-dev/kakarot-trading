#!/bin/bash
# Script to run tests inside the Docker container

echo "🚀 Running tests inside Docker container..."

# Ensure the container is built
docker-compose build app

# Run pytest inside the app container
# We use 'run --rm' to start a fresh container and remove it after tests
docker-compose run --rm app python3 -m pytest tests/ -v

echo "✅ Test run complete."
