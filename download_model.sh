#!/bin/bash
# Download the LLM model for Mira
# Qwen 2.5 1.5B Instruct (Q4_K_M quantization, ~1.1GB)

MODEL_DIR="./models"
MODEL_FILE="qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/${MODEL_FILE}"

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_DIR/$MODEL_FILE" ]; then
    echo "Model already exists: $MODEL_DIR/$MODEL_FILE"
    echo "Delete it first if you want to re-download."
    exit 0
fi

echo "Downloading $MODEL_FILE (~1.1 GB)..."
echo "From: $MODEL_URL"
echo ""

if command -v curl &> /dev/null; then
    curl -L --progress-bar -o "$MODEL_DIR/$MODEL_FILE" "$MODEL_URL"
elif command -v wget &> /dev/null; then
    wget --show-progress -O "$MODEL_DIR/$MODEL_FILE" "$MODEL_URL"
else
    echo "Error: curl or wget required"
    exit 1
fi

if [ -f "$MODEL_DIR/$MODEL_FILE" ]; then
    SIZE=$(stat --format=%s "$MODEL_DIR/$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_DIR/$MODEL_FILE" 2>/dev/null)
    echo ""
    echo "Download complete: $MODEL_DIR/$MODEL_FILE ($SIZE bytes)"
else
    echo "Download failed!"
    exit 1
fi
