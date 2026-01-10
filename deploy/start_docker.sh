#!/bin/bash

# start_docker.sh
# Launches the Ultralytics YOLOv8 container on Jetson Nano (JetPack 4.6)
# with CUDA support, USB camera access, and network access.

IMAGE_NAME="ultralytics/ultralytics:latest-jetson-jetpack4"

echo "=========================================================="
echo "Starting Ultralytics Docker Container for Jetson Nano"
echo "Image: $IMAGE_NAME"
echo "=========================================================="

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    sudo usermod -aG docker $USER
    echo "Docker installed. Please re-login for group changes to take effect."
fi

# Pull the image if not present
echo "Pulling latest image (this may take a while first time)..."
sudo docker pull $IMAGE_NAME

# Run the container
# --runtime nvidia: Enables CUDA access
# --network host: Allows Mavlink/ZMQ communication with host processes
# --ipc=host: Prevents shared memory issues with PyTorch loaders
# -v ~/temp/vision_stack:/workspace: Mounts your code directory to /workspace inside
# --device /dev/video0: Passes the USB camera
# --privileged: Ensures full hardware access (GPIO, Serial, etc)

echo "Launching container..."
echo "Your code will be mounted at: /workspace"
echo ""
echo "IMPORTANT: After entering, run these commands ONCE:"
echo "  pip install pyzmq pymavlink depthai==2.17.0"
echo "  cd vision_stack"
echo "  python3 -m src.main perception"
echo ""

sudo docker run -it --rm --runtime nvidia --ipc=host --network host \
    --privileged \
    -v /dev/bus/usb:/dev/bus/usb \
    -v ~/temp:/workspace \
    -w /workspace \
    $IMAGE_NAME \
    bash

# Note: The volume mount $(pwd)/../.. assumes this script is run from ~/temp/vision_stack/deploy
# and mounts ~/temp/vision_stack (the project root) to /workspace.
