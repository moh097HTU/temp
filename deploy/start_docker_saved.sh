#!/bin/bash

# start_docker_saved.sh
# Starts from your SAVED image (with all packages pre-installed).
# Run save_container.sh ONCE after initial setup to create this image.

IMAGE_NAME="vision-stack-ready"

echo "=========================================================="
echo "Starting Vision Stack Container (Pre-configured)"
echo "Image: $IMAGE_NAME"
echo "=========================================================="

# Check if saved image exists
if ! sudo docker image inspect $IMAGE_NAME &> /dev/null; then
    echo "[ERROR] Saved image '$IMAGE_NAME' not found!"
    echo ""
    echo "You need to create it first:"
    echo "  1. Run ./start_docker.sh"
    echo "  2. Install packages: apt-get update && apt-get install -y libxml2-dev libxslt1-dev libusb-1.0-0-dev"
    echo "  3. Install Python packages: pip install pyzmq pymavlink depthai==2.17.0"
    echo "  4. Open a NEW terminal, run: ./save_container.sh"
    echo "  5. Then you can use this script forever!"
    exit 1
fi

sudo docker run -it --rm --runtime nvidia --ipc=host --network host \
    --privileged \
    -v /dev/bus/usb:/dev/bus/usb \
    -v ~/temp:/workspace \
    -w /workspace \
    $IMAGE_NAME \
    bash
