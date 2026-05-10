# Ubuntu Deployment Guide

## 1. Clone repository

```bash
git clone <your-repo-url> ai_try_on
cd ai_try_on
```

## 2. Create .env file

```bash
cp env.example .env
```

Edit `.env` with your settings:

```bash
nano .env
```

**Critical settings for Ubuntu:**
- `STORAGE_PATH=./storage` (or absolute path like `/data/ai_try_on/storage`)
- `DIFFUSION_DEVICE=cuda` if you have NVIDIA GPU
- `IDM_VTON_PATH=/app/IDM-VTON` (for Docker, adjust for local)

## 3. Install Docker + NVIDIA Container Toolkit

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install NVIDIA Container Toolkit (for GPU support)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## 4. Build and run with Docker

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 5. Access the application

- Frontend: http://<your-ubuntu-ip>:3000
- Backend API: http://<your-ubuntu-ip>:8000
- Health check: http://<your-ubuntu-ip>:8000/health

## 6. Stop services

```bash
docker-compose down
```

## Optional: Run locally without Docker

If you prefer to run Python directly:

```bash
# Install Python 3.10+
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# Create venv
python3.10 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run backend
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Note:** Local run requires manual setup of IDM-VTON models, DensePose, etc. Docker is recommended.
