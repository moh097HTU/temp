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

# 2. Install PyTorch for Jetson Nano (Python 3.8 + aarch64)
# We use a pre-built wheel compatible with JetPack 4.6 (CUDA 10.2 capability)
# Source: QEngineering/PyTorch-Jetson-Nano
echo "[2/5] Downloading and installing PyTorch 1.13.0..."
mkdir -p build_temp
cd build_temp

# URL for PyTorch 1.13.0 wheel for Python 3.8 (aarch64)
TORCH_WHEEL_URL="https://github.com/Qengineering/PyTorch-Jetson-Nano/raw/main/torch-1.13.0a0+d0d6b1f2.nv22.10-cp38-cp38-linux_aarch64.whl"

if [ ! -f "torch-1.13.0-cp38.whl" ]; then
    wget -O torch-1.13.0-cp38.whl "$TORCH_WHEEL_URL"
fi

python3.8 -m pip install torch-1.13.0-cp38.whl

# 3. Install Torchvision
# We need to compile torchvision 0.14.0 from source to match PyTorch 1.13.0
echo "[3/5] Installing Torchvision 0.14.0 (Compiling from source)..."
if [ -d "vision" ]; then
    rm -rf vision
fi
git clone --branch v0.14.0 https://github.com/pytorch/vision torchvision_repo
cd torchvision_repo
export BUILD_VERSION=0.14.0
python3.8 setup.py install --user
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
