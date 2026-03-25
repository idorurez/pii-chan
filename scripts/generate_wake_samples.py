#!/usr/bin/env python3
"""
Generate synthetic wake word samples for "miraku" using Kokoro TTS.

Produces varied audio clips by:
- Using multiple Kokoro voices (English + Japanese)
- Varying speed (0.8x - 1.3x)
- Adding the wake word in different contexts (isolated, in phrases)
- Loading extra voice .bin files for Japanese support

Output: WAV files at 16kHz mono, ready for openWakeWord training.

Usage:
    python scripts/generate_wake_samples.py --output ./training/positive --count 5000
    python scripts/generate_wake_samples.py --output ./training/negative --negative --count 2000
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# Voices bundled in voices-v1.0.bin (always available)
BUILTIN_VOICES = [
    "af", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael",
    "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
]

# Extra voices to load from individual .bin files (models/kokoro_voices/voices/)
EXTRA_VOICE_FILES = [
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "af_alloy", "af_aoede", "af_jessica", "af_kore", "af_nova", "af_river",
    "am_echo", "am_eric", "am_fenrir", "am_liam", "am_onyx", "am_puck",
    "bf_alice", "bf_lily", "bm_daniel", "bm_fable",
]

# Positive samples — Japanese + romanized variations of "miraku"
POSITIVE_PHRASES_JP = [
    # Native Japanese
    "ミラク",
    "ミラク、",
    "ミラク、聞いて",
    "ミラク、教えて",
    "ミラク、おはよう",
    "ねえミラク",
    "ミラクちゃん",
]

POSITIVE_PHRASES_EN = [
    # Romanized for English voices
    "miraku",
    "meeraku",
    "mee rah koo",
    "mee ra koo",
    "hey miraku",
    "ok miraku",
    "yo miraku",
    "miraku listen",
    "miraku hey",
]

# Negative samples: similar-sounding words that should NOT trigger
NEGATIVE_PHRASES_JP = [
    "ありがとう", "おはよう", "すみません",
    "そうですね", "なるほど", "大丈夫",
    "ミラー", "みらい", "奇跡",
    "聞いて", "教えて", "お願い",
]

NEGATIVE_PHRASES_EN = [
    "miracle", "miraculous", "mirror", "mural",
    "morocco", "meraki", "maracas", "mikado",
    "karaoke", "teriyaki", "sudoku", "haiku",
    "hello", "hey there", "excuse me", "thank you",
    "good morning", "good night", "see you later",
    "turn left", "turn right", "slow down", "speed up",
    "what time is it", "how far", "are we there yet",
    "America", "medical", "mechanical",
]

# Speed variations for diversity
SPEEDS = [0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.3]


def load_extra_voice(path: str) -> np.ndarray:
    """Load a .bin voice file and reshape to (511, 1, 256)."""
    data = np.fromfile(path, dtype=np.float32)
    voice = data.reshape(-1, 1, 256)
    if voice.shape[0] < 511:
        voice = np.pad(voice, ((0, 511 - voice.shape[0]), (0, 0), (0, 0)))
    return voice


def generate_samples(output_dir: str, count: int, negative: bool = False):
    """Generate wake word samples using Kokoro TTS."""
    from kokoro_onnx import Kokoro

    model_path = "./models/kokoro/kokoro-v1.0.onnx"
    voices_path = "./models/kokoro/voices-v1.0.bin"

    if not Path(model_path).exists() or not Path(voices_path).exists():
        print(f"Error: Kokoro model not found at {model_path}")
        print("Download from: https://huggingface.co/deskpai/kokoro-onnx")
        sys.exit(1)

    print("Loading Kokoro TTS...")
    kokoro = Kokoro(model_path, voices_path)

    # Build voice list: builtin names + extra loaded voices
    builtin = kokoro.get_voices()
    voice_entries = []  # list of (name, voice_param) where voice_param is str or ndarray

    for v in BUILTIN_VOICES:
        if v in builtin:
            voice_entries.append((v, v))

    # Load extra voices from individual .bin files
    extra_dir = Path("./models/kokoro_voices/voices")
    if extra_dir.exists():
        for name in EXTRA_VOICE_FILES:
            bin_path = extra_dir / f"{name}.bin"
            if bin_path.exists():
                try:
                    voice_data = load_extra_voice(str(bin_path))
                    voice_entries.append((name, voice_data))
                except Exception as e:
                    print(f"  Warning: failed to load {name}: {e}")

    jp_voices = [(n, v) for n, v in voice_entries if n.startswith("j")]
    en_voices = [(n, v) for n, v in voice_entries if not n.startswith("j")]

    print(f"  {len(voice_entries)} voices loaded ({len(jp_voices)} JP, {len(en_voices)} EN)")

    os.makedirs(output_dir, exist_ok=True)

    if negative:
        # For negatives, pair JP phrases with JP voices, EN with EN
        phrase_voice_pairs = []
        for phrase in NEGATIVE_PHRASES_JP:
            for name, voice in jp_voices:
                phrase_voice_pairs.append((phrase, name, voice))
        for phrase in NEGATIVE_PHRASES_EN:
            for name, voice in en_voices:
                phrase_voice_pairs.append((phrase, name, voice))
        label = "negative"
    else:
        # For positives, pair JP phrases with JP voices, EN with EN
        phrase_voice_pairs = []
        for phrase in POSITIVE_PHRASES_JP:
            for name, voice in jp_voices:
                phrase_voice_pairs.append((phrase, name, voice))
        for phrase in POSITIVE_PHRASES_EN:
            for name, voice in en_voices:
                phrase_voice_pairs.append((phrase, name, voice))
        label = "positive"

    print(f"  {len(phrase_voice_pairs)} phrase/voice combos available")
    print(f"Generating {count} {label} samples...")
    generated = 0
    errors = 0

    while generated < count:
        pair_idx = generated % len(phrase_voice_pairs)
        speed_idx = generated % len(SPEEDS)
        phrase, voice_name, voice_param = phrase_voice_pairs[pair_idx]
        speed = SPEEDS[speed_idx]

        try:
            samples, sr = kokoro.create(phrase, voice=voice_param, speed=speed)

            # Convert to 16kHz mono (openWakeWord format)
            if sr != 16000:
                n_out = int(len(samples) * 16000 / sr)
                x_in = np.linspace(0, 1, len(samples), endpoint=False)
                x_out = np.linspace(0, 1, n_out, endpoint=False)
                samples = np.interp(x_out, x_in, samples)
                sr = 16000

            # Normalize
            peak = np.max(np.abs(samples))
            if peak > 0:
                samples = samples / peak * 0.9

            filename = f"{label}_{generated:05d}_{voice_name}_{speed:.2f}.wav"
            filepath = os.path.join(output_dir, filename)
            sf.write(filepath, samples.astype(np.float32), sr)
            generated += 1

            if generated % 200 == 0:
                print(f"  {generated}/{count} generated...")

        except Exception as e:
            errors += 1
            if errors > 50:
                print(f"Too many errors ({errors}), stopping.")
                break
            if errors <= 5:
                print(f"  Error ({voice_name}, '{phrase[:20]}', {speed}x): {e}")
            generated += 1  # Skip this combo
            continue

    print(f"Done! Generated {generated} {label} samples in {output_dir}")
    if errors:
        print(f"  ({errors} errors skipped)")


def main():
    parser = argparse.ArgumentParser(description="Generate wake word training samples")
    parser.add_argument("--output", "-o", default="./training/positive",
                        help="Output directory for WAV files")
    parser.add_argument("--count", "-n", type=int, default=5000,
                        help="Number of samples to generate")
    parser.add_argument("--negative", action="store_true",
                        help="Generate negative (non-wake-word) samples instead")
    args = parser.parse_args()

    generate_samples(args.output, args.count, args.negative)


if __name__ == "__main__":
    main()
