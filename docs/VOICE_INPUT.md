# Voice Input Guide

Voice input for Mira: wake word detection → speech recording → STT transcription.

## Current Stack (Working on Pi 5)

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────┐
│  OpenWakeWord   │────▶│   Record     │────▶│    Vosk       │────▶│  Brain   │
│  (hey_jarvis)   │     │  until       │     │    STT        │     │  + TTS   │
│  always on      │     │  silence     │     │  transcribe   │     │  respond │
└─────────────────┘     └──────────────┘     └───────────────┘     └──────────┘
```

**Latency:** ~200ms wake detection + ~500ms STT + ~1-2s LLM = ~2-3s total

## Setup

### Dependencies

```bash
source venv/bin/activate
pip install vosk sounddevice numpy openwakeword
```

### Vosk Model (~50MB)

```bash
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
cd ..
```

### USB Audio Devices

Check device indices:

```bash
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

On our Pi 5 setup:
- Device 0: USB PnP Sound Device (mic only, 44100Hz native)
- Device 1: USB PnP Audio Device (mic + speaker output)

Configure in `config.yaml`:

```yaml
audio:
  input_device: 0   # mic
  output_device: 1  # speaker
```

## Configuration

```yaml
voice_input:
  enabled: true
  vosk_model_path: ./models/vosk-model-small-en-us-0.15
  wake_word: hey_jarvis
  wake_word_threshold: 0.5
  max_record_seconds: 7.0
  silence_threshold: 0.20    # above mic noise floor (~0.10 RMS)
  silence_duration: 1.5      # seconds of silence to stop recording
```

## Running

### Full Voice Loop (default)

```bash
source venv/bin/activate
python -m src.main
```

Say "hey Jarvis" → speak your question → Mira responds via TTS.

### Text Mode with Push-to-Talk

```bash
python -m src.main --simulate
# Type "voice" to record once without wake word
```

### Disable Voice Input

```bash
python -m src.main --no-mic    # passive mode, no wake word/STT
```

## Technical Details

### Audio Resampling

The USB mic runs at 44100Hz natively. OpenWakeWord and Vosk need 16kHz.
We use fast linear interpolation (`np.interp`) instead of `scipy.signal.resample`
which was ~100x too slow for real-time processing.

### OpenWakeWord Chunk Size

OWW expects 1280 samples at 16kHz (80ms). At 44100Hz native rate, that's
`int(1280 * 44100 / 16000)` = 3528 samples per chunk.

### Silence Detection

USB mic noise floor is ~0.10 RMS. Voice is ~0.30+ RMS.
Threshold set to 0.20 to distinguish speech from background noise.

### Queue-Based Architecture

Audio callback pushes chunks to a `queue.Queue(maxsize=200)` using `put_nowait`
to prevent blocking the audio thread. Dropped frames are preferred over blocking.

## Troubleshooting

### Wake word not detecting
- Check mic is working: `arecord -D hw:2,0 -r 44100 -f S16_LE -c 1 -d 3 /tmp/test.wav`
- Verify wake word model exists: `python -c "from openwakeword.model import Model; m=Model(); print(list(m.models.keys()))"`
- Try lowering `wake_word_threshold` (default 0.5)

### "Didn't catch that" after wake word
- Increase `silence_threshold` above your mic's noise floor
- Increase `max_record_seconds` for longer utterances
- Check mic RMS: `python -c "import sounddevice as sd; import numpy as np; d=sd.rec(16000, samplerate=16000, channels=1, device=0); sd.wait(); print(f'RMS: {np.sqrt(np.mean(d**2)):.4f}')"`

### Audio overflow / choppy detection
- Ensure using `np.interp` resampling (not scipy)
- Check CPU usage — OpenWakeWord + Vosk should be <30% on Pi 5

### No audio input detected
```bash
# List ALSA devices
arecord -l

# Test recording
arecord -D hw:2,0 -r 44100 -f S16_LE -c 1 -d 3 /tmp/test.wav
aplay -D hw:3,0 /tmp/test.wav
```
