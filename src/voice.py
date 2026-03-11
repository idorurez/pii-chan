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
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    VOICEVOX_CORE_AVAILABLE = True
except ImportError:
    VOICEVOX_CORE_AVAILABLE = False

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

    # Default paths for VOICEVOX Core files (relative to project root)
    _VOICEVOX_ONNX = "./models/voicevox/voicevox_core/onnxruntime/lib/libvoicevox_onnxruntime.so.1.17.3"
    _VOICEVOX_DICT = "./models/voicevox/voicevox_core/dict/open_jtalk_dic_utf_8-1.11"
    _VOICEVOX_VVM = "./models/voicevox/voicevox_core/models/vvms/0.vvm"  # contains ずんだもん

    def __init__(self, engine: str = "mock", output_device: Optional[int] = None,
                 piper_model: Optional[str] = None,
                 speaker_id: int = 3, speed: float = 1.1,
                 volume: float = 0.3):
        self.engine = engine
        self.output_device = output_device
        self.piper_model = piper_model
        self.speaker_id = speaker_id
        self.speed = speed
        self.volume = volume
        self._speaking = False
        self._lock = threading.Lock()

        # Cache availability checks for auto mode
        self._piper_ok = None
        self._voicevox_ok = None
        self._vv_synth: Optional["Synthesizer"] = None  # lazy-init

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
            self._voicevox_ok = (
                VOICEVOX_CORE_AVAILABLE
                and Path(self._VOICEVOX_ONNX).exists()
                and Path(self._VOICEVOX_DICT).exists()
                and Path(self._VOICEVOX_VVM).exists()
            )
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

    # ---- VOICEVOX TTS (Japanese, local Core) ----

    def _init_voicevox(self) -> "Synthesizer":
        """Lazy-init VOICEVOX Core synthesizer on first use."""
        if self._vv_synth is None:
            ort = Onnxruntime.load_once(filename=self._VOICEVOX_ONNX)
            jtalk = OpenJtalk(self._VOICEVOX_DICT)
            self._vv_synth = Synthesizer(ort, jtalk)
            model = VoiceModelFile.open(self._VOICEVOX_VVM)
            self._vv_synth.load_voice_model(model)
            print(f"[voice] VOICEVOX Core loaded (style_id={self.speaker_id})")
        return self._vv_synth

    def _voicevox_speak(self, text: str) -> bool:
        text = _prep_for_voicevox(text)
        if not VOICEVOX_CORE_AVAILABLE or not AUDIO_AVAILABLE:
            print(f"[ピーちゃん] {text}")
            return False

        synth = self._init_voicevox()
        wav_bytes = synth.tts(text, style_id=self.speaker_id)
        self._play_wav_bytes(wav_bytes)
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
