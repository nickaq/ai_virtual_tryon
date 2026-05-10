#!/bin/bash
# Quick start script for Ubuntu

# 1. Clone repository (replace with your repo URL)
git clone <YOUR_REPO_URL> ai_try_on
cd ai_try_on

# 2. Create .env from template
cp env.example .env

# 3. (Optional) Edit .env with your settings
# nano .env

# 4. Install Docker (if not installed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# 5. Install NVIDIA Container Toolkit (for GPU support - optional)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 6. Build and run
docker-compose build
docker-compose up -d

# 7. Check logs
docker-compose logs -f
