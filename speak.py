#!/usr/bin/env python3
"""
TTS script for Pii-chan - speak text out loud.
Called from gateway via: nodes invoke --node piichan --command system.run --params '{"command":["python3","speak.py","Hello!"]}'
"""

import sys
import subprocess
import os

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_MODEL = os.path.join(SCRIPT_DIR, "voices", "en_US-lessac-medium.onnx")
OUTPUT_FILE = "/tmp/pii_speak.wav"

def speak(text):
    """Convert text to speech and play it."""
    
    # Generate audio with Piper
    piper_cmd = [
        "piper",
        "--model", VOICE_MODEL,
        "--output_file", OUTPUT_FILE
    ]
    
    try:
        result = subprocess.run(
            piper_cmd,
            input=text.encode(),
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Piper error: {e.stderr.decode()}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: piper not found. Run: source venv/bin/activate", file=sys.stderr)
        return False
    
    # Play audio
    try:
        subprocess.run(["aplay", OUTPUT_FILE], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"aplay error: {e.stderr.decode()}", file=sys.stderr)
        # Still return True since audio was generated
        return True
    except FileNotFoundError:
        print("Error: aplay not found", file=sys.stderr)
        return False
    
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python speak.py <text to speak>")
        sys.exit(1)
    
    text = " ".join(sys.argv[1:])
    success = speak(text)
    sys.exit(0 if success else 1)
