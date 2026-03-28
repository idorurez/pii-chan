#!/usr/bin/env python3
"""
Generate wake word training samples by augmenting real recordings.

Takes a small number of ground truth recordings and creates thousands
of variations using pitch shifting, speed changes, noise, and reverb.

Output: WAV files at 16kHz mono, ready for openWakeWord training.

Usage:
    python scripts/augment_wake_samples.py --input ./training/miraku_gt --output ./training/positive --count 20000
"""

import argparse
import os
import wave
import random
from pathlib import Path

import numpy as np


def load_wav(path: str) -> tuple:
    """Load a WAV file and return (samples_float32, sample_rate)."""
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        frames = w.readframes(w.getnframes())

    if sw == 2:
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        data = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sw}")

    # Convert to mono
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)

    return data, sr


def resample(data: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Simple linear interpolation resampling."""
    if sr_in == sr_out:
        return data
    n_out = int(len(data) * sr_out / sr_in)
    x_in = np.linspace(0, 1, len(data), endpoint=False)
    x_out = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_out, x_in, data)


def trim_silence(data: np.ndarray, threshold_ratio: float = 0.03) -> np.ndarray:
    """Trim leading and trailing silence."""
    threshold = np.max(np.abs(data)) * threshold_ratio
    active = np.where(np.abs(data) > threshold)[0]
    if len(active) == 0:
        return data
    # Add small padding
    start = max(0, active[0] - 200)
    end = min(len(data), active[-1] + 200)
    return data[start:end]


def pitch_shift(data: np.ndarray, semitones: float) -> np.ndarray:
    """Pitch shift by resampling (changes duration slightly)."""
    factor = 2.0 ** (semitones / 12.0)
    n_out = int(len(data) / factor)
    x_in = np.linspace(0, 1, len(data), endpoint=False)
    x_out = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_out, x_in, data)


def time_stretch(data: np.ndarray, rate: float) -> np.ndarray:
    """Simple time stretch by resampling."""
    n_out = int(len(data) / rate)
    x_in = np.linspace(0, 1, len(data), endpoint=False)
    x_out = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_out, x_in, data)


def add_noise(data: np.ndarray, snr_db: float) -> np.ndarray:
    """Add white noise at given SNR."""
    signal_power = np.mean(data ** 2)
    noise_power = signal_power / (10 ** (snr_db / 10))
    noise = np.random.randn(len(data)) * np.sqrt(noise_power)
    return data + noise


def random_gain(data: np.ndarray, min_db: float = -6, max_db: float = 6) -> np.ndarray:
    """Apply random gain."""
    gain_db = random.uniform(min_db, max_db)
    return data * (10 ** (gain_db / 20))


def add_padding(data: np.ndarray, sr: int, max_pad_s: float = 0.3) -> np.ndarray:
    """Add random silence padding before and after."""
    pad_before = int(random.uniform(0, max_pad_s) * sr)
    pad_after = int(random.uniform(0, max_pad_s) * sr)
    return np.concatenate([np.zeros(pad_before), data, np.zeros(pad_after)])


def augment_sample(data: np.ndarray, sr: int) -> np.ndarray:
    """Apply random augmentations to a sample."""
    result = data.copy()

    # Pitch shift: -4 to +4 semitones (simulates different speakers)
    if random.random() < 0.7:
        semitones = random.uniform(-4, 4)
        result = pitch_shift(result, semitones)

    # Time stretch: 0.8x to 1.3x
    if random.random() < 0.7:
        rate = random.uniform(0.8, 1.3)
        result = time_stretch(result, rate)

    # Add noise: 10-30 dB SNR
    if random.random() < 0.5:
        snr = random.uniform(10, 30)
        result = add_noise(result, snr)

    # Random gain
    if random.random() < 0.5:
        result = random_gain(result, -8, 8)

    # Add random padding
    result = add_padding(result, sr)

    # Normalize
    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * random.uniform(0.5, 0.95)

    return result


def main():
    parser = argparse.ArgumentParser(description="Augment wake word recordings")
    parser.add_argument("--input", "-i", default="./training/miraku_gt",
                        help="Directory with ground truth WAV recordings")
    parser.add_argument("--output", "-o", default="./training/positive",
                        help="Output directory for augmented WAV files")
    parser.add_argument("--count", "-n", type=int, default=20000,
                        help="Number of augmented samples to generate")
    args = parser.parse_args()

    # Load all ground truth recordings
    input_dir = Path(args.input)
    wav_files = sorted(input_dir.glob("*.wav"))
    if not wav_files:
        print(f"Error: No WAV files found in {args.input}")
        return

    print(f"Loading {len(wav_files)} ground truth recordings...")
    recordings = []
    for f in wav_files:
        data, sr = load_wav(str(f))
        # Resample to 16kHz
        data = resample(data, sr, 16000)
        # Trim silence
        data = trim_silence(data)
        recordings.append(data)
        print(f"  {f.name}: {len(data)/16000:.2f}s")

    os.makedirs(args.output, exist_ok=True)
    sr_out = 16000

    print(f"Generating {args.count} augmented samples...")
    for i in range(args.count):
        # Pick a random recording
        base = random.choice(recordings)

        # Augment it
        augmented = augment_sample(base, sr_out)

        # Save as 16kHz mono float32
        filename = f"positive_{i:05d}.wav"
        filepath = os.path.join(args.output, filename)

        # Write with wave module (16-bit PCM)
        augmented_int16 = (augmented * 32767).clip(-32768, 32767).astype(np.int16)
        with wave.open(filepath, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr_out)
            w.writeframes(augmented_int16.tobytes())

        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{args.count} generated...")

    print(f"Done! Generated {args.count} samples in {args.output}")


if __name__ == "__main__":
    main()
