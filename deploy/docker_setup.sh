#!/bin/bash

# docker_setup.sh
# RUN THIS INSIDE THE CONTAINER
# Installs Python 3.8 dependencies needed for the vision stack.

echo "=========================================================="
echo "Setting up Vision Stack Dependencies (Inside Docker)"
echo "=========================================================="

# 1. Update pip & Fix Setuptools (Downgrade required for some ARM builds)
# The "canonicalize_version" error is due to incompatible setuptools/packaging versions.
pip install "setuptools<65" "wheel"
pip install --upgrade pip

# 1.5 Install System Build Dependencies (Required for lxml, depthai, etc)
echo "Installing system build tools..."
apt-get update
# Added libzmq3-dev (for pyzmq) and libusb-1.0-0-dev (for depthai)
apt-get install -y libxml2-dev libxslt1-dev cmake build-essential libopenblas-dev libzmq3-dev libusb-1.0-0-dev

# 2. Install Dependencies
# Ultralytics and PyTorch are ALREADY INSTALLED in this image.
# We just need the rest.

DEPENDENCIES=(
    "pymavlink"     # For communicating with Flight Controller
    "pyzmq"         # For Inter-Process Communication (IPC)
    "depthai"       # For OAK-D Camera
    "opencv-python-headless" # Standard OpenCV
    "psutil"        # System monitoring
    "pyyaml"        # Config files
    "scipy"         # Math
    "pandas"        # Data
    "matplotlib"    # Plotting
    "tqdm"          # Progress bars
)

echo "Installing: ${DEPENDENCIES[@]}"
pip install "${DEPENDENCIES[@]}"

# 3. Verify
echo "=========================================================="
echo "Verifying Installation..."
python3 -c "import torch; print(f'PyTorch: {torch.__version__} (CUDA: {torch.cuda.is_available()})')"
python3 -c "import ultralytics; print(f'Ultralytics: {ultralytics.__version__}')"
python3 -c "import depthai; print(f'DepthAI: {depthai.__version__}')"

echo "=========================================================="
echo "Setup Complete! You can now run your code."
echo "Example: python3 -m src.main perception"
