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
# We use PyTorch 1.8.0 which is compatible with JetPack 4.6 (Ubuntu 18.04) libraries like libmpi
echo "[2/5] Downloading and installing PyTorch 1.8.0 & Torchvision 0.9.0..."
mkdir -p build_temp
cd build_temp

# Install gdown to download from Google Drive
python3.8 -m pip install gdown

# 1.5 Install OpenMPI 4.0.3 (Required for PyTorch 1.12+ on Ubuntu 18.04)
# JetPack 4.6 (Ubuntu 18.04) has old OpenMPI, so we build the newer version.
echo "[1.5/5] Building OpenMPI 4.0.3..."
if [ ! -f "/usr/local/lib/libmpi_cxx.so.40" ]; then
    wget https://download.open-mpi.org/release/open-mpi/v4.0/openmpi-4.0.3.tar.gz
    tar xf openmpi-4.0.3.tar.gz
    cd openmpi-4.0.3
    ./configure --prefix=/usr/local
    make -j4
    sudo make install
    sudo ldconfig
    cd ..
    rm -rf openmpi-4.0.3 openmpi-4.0.3.tar.gz
    
    # Add to LD_LIBRARY_PATH
    echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
    export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
else
    echo "OpenMPI 4.0.3 seems to be installed."
    export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
fi

# 2. Install PyTorch & Torchvision for Jetson Nano (Python 3.8 + aarch64)
# Source: QEngineering/PyTorch-Jetson-Nano (Hosted on Google Drive)
echo "[2/5] Downloading and installing PyTorch 1.12.0 & Torchvision 0.13.0..."
mkdir -p build_temp
cd build_temp

# Install gdown to download from Google Drive
python3.8 -m pip install gdown

# 2. Install PyTorch & Torchvision for Jetson Nano (Python 3.8 + aarch64)
# Source: KumaTea (verified compatible wheels for older GLIBC)
# We use PyTorch 1.8.1 and Torchvision 0.9.1
echo "[2/5] Installing PyTorch 1.8.1 & Torchvision 0.9.1..."

# Convert the html to a package index url format if possible, or just download wheels directly.
# The URL `https://torch.kmtea.eu/whl/stable.html` is an index.
# We will use `--extra-index-url` to install.

# Note: numpy<2 is needed.
python3.8 -m pip install "numpy<1.24" 

echo "Installing PyTorch 1.8.1 from KumaTea..."
python3.8 -m pip install torch==1.8.1 torchvision==0.9.1 --extra-index-url https://torch.kmtea.eu/whl/stable-cn.html

# Fallback: if index fails, we can wget the file, but index is cleaner.
# URL structure for KumaTea seems to be: https://torch.kmtea.eu/whl/stable-cn/torch-1.8.1-cp38-cp38-linux_aarch64.whl
# Let's try downloading directly if pip fails, to be robust.

if ! python3.8 -c "import torch" 2>/dev/null; then
    echo "Direct pip install failed, trying wget..."
    wget https://torch.kmtea.eu/whl/stable-cn/torch-1.8.1-cp38-cp38-linux_aarch64.whl
    python3.8 -m pip install torch-1.8.1-cp38-cp38-linux_aarch64.whl
    
    wget https://torch.kmtea.eu/whl/stable-cn/torchvision-0.9.1-cp38-cp38-linux_aarch64.whl
    python3.8 -m pip install torchvision-0.9.1-cp38-cp38-linux_aarch64.whl
fi

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
