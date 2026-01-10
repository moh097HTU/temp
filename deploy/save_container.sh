#!/bin/bash

# save_container.sh
# Run this OUTSIDE the container (on the Jetson host) while the container is running.
# This saves your configured container as a custom image.

CUSTOM_IMAGE_NAME="vision-stack-ready"

echo "=========================================================="
echo "Saving current container as image: $CUSTOM_IMAGE_NAME"
echo "=========================================================="

# Find the running container ID
CONTAINER_ID=$(sudo docker ps -q --filter ancestor=ultralytics/ultralytics:latest-jetson-jetpack4)

if [ -z "$CONTAINER_ID" ]; then
    echo "[ERROR] No running ultralytics container found!"
    echo "Make sure the container is running first."
    exit 1
fi

echo "Found container: $CONTAINER_ID"
echo "Committing..."

sudo docker commit $CONTAINER_ID $CUSTOM_IMAGE_NAME

echo "=========================================================="
echo "Done! Your custom image is saved as: $CUSTOM_IMAGE_NAME"
echo ""
echo "Next time, start with:"
echo "  ./start_docker_saved.sh"
echo "=========================================================="
