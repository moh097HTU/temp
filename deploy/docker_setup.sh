#!/bin/bash

# docker_setup.sh
# RUN THIS INSIDE THE CONTAINER
# Installs Python 3.8 dependencies needed for the vision stack.

set -e  # Exit on any error

echo "=========================================================="
echo "Setting up Vision Stack Dependencies (Inside Docker)"
echo "=========================================================="

# 1. Install System Build Dependencies FIRST
echo "Installing system build tools..."
apt-get update
apt-get install -y software-properties-common

# Upgrade GCC to 9 (Required for depthai C++17 <filesystem> support)
add-apt-repository -y ppa:ubuntu-toolchain-r/test
apt-get update
apt-get install -y gcc-9 g++-9 libstdc++-9-dev

# Force system to use GCC 9
update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-9 100 --slave /usr/bin/g++ g++ /usr/bin/g++-9
update-alternatives --install /usr/bin/cc cc /usr/bin/gcc-9 100
update-alternatives --install /usr/bin/c++ c++ /usr/bin/g++-9 100

# CRITICAL: Export CC and CXX so CMake picks them up
export CC=/usr/bin/gcc-9
export CXX=/usr/bin/g++-9

echo "Compiler version:"
gcc --version | head -1
g++ --version | head -1

# Install other dependencies
apt-get install -y libxml2-dev libxslt1-dev cmake build-essential libopenblas-dev libzmq3-dev libusb-1.0-0-dev

# 2. CRITICAL: Clear ALL cached builds that used the old compiler
echo "Clearing cached builds..."
rm -rf ~/.hunter
rm -rf ~/.cache/pip
pip cache purge || true

# 3. Fix pip/setuptools
pip install "setuptools<65" "wheel"
pip install --upgrade pip

# 4. Install Dependencies one by one to isolate failures
echo "Installing pymavlink..."
pip install pymavlink

echo "Installing pyzmq..."
pip install pyzmq

echo "Installing other deps..."
pip install opencv-python-headless psutil pyyaml scipy pandas matplotlib tqdm

# 5. Install depthai LAST (it's the problematic one)
echo "Installing depthai (this will take a while to compile)..."
CC=/usr/bin/gcc-9 CXX=/usr/bin/g++-9 pip install --no-cache-dir depthai

# 6. Verify
echo "=========================================================="
echo "Verifying Installation..."
python3 -c "import torch; print(f'PyTorch: {torch.__version__} (CUDA: {torch.cuda.is_available()})')"
python3 -c "import ultralytics; print(f'Ultralytics: {ultralytics.__version__}')"
python3 -c "import depthai; print(f'DepthAI: {depthai.__version__}')"
python3 -c "import zmq; print(f'ZMQ: {zmq.__version__}')"

echo "=========================================================="
echo "Setup Complete! You can now run your code."
echo "Example: python3 -m src.main perception"
