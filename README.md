# ONE-TIME SETUP (Do this once)

# 1. SSH to Jetson
ssh albayrak@<jetson-ip>

# 2. Go to deploy folder
cd ~/temp/deploy

# 3. Pull latest code
git pull

# 4. Make scripts executable
chmod +x *.sh

# 5. Start the container
./start_docker.sh

# 6. INSIDE CONTAINER - Install system packages
apt-get update && apt-get install -y libxml2-dev libxslt1-dev libusb-1.0-0-dev

# 7. INSIDE CONTAINER - Install Python packages
pip install pyzmq pymavlink depthai==2.17.0

# 8. KEEP THIS TERMINAL OPEN - Don't exit yet!

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Terminal 2 - Save the Container:


# Open a NEW SSH session to Jetson
ssh albayrak@<jetson-ip>

# Save the container as image
cd ~/temp/deploy
./save_container.sh

# Done! You can close Terminal 1 now.


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++
# 1. SSH to Jetson
ssh albayrak@<jetson-ip>

# 2. Start from saved image
cd ~/temp/deploy
./start_docker_saved.sh

# 3. INSIDE CONTAINER - Run everything
cd /workspace/deploy
./run_all.sh
