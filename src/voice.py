"""
Voice Output - TTS with auto language detection

Engines:
- "kokoro": Kokoro-82M TTS (expressive, offline, English)
- "voicevox": VOICEVOX Core (Japanese, local)
- "auto": Auto-detect language per utterance — Japanese text → VOICEVOX, English → Kokoro
- "mock": Print only, no audio
"""
import io
import os
import queue
import re
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

try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

# Japanese/CJK detection
_CJK_RE = re.compile(r'[\u3000-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]')

# Known Japanese → English substitutions for Kokoro
_JP_TO_EN = {
    "ミラ": "Mira",
}

# Known English → Japanese substitutions for VOICEVOX
_EN_TO_JP = {
    "Mira": "ミラ",
    "Mira": "ミラ",
}

# Strip all CJK for Kokoro fallback
_CJK_STRIP_RE = re.compile(r'[\u3000-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]+')


def _has_japanese(text: str) -> bool:
    """Check if text contains Japanese/CJK characters."""
    # First remove known replaceable terms to avoid false positives
    cleaned = text
    for jp in _JP_TO_EN:
        cleaned = cleaned.replace(jp, "")
    return bool(_CJK_RE.search(cleaned))


def _prep_for_kokoro(text: str) -> str:
    """Prepare text for English Kokoro TTS."""
    for jp, en in _JP_TO_EN.items():
        text = text.replace(jp, en)
    text = _CJK_STRIP_RE.sub('', text)
    return text.strip()


def _prep_for_voicevox(text: str) -> str:
    """Prepare text for Japanese VOICEVOX TTS."""
    for en, jp in _EN_TO_JP.items():
        text = text.replace(en, jp)
    return text.strip()


