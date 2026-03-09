import sounddevice as sd
import numpy as np
from scipy import signal
from openwakeword.model import Model

# List devices
print("Audio devices:")
print(sd.query_devices())

# Find USB mic
devices = sd.query_devices()
usb_idx = None
for i, d in enumerate(devices):
    if 'USB' in d['name'] and d['max_input_channels'] > 0:
        usb_idx = i
        print(f"\nUsing: {d['name']}")
        print(f"Default sample rate: {d['default_samplerate']}")
        break

# Load model
model = Model()
print("Wake words:", list(model.models.keys()))

# Use device's native sample rate, resample to 16000 for model
NATIVE_RATE = int(sd.query_devices(usb_idx)['default_samplerate'])
TARGET_RATE = 16000
CHUNK = int(NATIVE_RATE * 0.08)  # 80ms

print(f"\nRecording at {NATIVE_RATE}Hz, resampling to {TARGET_RATE}Hz")
print("Listening... say 'hey jarvis' (Ctrl+C to stop)")

def callback(indata, frames, time, status):
    # Resample to 16kHz
    audio_float = indata[:, 0]
    num_samples = int(len(audio_float) * TARGET_RATE / NATIVE_RATE)
    resampled = signal.resample(audio_float, num_samples)
    audio = (resampled * 32767).astype(np.int16)
    
    prediction = model.predict(audio)
    for ww, score in prediction.items():
        if score > 0.5:
            print(f"🎤 {ww}: {score:.2f}")

with sd.InputStream(device=usb_idx, channels=1, samplerate=NATIVE_RATE, 
                    blocksize=CHUNK, callback=callback):
    try:
        while True:
            sd.sleep(100)
    except KeyboardInterrupt:
        print("\nStopped")
