#!/bin/bash

# docker_setup.sh
# RUN THIS INSIDE THE CONTAINER
# Installs Python 3.8 dependencies needed for the vision stack.

set -e  # Exit on any error

echo "=========================================================="
echo "Setting up Vision Stack Dependencies (Inside Docker)"
echo "=========================================================="

# 1. Install System Build Dependencies
echo "Installing system build tools..."
apt-get update
apt-get install -y libusb-1.0-0-dev libzmq3-dev cmake build-essential libxml2-dev libxslt1-dev

# 2. Fix pip/setuptools
pip install "setuptools<65" "wheel"
pip install --upgrade pip

# 3. Install Dependencies 
echo "Installing pymavlink..."
pip install pymavlink

echo "Installing pyzmq..."
pip install pyzmq

echo "Installing other deps..."
pip install opencv-python-headless psutil pyyaml scipy pandas matplotlib tqdm

# 4. Install depthai from Luxonis Artifactory (PRE-BUILT WHEEL - NO COMPILATION!)
echo "Installing depthai from Luxonis pre-built wheels..."
pip install --extra-index-url https://artifacts.luxonis.com/artifactory/luxonis-python-snapshot-local/ depthai

# 5. Verify
echo "=========================================================="
echo "Verifying Installation..."
python3 -c "import torch; print(f'PyTorch: {torch.__version__} (CUDA: {torch.cuda.is_available()})')"
python3 -c "import ultralytics; print(f'Ultralytics: {ultralytics.__version__}')"
python3 -c "import depthai; print(f'DepthAI: {depthai.__version__}')"
python3 -c "import zmq; print(f'ZMQ: {zmq.__version__}')"

echo "=========================================================="
echo "Setup Complete! You can now run your code."
echo "Example: python3 -m src.main perception"
