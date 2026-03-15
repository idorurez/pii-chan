# Model Setup

Mira uses a local LLM for generating responses. The recommended model is **Qwen 2.5 1.5B Instruct** - it's small enough to run on a Raspberry Pi 5 but capable enough for natural Japanese conversation.

## Quick Setup

### Option 1: Download with script

```bash
# Create models directory
mkdir -p models

# Download Qwen 2.5 1.5B (Q4_K_M quantization, ~1GB)
wget -O models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
```

### Option 2: Manual download

1. Go to: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
2. Download `qwen2.5-1.5b-instruct-q4_k_m.gguf`
3. Place in `./models/` directory

## Model Options

| Model | Size | RAM | Speed (Pi 5) | Quality |
|-------|------|-----|--------------|---------|
| Qwen 2.5 0.5B | ~400MB | 1GB | ~0.5s | Okay |
| **Qwen 2.5 1.5B** | ~1GB | 2GB | ~1-2s | Good ✓ |
| Qwen 2.5 3B | ~2GB | 4GB | ~3-5s | Better |
| Phi-3 Mini | ~2.5GB | 4GB | ~3-4s | Good |

**Recommended:** Qwen 2.5 1.5B for balance of speed and quality.

## Quantization Formats

- **Q4_K_M** - Best balance of quality/size (recommended)
- **Q5_K_M** - Slightly better quality, larger
- **Q8_0** - Near-original quality, much larger

## Testing

After downloading, test the model:

```bash
# Activate venv
source venv/bin/activate

# Test inference
python -c "
from llama_cpp import Llama
llm = Llama(model_path='./models/qwen2.5-1.5b-instruct-q4_k_m.gguf', n_ctx=2048)
response = llm('こんにちは！', max_tokens=50)
print(response['choices'][0]['text'])
"
```

## No Model Mode

If you don't have a model, Mira will use simple rule-based responses:

```bash
python -m src.main --simulate --no-model
```

This is good for testing the CAN/voice pipeline without LLM overhead.
