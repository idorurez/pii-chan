#!/bin/bash
# 🐣 ミラ Setup Script

set -e

echo "🐣 Setting up ミラ (Mira)..."
echo

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create directories
mkdir -p models data assets/faces

# Copy config if doesn't exist
if [ ! -f "config.yaml" ]; then
    echo "Creating config.yaml from example..."
    cp config.example.yaml config.yaml
fi

echo
echo "✅ Setup complete!"
echo
echo "Next steps:"
echo "  1. Download a model (see docs/MODEL_SETUP.md)"
echo "     Quick: wget -O models/qwen2.5-1.5b-instruct-q4_k_m.gguf \\"
echo "            'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf'"
echo
echo "  2. (Optional) Install VOICEVOX for voice output"
echo "     See docs/VOICEVOX_SETUP.md"
echo
echo "  3. Run the simulator:"
echo "     source venv/bin/activate"
echo "     python -m src.main --simulator"
echo
echo "  4. Or run in text mode:"
echo "     python -m src.main --simulate --no-model"
echo
