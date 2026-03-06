# Voice Input Guide

This guide covers setting up voice input for Pii-chan — talking to your car AI instead of typing.

## Quick Start (Push-to-Talk with Vosk)

```bash
# Install dependencies
pip install vosk sounddevice numpy

# Download English model (~50MB)
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
cd ..

# Test it
python -c "from src.voice_input import listen; print(listen())"
```

## STT Engine Options

### 1. Vosk (Recommended for Pi)

**Pros:** Lightweight, offline, real-time capable, free
**Cons:** Accuracy not as good as Whisper

| Model | Size | Quality | Speed on Pi 5 |
|-------|------|---------|---------------|
| vosk-model-small-en-us | 50MB | Good | Real-time ✓ |
| vosk-model-en-us | 1.8GB | Better | Near real-time |

**Install:**
```bash
pip install vosk
```

**Models:** https://alphacephei.com/vosk/models

---

### 2. Whisper.cpp (Better Quality)

OpenAI's Whisper ported to C++ for efficiency. Better accuracy than Vosk but slower.

| Model | Size | Quality | Speed on Pi 5 |
|-------|------|---------|---------------|
| tiny | 75MB | Good | ~2-3s per 5s audio |
| base | 150MB | Better | ~5-6s per 5s audio |
| small | 500MB | Great | ~15-20s (too slow) |

**Install:**
```bash
# Build whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
make

# Download model
./models/download-ggml-model.sh tiny.en
```

**Python binding:**
```bash
pip install pywhispercpp
```

---

### 3. Whisper API (Cloud, Best Quality)

Use OpenAI's Whisper API for best accuracy. Requires internet.

**Cost:** ~$0.006 per minute
**Latency:** ~1-2s for short clips

```python
import openai

def transcribe_with_whisper_api(audio_file):
    with open(audio_file, "rb") as f:
        result = openai.Audio.transcribe("whisper-1", f)
    return result["text"]
```

---

### 4. Google Cloud Speech-to-Text

Very accurate, requires internet and Google Cloud account.

```bash
pip install google-cloud-speech
```

---

## Wake Word Options

For hands-free activation ("Hey Pii-chan"), you need wake word detection.

### 1. Porcupine (Recommended)

**Pros:** Very lightweight, custom wake words, great accuracy
**Cons:** Free tier limited to 3 custom words

```bash
pip install pvporcupine
```

**Get free API key:** https://picovoice.ai/

```python
import pvporcupine

porcupine = pvporcupine.create(
    access_key="YOUR_KEY",
    keywords=["porcupine"],  # Built-in, or use custom
)
```

**Custom wake word:**
1. Go to https://console.picovoice.ai/
2. Create custom wake word "Pii-chan"
3. Download and use in your code

---

### 2. OpenWakeWord (Open Source)

**Pros:** Free, open source, trainable
**Cons:** Larger, newer project

```bash
pip install openwakeword
```

```python
from openwakeword import Model

model = Model(wakeword_models=["hey_jarvis"])

# Process audio frames
prediction = model.predict(audio_frame)
if prediction["hey_jarvis"] > 0.5:
    print("Wake word detected!")
```

**Train custom wake word:**
https://github.com/dscripka/openWakeWord#training-new-models

---

### 3. Vosk Keyword Spotting

Vosk can also do keyword spotting (less accurate than Porcupine).

```python
from vosk import Model, KaldiRecognizer

model = Model("model-path")
rec = KaldiRecognizer(model, 16000, '["pii chan", "[unk]"]')

# Process audio, check for keyword
if rec.AcceptWaveform(data):
    result = json.loads(rec.Result())
    if "pii chan" in result.get("text", ""):
        print("Wake word detected!")
```

---

## Architecture Recommendations

### For Raspberry Pi 5 (Resource Constrained)

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐
│   Porcupine     │────▶│    Vosk      │────▶│   Qwen 1.5B   │
│  (wake word)    │     │   (STT)      │     │    (LLM)      │
│   ~2MB, <1%CPU  │     │  ~50MB, 10%  │     │  ~1GB, 100%   │
└─────────────────┘     └──────────────┘     └───────────────┘
        │                      │                     │
   Always on              On wake only          On command only
```

**Total voice pipeline:** ~150ms wake detection + ~500ms STT + ~1-2s LLM = ~2-3s total

---

### For Desktop/Laptop (More Resources)

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐
│   Porcupine     │────▶│ Whisper.cpp  │────▶│   Qwen 3B     │
│  (wake word)    │     │   (base)     │     │    (LLM)      │
└─────────────────┘     └──────────────┘     └───────────────┘
```

---

### With Internet (Best Quality)

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐
│   Porcupine     │────▶│ Whisper API  │────▶│  Local LLM    │
│  (local)        │     │   (cloud)    │     │               │
└─────────────────┘     └──────────────┘     └───────────────┘
```

---

## Integration with Pii-chan

### Option 1: Push-to-Talk Command

Add to `main.py` text mode:

```python
elif verb == "voice":
    from .voice_input import VoiceInput
    vi = VoiceInput()
    text = vi.listen()
    if text:
        response = brain.chat(text, can.state)
        voice.speak(response)
```

### Option 2: Hardware Button

Connect a button to GPIO (Pi) and trigger recording:

```python
import RPi.GPIO as GPIO

BUTTON_PIN = 17

GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def on_button_press(channel):
    text = voice_input.listen()
    response = brain.chat(text, can.state)
    voice.speak(response)

GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=on_button_press)
```

### Option 3: Wake Word Loop

```python
def voice_loop():
    porcupine = create_porcupine("pii-chan")
    voice_input = VoiceInput()
    
    while running:
        if detect_wake_word(porcupine):
            voice.speak("Yes?")
            text = voice_input.listen()
            response = brain.chat(text, can.state)
            voice.speak(response)
```

---

## Troubleshooting

### No audio input detected
```bash
# List audio devices
python -c "import sounddevice; print(sounddevice.query_devices())"

# Set default device
export SD_DEVICE=1  # Use device index from above
```

### Vosk model not loading
- Ensure model is unzipped (should be a directory, not .zip)
- Check path in config

### Poor transcription quality
- Speak clearly, reduce background noise
- Try a larger Vosk model
- Consider Whisper.cpp for better accuracy

### High latency
- Use smaller models
- Reduce max recording time
- Consider wake word to avoid processing silence

---

## Hardware Recommendations

### Microphone for Car
- **USB:** Blue Snowball iCE (~$50) — good quality
- **I2S:** INMP441 (~$5) — connects directly to Pi GPIO
- **USB Array:** ReSpeaker USB (~$80) — beam forming, better in noise

### For Pi Setup
```
Pi 5 ─── USB Mic ─── INMP441
  │
  └─── I2S DAC ─── Speaker (for VOICEVOX output)
```

---

## Performance Tips

1. **Load models once** at startup, not per request
2. **Use wake word** to avoid processing silence
3. **Silence detection** to stop recording early
4. **Async processing** — start STT while LLM might still be loaded
5. **Consider streaming** — Vosk supports streaming for lower latency
