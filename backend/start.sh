#!/bin/bash
# Quick start script for the AI Virtual Try-On service

echo "🚀 Starting AI Virtual Try-On Service..."
echo ""

# Check if virtual environment exists
VENV_DIR="venv"
if [ -d ".venv" ]; then
    VENV_DIR=".venv"
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source $VENV_DIR/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
fi

echo "✓ Environment activated"
echo ""
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

# Start the server
python -m app.main
