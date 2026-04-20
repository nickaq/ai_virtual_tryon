#!/bin/bash
# Setup script for IDM-VTON model and preprocessing checkpoints
# Run this inside the Docker container or on the server

set -e

IDM_VTON_DIR="${IDM_VTON_PATH:-/app/IDM-VTON}"
CKPT_DIR="$IDM_VTON_DIR/ckpt"

echo "=== Setting up IDM-VTON ==="

# 1. Clone IDM-VTON if not present
if [ ! -d "$IDM_VTON_DIR/src" ]; then
    echo "Cloning IDM-VTON repository..."
    git clone --depth 1 https://github.com/yisol/IDM-VTON.git "$IDM_VTON_DIR"
else
    echo "IDM-VTON already cloned at $IDM_VTON_DIR"
fi

# 2. Download preprocessing checkpoints
echo "Downloading preprocessing checkpoints..."

# DensePose model
mkdir -p "$CKPT_DIR/densepose"
if [ ! -f "$CKPT_DIR/densepose/model_final_162be9.pkl" ]; then
    echo "  Downloading DensePose model..."
    wget -q --show-progress -O "$CKPT_DIR/densepose/model_final_162be9.pkl" \
        "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/ckpt/densepose/model_final_162be9.pkl"
fi

# Human parsing ONNX models
mkdir -p "$CKPT_DIR/humanparsing"
if [ ! -f "$CKPT_DIR/humanparsing/parsing_atr.onnx" ]; then
    echo "  Downloading human parsing models..."
    wget -q --show-progress -O "$CKPT_DIR/humanparsing/parsing_atr.onnx" \
        "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/ckpt/humanparsing/parsing_atr.onnx"
    wget -q --show-progress -O "$CKPT_DIR/humanparsing/parsing_lip.onnx" \
        "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/ckpt/humanparsing/parsing_lip.onnx"
fi

# OpenPose body model
mkdir -p "$CKPT_DIR/openpose/ckpts"
if [ ! -f "$CKPT_DIR/openpose/ckpts/body_pose_model.pth" ]; then
    echo "  Downloading OpenPose model..."
    wget -q --show-progress -O "$CKPT_DIR/openpose/ckpts/body_pose_model.pth" \
        "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/ckpt/openpose/ckpts/body_pose_model.pth"
fi

echo "=== IDM-VTON setup complete ==="
echo "Checkpoints directory: $CKPT_DIR"
ls -la "$CKPT_DIR/densepose/" "$CKPT_DIR/humanparsing/" "$CKPT_DIR/openpose/ckpts/"