def _generate_chime(sample_rate=24000, duration=0.15, ascending=True):
    """Generate a short two-tone chime as float32 numpy array."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    half = len(t) // 2
    tone = np.zeros_like(t)
    if ascending:
        tone[:half] = np.sin(2 * np.pi * 880 * t[:half])   # A5 → E6
        tone[half:] = np.sin(2 * np.pi * 1320 * t[half:])
    else:
        tone[:half] = np.sin(2 * np.pi * 1320 * t[:half])  # E6 → A5
        tone[half:] = np.sin(2 * np.pi * 880 * t[half:])
    envelope = np.ones_like(t)
    fade = int(sample_rate * 0.01)
    envelope[:fade] = np.linspace(0, 1, fade)
    envelope[-fade:] = np.linspace(1, 0, fade)
    return (tone * envelope).astype(np.float32), sample_rate


def _find_device_by_name(name_fragment: str, kind: str = "output") -> Optional[int]:
    """Find audio device index by partial name match. Returns None if not found."""
    if not AUDIO_AVAILABLE:
        return None
    try:
        for i, dev in enumerate(sd.query_devices()):
            if name_fragment.lower() in dev["name"].lower():
                if kind == "output" and dev["max_output_channels"] > 0:
                    return i
                elif kind == "input" and dev["max_input_channels"] > 0:
                    return i
        return None
    except Exception:
        return None


class Voice:
    """
    Text-to-speech output for ミラ.

    In "auto" mode, each utterance is routed to the appropriate engine
    based on whether it contains Japanese text:
    - Japanese detected → VOICEVOX Core (ずんだもん)
    - English only → Kokoro (af_jessica)
    """

    # Default paths for VOICEVOX Core files (relative to project root)
    _VOICEVOX_ONNX = "./models/voicevox/voicevox_core/onnxruntime/lib/libvoicevox_onnxruntime.so.1.17.3"
    _VOICEVOX_DICT = "./models/voicevox/voicevox_core/dict/open_jtalk_dic_utf_8-1.11"
    _VOICEVOX_VVM_DIR = "./models/voicevox/voicevox_core/models/vvms"

    # Default paths for Kokoro model files
    _KOKORO_MODEL = "./models/kokoro/kokoro-v1.0.onnx"
    _KOKORO_VOICES = "./models/kokoro/voices-v1.0.bin"

    def __init__(self, engine: str = "mock", output_device: Optional[int] = None,
                 kokoro_voice: str = "af_jessica",
                 speaker_id: int = 3, speed: float = 1.0,
                 volume: float = 0.3):
        self.engine = engine
        self.kokoro_voice = kokoro_voice
        self.speaker_id = speaker_id
        self.speed = speed
        self.volume = volume
        self._speaking = False
        self._lock = threading.Lock()

        # Resolve output device — validate index, fall back to name lookup
        self.output_device = output_device
        if AUDIO_AVAILABLE and output_device is not None:
            try:
                sd.query_devices(output_device)
            except Exception:
                resolved = _find_device_by_name("USB PnP Audio", "output")
                if resolved is not None:
                    print(f"[voice] Output device {output_device} not found, using {resolved}")
                    self.output_device = resolved

        # Lazy-init engines
        self._kokoro_ok = None
        self._voicevox_ok = None
        self._kokoro_engine: Optional["Kokoro"] = None
        self._vv_synth: Optional["Synthesizer"] = None

    def is_available(self) -> bool:
        if self.engine == "mock":
            return True
        if self.engine == "auto":
            return self._check_kokoro() or self._check_voicevox()
        if self.engine == "kokoro":
            return self._check_kokoro()
        if self.engine == "voicevox":
            return self._check_voicevox()
        return False

    def _check_kokoro(self) -> bool:
        if self._kokoro_ok is None:
            self._kokoro_ok = (
                KOKORO_AVAILABLE
                and Path(self._KOKORO_MODEL).exists()
                and Path(self._KOKORO_VOICES).exists()
            )
        return self._kokoro_ok

    def _check_voicevox(self) -> bool:
        if self._voicevox_ok is None:
            self._voicevox_ok = (
                VOICEVOX_CORE_AVAILABLE
                and Path(self._VOICEVOX_ONNX).exists()
                and Path(self._VOICEVOX_DICT).exists()
                and Path(self._VOICEVOX_VVM_DIR).is_dir()
            )
        return self._voicevox_ok

    def speak(self, text: str, blocking: bool = True) -> bool:
        if self.engine == "mock":
            print(f"[ミラ] {text}")
            return True
        if blocking:
            return self._speak_sync(text)
        else:
            t = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
            t.start()
            return True

    def speak_streamed(self, sentence_queue: queue.Queue, on_start=None, on_done=None):
        """Consume sentences from a queue and speak them back-to-back.

        Blocks until a None sentinel is received on the queue.
        Sentences are synthesized and played one at a time — while one plays,
        the next can already be queued by the streaming source.

        Args:
            sentence_queue: Queue of sentence strings. None signals end.
            on_start: Called before first sentence plays.
            on_done: Called after all sentences have played.
        """
        if self.engine == "mock":
            while True:
                sentence = sentence_queue.get()
                if sentence is None:
                    break
                print(f"[ミラ] {sentence}", end=" ", flush=True)
            print()
            if on_done:
                on_done()
            return

        self._speaking = True
        first = True
        try:
            while True:
                try:
                    sentence = sentence_queue.get(timeout=15)
                except queue.Empty:
                    break
                if sentence is None:
                    break
                if not sentence.strip():
                    continue

                if first and on_start:
                    on_start()
                    first = True

                engine = self.engine
                if engine == "auto":
                    engine = self._pick_engine(sentence)

                if engine == "kokoro":
                    self._kokoro_speak(sentence)
                elif engine == "voicevox":
                    self._voicevox_speak(sentence)
        except Exception as e:
            print(f"TTS stream error: {e}")
        finally:
            self._speaking = False
            if on_done:
                on_done()

    def _pick_engine(self, text: str) -> str:
        """For auto mode: choose engine based on text content."""
        if _has_japanese(text):
            if self._check_voicevox():
                return "voicevox"
            return "kokoro"
        return "kokoro"

    def _speak_sync(self, text: str) -> bool:
        with self._lock:
            if self._speaking:
                return False
            self._speaking = True
        try:
            engine = self.engine
            if engine == "auto":
                engine = self._pick_engine(text)

            if engine == "kokoro":
                return self._kokoro_speak(text)
            elif engine == "voicevox":
                return self._voicevox_speak(text)
            else:
                print(f"[ミラ] {text}")
                return True
        except Exception as e:
            print(f"TTS error ({self.engine}): {e}")
            return False
        finally:
            self._speaking = False

    # ---- Kokoro TTS (English) ----

    def _init_kokoro(self) -> "Kokoro":
        """Lazy-init Kokoro synthesizer on first use."""
        if self._kokoro_engine is None:
            self._kokoro_engine = Kokoro(self._KOKORO_MODEL, self._KOKORO_VOICES)
            print(f"[voice] Kokoro loaded (voice={self.kokoro_voice})")
        return self._kokoro_engine

    def _kokoro_speak(self, text: str) -> bool:
        text = _prep_for_kokoro(text)
        if not text:
            return True
        if not KOKORO_AVAILABLE or not AUDIO_AVAILABLE:
            print(f"[ミラ] {text}")
            return False

        kokoro = self._init_kokoro()
        samples, sr = kokoro.create(text, voice=self.kokoro_voice, speed=self.speed)
        audio = (samples * self.volume).astype(np.float32)
        sd.play(audio, sr, device=self.output_device)
        sd.wait()
        return True

    # ---- VOICEVOX TTS (Japanese, local Core) ----

    def _init_voicevox(self) -> "Synthesizer":
        """Lazy-init VOICEVOX Core synthesizer on first use."""
        if self._vv_synth is None:
            ort = Onnxruntime.load_once(filename=self._VOICEVOX_ONNX)
            jtalk = OpenJtalk(self._VOICEVOX_DICT)
            self._vv_synth = Synthesizer(ort, jtalk)
            vvm_dir = Path(self._VOICEVOX_VVM_DIR)
            for vvm_file in sorted(vvm_dir.glob("*.vvm")):
                model = VoiceModelFile.open(str(vvm_file))
                self._vv_synth.load_voice_model(model)
            print(f"[voice] VOICEVOX Core loaded (style_id={self.speaker_id})")
        return self._vv_synth

    def _voicevox_speak(self, text: str) -> bool:
        text = _prep_for_voicevox(text)
        if not VOICEVOX_CORE_AVAILABLE or not AUDIO_AVAILABLE:
            print(f"[ミラ] {text}")
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

    def chime(self, ascending=True):
        """Play a short chime. Ascending = wake, descending = done."""
        if not AUDIO_AVAILABLE:
            return
        try:
            audio, sr = _generate_chime(ascending=ascending)
            sd.play(audio * self.volume, sr, device=self.output_device)
            sd.wait()
        except Exception:
            pass

    def stop(self):
        try:
            sd.stop()
        except Exception:
            pass
        self._speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._speaking
