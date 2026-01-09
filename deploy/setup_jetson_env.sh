#!/bin/bash
set -e

# setup_jetson_env.sh
# Purpose: Set up Python 3.8 environment on Jetson Nano (JetPack 4.6) for Ultralytics/YOLOv8 support.
# Author: Drone Vision Agent

echo "=========================================================="
echo "Starting Jetson Nano Environment Setup (Python 3.8)"
echo "Target: JetPack 4.6 (L4T 32.6.1)"
echo "=========================================================="

# 1. Install system dependencies and Python 3.8
echo "[1/5] Installing Python 3.8 and system libraries..."
sudo apt-get update
sudo apt-get install -y python3.8 python3.8-dev python3.8-venv python3-pip
sudo apt-get install -y build-essential libopenblas-base libopenmpi-dev libjpeg-dev zlib1g-dev

# Update pip for Python 3.8
python3.8 -m pip install --upgrade pip

# 2. Install PyTorch & Torchvision for Jetson Nano (Python 3.8 + aarch64)
# Source: QEngineering/PyTorch-Jetson-Nano (Hosted on Google Drive)
echo "[2/5] Downloading and installing PyTorch 1.13.0 & Torchvision 0.14.0..."
mkdir -p build_temp
cd build_temp

# Install gdown to download from Google Drive
python3.8 -m pip install gdown

# Download PyTorch 1.13.0
# ID: 1MnVB7I4N8iVDAkogJO76CiQ2KRbyXH_e -> torch-1.13.0a0+git7c98e70-cp38-cp38-linux_aarch64.whl
echo "Downloading PyTorch..."
gdown 1MnVB7I4N8iVDAkogJO76CiQ2KRbyXH_e
# Since gdown might save with the original filename or "Unknown", we find the .whl
TORCH_WHEEL=$(find . -maxdepth 1 -name "torch*.whl" | head -n 1)
python3.8 -m pip install "$TORCH_WHEEL"

# Download Torchvision 0.14.0
# ID: 19UbYsKHhKnyeJ12VPUwcSvoxJaX7jQZ2 -> torchvision-0.14.0a0+5ce4506-cp38-cp38-linux_aarch64.whl
echo "Downloading Torchvision..."
gdown 19UbYsKHhKnyeJ12VPUwcSvoxJaX7jQZ2
VISION_WHEEL=$(find . -maxdepth 1 -name "torchvision*.whl" | head -n 1)
python3.8 -m pip install "$VISION_WHEEL"

echo "PyTorch and Torchvision installed."
cd ..


# 4. Install Ultralytics and Project Dependencies
echo "[4/5] Installing Ultralytics and other dependencies..."
# Upgrade numpy first as it can be tricky on aarch64
python3.8 -m pip install --upgrade numpy

# Install Ultralytics (YOLOv8)
# We exclude torch/torchvision from deps to prevent pip from overwriting our custom installs
python3.8 -m pip install ultralytics --no-deps

# Install common dependencies needed for ultralytics and the vision stack
python3.8 -m pip install matplotlib>=3.2.2 pandas>=1.1.4 scipy>=1.4.1 tqdm>=4.64.0 pyyaml>=5.3.1 seaborn>=0.11.0 psutil
python3.8 -m pip install depthai opencv-python-headless pymavlink pyzmq

# 5. Cleanup
cd ..
rm -rf build_temp
echo "=========================================================="
echo "Setup Complete!"
echo "Use 'python3.8' to run your scripts."
echo "Example: python3.8 vision_stack/src/main.py"
echo "=========================================================="
