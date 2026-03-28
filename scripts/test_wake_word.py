#!/usr/bin/env python3
"""Test wake word detection from microphone."""
import pyaudio
import numpy as np
from openwakeword.model import Model

DEVICE_INDEX = 1  # HyperX QuadCast S
SAMPLE_RATE = 16000
CHUNK = 1280

m = Model(wakeword_models=["models/miraku.onnx"])
print("Listening for 'miraku' on HyperX QuadCast S...")
print("Threshold: 0.5 | Ctrl+C to stop\n")

pa = pyaudio.PyAudio()
stream = pa.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=SAMPLE_RATE,
    input=True,
    input_device_index=DEVICE_INDEX,
    frames_per_buffer=CHUNK,
)

try:
    while True:
        audio = np.frombuffer(
            stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16
        )
        prediction = m.predict(audio)
        for key, score in prediction.items():
            if score > 0.1:
                bar = "#" * int(score * 50)
                status = " << WAKE!" if score > 0.5 else ""
                print(f"  {score:.4f} [{bar}]{status}", flush=True)
except KeyboardInterrupt:
    print("\nStopped.")
finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
