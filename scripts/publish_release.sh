#!/bin/bash

# Configuration
IMAGE_NAME="shetta20/upstox-bot"
VERSION="v1"

echo "🚀 Preparing to publish $IMAGE_NAME:$VERSION..."

# 1. Build the image for linux/amd64 (standard for servers/cloud) and local architecture
# Using buildx for multi-platform support if available, otherwise standard build
if docker buildx version > /dev/null 2>&1; then
    echo "📦 Building with Docker Buildx..."
    docker buildx build --platform linux/amd64,linux/arm64 -t $IMAGE_NAME:$VERSION -t $IMAGE_NAME:latest --push backend/
else
    echo "⚠️  Docker Buildx not found. Building standard image..."
    docker build -t $IMAGE_NAME:$VERSION backend/
    docker tag $IMAGE_NAME:$VERSION $IMAGE_NAME:latest
    
    echo "⬆️  Pushing to Docker Hub..."
    docker push $IMAGE_NAME:$VERSION
    docker push $IMAGE_NAME:latest
fi

echo "✅ Done! Your friend can now run the bot using the 'dist' folder."
echo "   Image: $IMAGE_NAME:$VERSION"
