#!/bin/bash

IMAGE_NAME="shetta20/upstox-bot"
VERSION="v1"
OUTPUT_FILE="dist/upstox-bot-image.tar.gz"

echo "📦 Building local image from backend/..."
docker build -t $IMAGE_NAME:$VERSION backend/

echo "💾 Exporting image to $OUTPUT_FILE..."
mkdir -p dist
docker save $IMAGE_NAME:$VERSION | gzip > $OUTPUT_FILE

echo "✅ Done! The image is now inside the 'dist' folder."
echo "   You can now zip the 'dist' folder and send it."
echo "   Your friend will need to run 'docker load < upstox-bot-image.tar.gz' before starting."
