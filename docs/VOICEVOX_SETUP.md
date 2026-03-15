# VOICEVOX Setup

VOICEVOX is a free, open-source Japanese text-to-speech engine with cute anime-style voices. Perfect for Mira!

Mira supports two modes:
- **VOICEVOX Core** (local Python bindings) — recommended for Raspberry Pi, no server needed
- **VOICEVOX Engine** (HTTP API) — requires running VOICEVOX server

## Option 1: VOICEVOX Core (Recommended for Pi)

Local Python bindings — no server process needed, lower latency.

### Install Python package

```bash
source venv/bin/activate

# For Raspberry Pi 5 (aarch64, Python 3.11+)
pip install https://github.com/VOICEVOX/voicevox_core/releases/download/0.16.4/voicevox_core-0.16.4-cp310-abi3-manylinux_2_34_aarch64.whl

# For x86_64 Linux
pip install voicevox-core==0.16.4
```

### Download required files

```bash
mkdir -p models/voicevox/voicevox_core/{dict,models/vvms,onnxruntime/lib}

# 1. OpenJTalk dictionary (required for text processing)
cd models/voicevox/voicevox_core/dict
wget https://jaist.dl.sourceforge.net/project/open-jtalk/Dictionary/open_jtalk_dic-1.11/open_jtalk_dic_utf_8-1.11.tar.gz
tar xzf open_jtalk_dic_utf_8-1.11.tar.gz
rm open_jtalk_dic_utf_8-1.11.tar.gz
cd ../../../..

# 2. ONNX Runtime library (required by voicevox_core)
cd models/voicevox/voicevox_core/onnxruntime/lib
wget https://github.com/VOICEVOX/onnxruntime-builder/releases/download/1.17.3/voicevox-onnxruntime-linux-arm64-cpu-1.17.3.tgz
tar xzf voicevox-onnxruntime-linux-arm64-cpu-1.17.3.tgz --strip-components=1
rm voicevox-onnxruntime-linux-arm64-cpu-1.17.3.tgz
cd ../../../../..

# 3. Voice model files (.vvm)
cd models/voicevox/voicevox_core/models/vvms
# Download from VOICEVOX releases — each .vvm contains one or more characters
# See https://github.com/VOICEVOX/voicevox_core/releases for model downloads
cd ../../../../..
```

### Test VOICEVOX Core

```bash
source venv/bin/activate
python3 -c "
from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
from pathlib import Path

ort = Onnxruntime.load_once(
    filename='./models/voicevox/voicevox_core/onnxruntime/lib/libvoicevox_onnxruntime.so.1.17.3'
)
jtalk = OpenJtalk('./models/voicevox/voicevox_core/dict/open_jtalk_dic_utf_8-1.11')
synth = Synthesizer(ort, jtalk)

# Load a voice model
for vvm in Path('./models/voicevox/voicevox_core/models/vvms').glob('*.vvm'):
    model = VoiceModelFile.open(vvm)
    synth.load_voice_model(model)

# Synthesize (style_id=3 = ずんだもん ノーマル)
wav = synth.tts('こんにちは！ミラです！', style_id=3)
with open('/tmp/voicevox_test.wav', 'wb') as f:
    f.write(wav)
print('Saved to /tmp/voicevox_test.wav')
"
aplay /tmp/voicevox_test.wav
```

## Option 2: VOICEVOX Engine (HTTP API)

### macOS / Windows

1. Download from: https://voicevox.hiroshiba.jp/
2. Install and run VOICEVOX
3. It starts a local server on port 50021

### Linux

```bash
# Docker (easiest)
docker run -p 50021:50021 voicevox/voicevox_engine:cpu-latest
```

## Available Voices

| ID | Character | Style |
|----|-----------|-------|
| 0 | 四国めたん | あまあま (sweet) |
| 1 | ずんだもん | あまあま (sweet) |
| 2 | 四国めたん | ノーマル |
| 3 | **ずんだもん** | **ノーマル** ← Recommended for Mira |
| 8 | 春日部つむぎ | ノーマル |
| 10 | 雨晴はう | ノーマル |
| 14 | 冥鳴ひまり | ノーマル |

**Recommended for Mira:** Speaker ID `3` (ずんだもん ノーマル) - cute but clear.

## Testing

```bash
# Check if VOICEVOX is running
curl http://localhost:50021/speakers

# Generate test audio
curl -X POST "http://localhost:50021/audio_query?text=ピピッ！こんにちは！&speaker=3" \
  -H "Content-Type: application/json" > query.json

curl -X POST "http://localhost:50021/synthesis?speaker=3" \
  -H "Content-Type: application/json" \
  -d @query.json > test.wav

# Play it
aplay test.wav  # Linux
afplay test.wav  # macOS
```

## Configuration

In `config.yaml`:

```yaml
voice:
  # "auto" = auto-detect language per utterance
  # Japanese text → VOICEVOX, English text → Piper
  engine: auto
  piper_model: ./voices/en_US-lessac-medium.onnx
  speaker_id: 3  # ずんだもん ノーマル
  speed: 1.1
  volume: 0.3
```

## Auto-Detect Dual Engine Mode

When `engine: auto`, Mira automatically routes each utterance:
- **Japanese/CJK text** → VOICEVOX (if available, else falls back to Piper with substitutions)
- **English text** → Piper TTS

Known substitutions:
- `ミラ` → "Mira" (for Piper)
- "Mira" / "Mira" → `ミラ` (for VOICEVOX)

## Troubleshooting

### VOICEVOX Core: ImportError or library not found
- Ensure ONNX runtime .so file exists and path is correct
- On Pi: the wheel is `cp310-abi3` — works with Python 3.10+

### VOICEVOX Engine: not responding
- Check if the process/container is running
- Verify port 50021 is not blocked
- Try `curl http://localhost:50021/speakers`

### Audio not playing
- Check `sounddevice` is installed: `pip install sounddevice`
- Verify output device index: `python -c "import sounddevice; print(sounddevice.query_devices())"`
- Test speaker: `speaker-test -D hw:3,0 -c 1 -t wav`

### Volume too loud/quiet
- Adjust `volume` in config.yaml (0.0 - 1.0, default 0.3)
