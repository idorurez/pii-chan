# Custom Wake Word Training

Train a custom "pii-chan" wake word for OpenWakeWord.

## Prerequisites

```bash
cd ~/pii-chan
source venv/bin/activate
pip install openwakeword
```

## Option 1: Synthetic Training (Easier)

OpenWakeWord can generate training data using TTS:

```bash
# Clone the training repo
git clone https://github.com/dscripka/openWakeWord.git
cd openWakeWord

# Install training dependencies
pip install -e ".[training]"

# Generate synthetic samples for "pii-chan"
python -m openwakeword.train \
  --wake-word "pii chan" \
  --output-dir ~/pii-chan/models/pii-chan-wakeword \
  --synthetic-samples 5000
```

## Option 2: Real Voice Training (Better Accuracy)

### Step 1: Record Samples

Record yourself saying "pii-chan" 50-100 times:

```bash
mkdir -p ~/pii-chan/wake_samples/positive

# Record samples (say "pii-chan" each time)
for i in $(seq 1 50); do
  echo "Say 'pii-chan' (sample $i/50)..."
  arecord -D plughw:2,0 -f cd -d 2 ~/pii-chan/wake_samples/positive/sample_$i.wav
  sleep 1
done
```

### Step 2: Record Negative Samples

Record random speech that's NOT the wake word:

```bash
mkdir -p ~/pii-chan/wake_samples/negative

# Record random talking, background noise, etc.
for i in $(seq 1 50); do
  echo "Say something else or make noise (sample $i/50)..."
  arecord -D plughw:2,0 -f cd -d 3 ~/pii-chan/wake_samples/negative/sample_$i.wav
  sleep 1
done
```

### Step 3: Train the Model

```bash
cd ~/pii-chan
python -m openwakeword.train \
  --positive-samples wake_samples/positive \
  --negative-samples wake_samples/negative \
  --output-dir models/pii-chan-wakeword \
  --epochs 50
```

## Using Custom Wake Word

Once trained, update your wake word script:

```python
from openwakeword.model import Model

# Load custom model
model = Model(
    wakeword_models=["models/pii-chan-wakeword/pii_chan.onnx"]
)
```

## Alternative: Porcupine (Picovoice)

If OpenWakeWord training is difficult, Picovoice offers:
- Free tier with custom wake words
- Pre-trained engine, just provide samples
- https://picovoice.ai/platform/porcupine/

```bash
pip install pvporcupine
```

Then train at https://console.picovoice.ai/

---

*Note: Custom wake word training requires good quality recordings and may need iteration to get right.*
