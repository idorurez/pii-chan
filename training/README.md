# Miraku Wake Word Training

Custom wake word model for "miraku" (ミラク) using openWakeWord.

## Overview

- **Wake word**: miraku (ミラク)
- **TTS engine**: Kokoro ONNX (supports Japanese voices, unlike Piper which is English-only)
- **Training**: openWakeWord pipeline via Google Colab
- **Output**: `.onnx` model file for use with openWakeWord on the Pi

## Step 1: Generate Synthetic Samples (Local - Windows Desktop)

### Prerequisites

```bash
pip install kokoro-onnx soundfile numpy "numpy<2"
pip install huggingface-hub
```

### Download Kokoro Model

```bash
mkdir -p models/kokoro
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('deskpai/kokoro-onnx', '2e8a51507c9e3a8d8c3da74ac5ecb15d.onnx', local_dir='models/kokoro')
hf_hub_download('deskpai/kokoro-onnx', 'dbb89653b2b3ceddb20978acab402608.bin', local_dir='models/kokoro')
"
# Rename to expected names
cd models/kokoro
mv 2e8a51507c9e3a8d8c3da74ac5ecb15d.onnx kokoro-v1.0.onnx
mv dbb89653b2b3ceddb20978acab402608.bin voices-v1.0.bin
```

### Download Extra Japanese Voices

```bash
python -c "
from huggingface_hub import hf_hub_download
voices = ['jf_alpha','jf_gongitsune','jf_nezumi','jf_tebukuro','jm_kumo',
          'af_alloy','af_aoede','af_jessica','af_kore','af_nova','af_river',
          'am_echo','am_eric','am_fenrir','am_liam','am_onyx','am_puck',
          'bf_alice','bf_lily','bm_daniel','bm_fable']
for v in voices:
    hf_hub_download('onnx-community/Kokoro-82M-v1.0-ONNX', f'voices/{v}.bin', local_dir='models/kokoro_voices')
    print(f'OK: {v}')
"
```

### Generate Samples

```bash
# 5000 positive samples (Japanese + English voices saying "miraku" variations)
python scripts/generate_wake_samples.py --output ./training/positive --count 5000

# 2000 negative samples (similar-sounding words that should NOT trigger)
python scripts/generate_wake_samples.py --output ./training/negative --negative --count 2000
```

The script uses:
- 5 Japanese voices (jf_alpha, jf_gongitsune, jf_nezumi, jf_tebukuro, jm_kumo) for native Japanese phrases (ミラク, ねえミラク, etc.)
- 26 English voices for romanized phrases (miraku, mee rah koo, hey miraku, etc.)
- 10 speed variations (0.8x - 1.3x)
- Output: 16kHz mono WAV files

### Zip for Upload

```bash
cd training
python -c "
import zipfile, os
for name in ['positive', 'negative']:
    with zipfile.ZipFile(f'{name}.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in os.listdir(name):
            if f.endswith('.wav'):
                zf.write(os.path.join(name, f), f)
    print(f'{name}.zip: {os.path.getsize(name + \".zip\") / 1024 / 1024:.1f} MB')
"
```

## Step 2: Train Model (Google Colab)

### Open the Notebook

Open the detailed training notebook in Colab:
https://colab.research.google.com/github/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb

Save a copy to your Drive (File > Save a copy in Drive).

### Run Setup Cells (Cells 1-5)

Run these as-is. They install dependencies and download training data:
- Cell 1: Environment setup (pip installs)
- Cell 2: Imports
- Cell 3: Download MIT room impulse responses
- Cell 4: Download background noise (AudioSet + Free Music Archive)
- Cell 5: Download pre-computed negative features (ACAV100M ~3.5GB)

### Fix Colab Compatibility Issues

You may need to run these fixes before training:

```python
# Fix torch version conflicts
!pip install torchmetrics==1.2.0 torchvision==0.19.0 torch==2.4.0 torchaudio==2.4.0
# Then: Runtime > Restart runtime

# Fix piper-sample-generator (needs old commit)
!cd /content/piper-sample-generator && git checkout 213d4d5
!pip install piper-phonemize-cross
```

### Configure Model (Cell 7)

```python
config["target_phrase"] = ["miraku"]
config["model_name"] = "miraku"
config["n_samples"] = 5000
config["n_samples_val"] = 500
config["steps"] = 50000
config["target_accuracy"] = 0.6
config["target_recall"] = 0.25
config["background_paths"] = ['./audioset_16k', './fma']
config["false_positive_validation_data_path"] = "validation_set_features.npy"
config["feature_data_files"] = {"ACAV100M_sample": "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"}
```

### SKIP Cell 8 (Generate Clips)

Do NOT run the generate_clips step — Piper TTS is English-only and can't pronounce "miraku" correctly. We use our Kokoro-generated clips instead.

### Upload Our Clips

Upload `positive.zip` and `negative.zip` to Colab, then run:

```python
import os, random

# Create directories
os.makedirs("my_custom_model/miraku/positive_train", exist_ok=True)
os.makedirs("my_custom_model/miraku/positive_test", exist_ok=True)
os.makedirs("my_custom_model/miraku/negative_train", exist_ok=True)
os.makedirs("my_custom_model/miraku/negative_test", exist_ok=True)

# Unzip
!unzip positive.zip -d my_custom_model/miraku/positive_train/
!unzip negative.zip -d my_custom_model/miraku/negative_train/

# Split ~500 positive and ~200 negative into test sets
files = os.listdir("my_custom_model/miraku/positive_train/")
random.shuffle(files)
for f in files[:500]:
    os.rename(f"my_custom_model/miraku/positive_train/{f}", f"my_custom_model/miraku/positive_test/{f}")

neg_files = os.listdir("my_custom_model/miraku/negative_train/")
random.shuffle(neg_files)
for f in neg_files[:200]:
    os.rename(f"my_custom_model/miraku/negative_train/{f}", f"my_custom_model/miraku/negative_test/{f}")
```

### Run Augment Clips (Cell 9)

```python
import sys
!{sys.executable} openwakeword/openwakeword/train.py --training_config my_model.yaml --augment_clips
```

### Run Train Model (Cell 10)

```python
import sys
!{sys.executable} openwakeword/openwakeword/train.py --training_config my_model.yaml --train_model
```

Training takes ~30-60 minutes. Output: `my_custom_model/miraku.onnx`

### Download the Model

In the Colab file browser (folder icon, left sidebar):
Navigate to `my_custom_model/` > right-click `miraku.onnx` > Download

## Step 3: Deploy to Pi

1. Copy `miraku.onnx` to the Pi at `models/miraku.onnx`
2. Set in `config.yaml`:
   ```yaml
   voice_input:
     wake_word_model_path: models/miraku.onnx
   ```
3. The wiring is already done in `src/voice_input.py` and `src/config.py` — openWakeWord loads it via `OWWModel(wakeword_models=[path])`
4. Tune `wake_threshold` (default 0.5) based on real-world testing

## Notes

- **Why not Piper TTS?** Piper uses an English-only LibriTTS model. It can't produce the Japanese R sound (ら行) in "miraku" — the English R/L sounds comical. Kokoro ONNX has native Japanese voices that pronounce ミラク correctly.
- **Sample counts**: openWakeWord recommends 20,000+ positive samples for best results. Our 5000 is a starting point — if accuracy is low, regenerate with higher count.
- **The bundled Kokoro voices file** (`voices-v1.0.bin`) only has 11 English voices. Japanese voices must be loaded from individual `.bin` files downloaded from `onnx-community/Kokoro-82M-v1.0-ONNX`. The script handles this automatically.
