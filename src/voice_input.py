"""
Voice Input - Wake word detection + Speech-to-text for Mira

Full loop:
  1. Listen for wake word (OpenWakeWord, always on)
  2. On wake word, record speech until silence
  3. Transcribe with Vosk STT
  4. Return transcribed text via callback
"""

import json
import queue
import threading
import time
import sys
from pathlib import Path
from typing import Optional, Callable

import numpy as np
import sounddevice as sd


class VoskSTT:
    """Offline speech-to-text using Vosk."""

    def __init__(self, model_path: str):
        import vosk
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Vosk model not found at {model_path}\n"
                "Download: https://alphacephei.com/vosk/models"
            )
        vosk.SetLogLevel(-1)
        self.model = vosk.Model(model_path)
        self.sample_rate = 16000

    def transcribe(self, audio_int16: np.ndarray) -> str:
        """Transcribe 16kHz int16 audio to text."""
        import vosk
        rec = vosk.KaldiRecognizer(self.model, self.sample_rate)
        rec.AcceptWaveform(audio_int16.tobytes())
        result = json.loads(rec.FinalResult())
        return result.get("text", "").strip()


class VoiceInput:
    """
    Continuous voice input: wake word detection → record → STT.

    Usage:
        vi = VoiceInput(
            vosk_model_path="./models/vosk-model-small-en-us-0.15",
            on_speech=lambda text: print(f"You said: {text}"),
            on_wake=lambda: print("Wake word detected!"),
        )
        vi.start()   # starts background thread
        vi.stop()    # stops
    """

    def __init__(
        self,
        vosk_model_path: str = "./models/vosk-model-small-en-us-0.15",
        wake_word: str = "hey_jarvis",
        wake_threshold: float = 0.5,
        input_device: Optional[int] = None,
        max_record_seconds: float = 5.0,
        silence_threshold: float = 0.15,
        silence_duration: float = 1.0,
        on_speech: Optional[Callable[[str], None]] = None,
        on_wake: Optional[Callable[[], None]] = None,
    ):
        self.vosk_model_path = vosk_model_path
        self.wake_word = wake_word
        self.wake_threshold = wake_threshold
        self.input_device = self._resolve_input_device(input_device)
        self.max_record_seconds = max_record_seconds
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.on_speech = on_speech
        self.on_wake = on_wake
        self.on_speech_fail = None  # Called when recording fails (silence, too short)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stt: Optional[VoskSTT] = None
        self._recording = False  # True while recording user speech
        self.muted = False  # Set True to suppress wake word detection (e.g. during TTS)
        self._audio_queue: Optional[queue.Queue] = None

    @staticmethod
    def _resolve_input_device(device: Optional[int]) -> Optional[int]:
        """Validate device index, fall back to name lookup if invalid."""
        if device is None:
            return None
        try:
            sd.query_devices(device, 'input')
            return device
        except Exception:
            # Search by name
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0 and "usb" in dev["name"].lower():
                    print(f"  [voice_input] Device {device} not found, using [{i}] {dev['name']}")
                    return i
            return None

    @property
    def is_listening(self) -> bool:
        return self._running

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self):
        """Start the wake word → STT loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def drain_queue(self):
        """Drain the audio queue to discard buffered audio (e.g. after TTS)."""
        if hasattr(self, '_audio_queue') and self._audio_queue is not None:
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

    def listen_once(self) -> str:
        """Record once (no wake word) and return transcribed text."""
        self._ensure_stt()
        audio = self._record_until_silence()
        if audio is None or len(audio) == 0:
            return ""
        return self._stt.transcribe(audio)

    def _ensure_stt(self):
        if self._stt is None:
            self._stt = VoskSTT(self.vosk_model_path)

    @staticmethod
    def _resample_16k(audio_float, native_rate):
        """Fast resample to 16kHz using linear interpolation."""
        n_out = int(len(audio_float) * 16000 / native_rate)
        x_in = np.linspace(0, 1, len(audio_float), endpoint=False)
        x_out = np.linspace(0, 1, n_out, endpoint=False)
        resampled = np.interp(x_out, x_in, audio_float)
        return (resampled * 32767).astype(np.int16)

    def _loop(self):
        """Main loop: wake word detection → record → transcribe → callback."""
        from openwakeword.model import Model as OWWModel

        self._ensure_stt()

        # Load wake word model
        oww = OWWModel()
        available_words = list(oww.models.keys())
        print(f"  Wake words available: {available_words}")

        # Pick the matching wake word (or first available)
        target_ww = self.wake_word
        if target_ww not in available_words:
            print(f"  Warning: '{target_ww}' not in available models, using first: {available_words[0]}")
            target_ww = available_words[0]
        print(f"  Listening for: '{target_ww}'")

        # Get mic's native sample rate
        dev_info = sd.query_devices(self.input_device, 'input')
        native_rate = int(dev_info['default_samplerate'])
        # OWW wants 1280 samples at 16kHz = 80ms
        # At 44100Hz that's 3528 samples
        chunk_samples = int(1280 * native_rate / 16000)

        print(f"  Mic: {dev_info['name']} @ {native_rate}Hz")
        print(f"  Voice input ready!")

        audio_queue = queue.Queue(maxsize=200)
        self._audio_queue = audio_queue

        def audio_callback(indata, frames, time_info, status):
            try:
                audio_queue.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass  # drop frames rather than block

        with sd.InputStream(
            device=self.input_device,
            channels=1,
            samplerate=native_rate,
            blocksize=chunk_samples,
            callback=audio_callback,
        ):
            while self._running:
                try:
                    chunk = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                # Skip processing entirely while muted (during TTS playback)
                if self.muted:
                    continue

                # Fast resample to 16kHz
                audio_int16 = self._resample_16k(chunk, native_rate)

                # Feed to wake word model
                prediction = oww.predict(audio_int16)
                score = prediction.get(target_ww, 0)

                if score > self.wake_threshold:
                    print(f"  Wake word detected! (score: {score:.2f})")
                    oww.reset()

                    if self.on_wake:
                        self.on_wake()

                    # Drain the queue so we don't process old audio
                    while not audio_queue.empty():
                        try:
                            audio_queue.get_nowait()
                        except queue.Empty:
                            break

                    # Record speech
                    self._recording = True
                    audio = self._record_speech(audio_queue, native_rate)
                    self._recording = False

                    if audio is not None and len(audio) > 0:
                        text = self._stt.transcribe(audio)
                        if text and len(text.split()) >= 2 and self.on_speech:
                            self.on_speech(text)
                        else:
                            if text and len(text.split()) < 2:
                                print(f"  (Too short, ignoring: \"{text}\")")
                            elif not text:
                                print("  (Didn't catch that)")
                            if self.on_speech_fail:
                                self.on_speech_fail()
                    else:
                        if self.on_speech_fail:
                            self.on_speech_fail()

    def _record_speech(self, audio_queue: queue.Queue, native_rate: int) -> Optional[np.ndarray]:
        """Record until silence or max duration. Returns 16kHz int16 numpy array."""
        print("  Listening...")
        chunks = []
        silence_start = None
        start_time = time.time()

        while self._running:
            elapsed = time.time() - start_time
            if elapsed >= self.max_record_seconds:
                print(f"  (max duration {self.max_record_seconds}s reached)")
                break

            try:
                chunk = audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            audio_int16 = self._resample_16k(chunk, native_rate)
            chunks.append(audio_int16)

            # Check RMS for silence detection (on original float audio)
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms < self.silence_threshold:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= self.silence_duration:
                    print(f"  (silence detected after {elapsed:.1f}s)")
                    break
            else:
                silence_start = None

        if not chunks:
            return None

        return np.concatenate(chunks)

    def _record_until_silence(self) -> Optional[np.ndarray]:
        """One-shot recording (no wake word). Returns 16kHz int16 numpy array."""
        dev_info = sd.query_devices(self.input_device, 'input')
        native_rate = int(dev_info['default_samplerate'])
        chunk_samples = int(native_rate * 0.1)

        audio_queue = queue.Queue(maxsize=200)

        def cb(indata, frames, time_info, status):
            try:
                audio_queue.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass

        chunks = []
        silence_start = None
        start_time = time.time()

        with sd.InputStream(device=self.input_device, channels=1,
                            samplerate=native_rate, blocksize=chunk_samples, callback=cb):
            while time.time() - start_time < self.max_record_seconds:
                try:
                    chunk = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                audio_int16 = self._resample_16k(chunk, native_rate)
                chunks.append(audio_int16)

                rms = np.sqrt(np.mean(chunk ** 2))
                if rms < self.silence_threshold:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= self.silence_duration:
                        break
                else:
                    silence_start = None

        if not chunks:
            return None
        return np.concatenate(chunks)
