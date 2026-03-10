"""
Voice Output - TTS with auto language detection

Engines:
- "piper": Local Piper TTS (fast, offline, English)
- "voicevox": VOICEVOX server (Japanese)
- "auto": Auto-detect language per utterance — Japanese text → VOICEVOX, English → Piper
- "mock": Print only, no audio
"""
import io
import os
import re
import subprocess
import wave
import threading
from typing import Optional
from pathlib import Path

try:
    import numpy as np
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Japanese/CJK detection
_CJK_RE = re.compile(r'[\u3000-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]')

# Known Japanese → English substitutions for Piper
_JP_TO_EN = {
    "ピーちゃん": "Pee-chan",
}

# Known English → Japanese substitutions for VOICEVOX
_EN_TO_JP = {
    "Pii-chan": "ピーちゃん",
    "Pee-chan": "ピーちゃん",
}

# Strip all CJK for Piper fallback
_CJK_STRIP_RE = re.compile(r'[\u3000-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]+')


def _has_japanese(text: str) -> bool:
    """Check if text contains Japanese/CJK characters."""
    # First remove known replaceable terms to avoid false positives
    cleaned = text
    for jp in _JP_TO_EN:
        cleaned = cleaned.replace(jp, "")
    return bool(_CJK_RE.search(cleaned))


def _prep_for_piper(text: str) -> str:
    """Prepare text for English Piper TTS."""
    for jp, en in _JP_TO_EN.items():
        text = text.replace(jp, en)
    text = _CJK_STRIP_RE.sub('', text)
    return text.strip()


def _prep_for_voicevox(text: str) -> str:
    """Prepare text for Japanese VOICEVOX TTS."""
    for en, jp in _EN_TO_JP.items():
        text = text.replace(en, jp)
    return text.strip()


class Voice:
    """
    Text-to-speech output for ピーちゃん.

    In "auto" mode, each utterance is routed to the appropriate engine
    based on whether it contains Japanese text:
    - Japanese detected → VOICEVOX (if available, else falls back to Piper with substitutions)
    - English only → Piper
    """

    def __init__(self, engine: str = "mock", output_device: Optional[int] = None,
                 piper_model: Optional[str] = None,
                 voicevox_url: str = "http://localhost:50021",
                 speaker_id: int = 1, speed: float = 1.1,
                 volume: float = 0.3):
        self.engine = engine
        self.output_device = output_device
        self.piper_model = piper_model
        self.voicevox_url = voicevox_url
        self.speaker_id = speaker_id
        self.speed = speed
        self.volume = volume
        self._speaking = False
        self._lock = threading.Lock()

        # Cache availability checks for auto mode
        self._piper_ok = None
        self._voicevox_ok = None

    def is_available(self) -> bool:
        if self.engine == "mock":
            return True
        if self.engine == "auto":
            return self._check_piper() or self._check_voicevox()
        if self.engine == "piper":
            return self._check_piper()
        if self.engine == "voicevox":
            return self._check_voicevox()
        return False

    def _check_piper(self) -> bool:
        if self._piper_ok is None:
            try:
                subprocess.run(["piper", "--help"], capture_output=True)
                self._piper_ok = not self.piper_model or Path(self.piper_model).exists()
            except FileNotFoundError:
                self._piper_ok = False
        return self._piper_ok

    def _check_voicevox(self) -> bool:
        if self._voicevox_ok is None:
            if not REQUESTS_AVAILABLE:
                self._voicevox_ok = False
            else:
                try:
                    r = requests.get(f"{self.voicevox_url}/speakers", timeout=2)
                    self._voicevox_ok = r.status_code == 200
                except Exception:
                    self._voicevox_ok = False
        return self._voicevox_ok

    def speak(self, text: str, blocking: bool = True) -> bool:
        if self.engine == "mock":
            print(f"[ピーちゃん] {text}")
            return True
        if blocking:
            return self._speak_sync(text)
        else:
            t = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
            t.start()
            return True

    def _pick_engine(self, text: str) -> str:
        """For auto mode: choose engine based on text content."""
        if _has_japanese(text):
            if self._check_voicevox():
                return "voicevox"
            # Fallback: substitute Japanese and use Piper
            return "piper"
        return "piper"

    def _speak_sync(self, text: str) -> bool:
        with self._lock:
            if self._speaking:
                return False
            self._speaking = True
        try:
            engine = self.engine
            if engine == "auto":
                engine = self._pick_engine(text)

            if engine == "piper":
                return self._piper_speak(text)
            elif engine == "voicevox":
                return self._voicevox_speak(text)
            else:
                print(f"[ピーちゃん] {text}")
                return True
        except Exception as e:
            print(f"TTS error ({self.engine}): {e}")
            return False
        finally:
            self._speaking = False

    # ---- Piper TTS (English) ----

    def _piper_speak(self, text: str) -> bool:
        text = _prep_for_piper(text)
        if not text:
            return True
        if not AUDIO_AVAILABLE:
            print(f"[ピーちゃん] {text}")
            return False

        cmd = ["piper", "--output-raw"]
        if self.piper_model:
            cmd += ["--model", self.piper_model]

        result = subprocess.run(
            cmd, input=text.encode(), capture_output=True, check=True
        )

        audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        audio = audio * self.volume
        sd.play(audio, samplerate=22050, device=self.output_device)
        sd.wait()
        return True

    # ---- VOICEVOX TTS (Japanese) ----

    def _voicevox_speak(self, text: str) -> bool:
        text = _prep_for_voicevox(text)
        if not REQUESTS_AVAILABLE or not AUDIO_AVAILABLE:
            print(f"[ピーちゃん] {text}")
            return False

        params = {"text": text, "speaker": self.speaker_id}
        r = requests.post(f"{self.voicevox_url}/audio_query", params=params, timeout=10)
        if r.status_code != 200:
            return False
        query = r.json()
        query["speedScale"] = self.speed

        r = requests.post(
            f"{self.voicevox_url}/synthesis",
            params={"speaker": self.speaker_id},
            json=query, timeout=30,
        )
        if r.status_code != 200:
            return False

        self._play_wav_bytes(r.content)
        return True

    def _play_wav_bytes(self, wav_data: bytes):
        with io.BytesIO(wav_data) as f:
            with wave.open(f, 'rb') as wav:
                sr = wav.getframerate()
                audio = wav.readframes(wav.getnframes())
                arr = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
                if wav.getnchannels() == 2:
                    arr = arr.reshape(-1, 2)
        arr = arr * self.volume
        sd.play(arr, sr, device=self.output_device)
        sd.wait()

    def stop(self):
        try:
            sd.stop()
        except Exception:
            pass
        self._speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._speaking
