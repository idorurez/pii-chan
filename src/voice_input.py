"""
Voice Input - Speech-to-text for Pii-chan

Supports multiple modes:
- Push-to-talk (simplest, press key to speak)
- Wake word + STT (hands-free with Porcupine/OpenWakeWord)
- Continuous listening (not recommended, resource heavy)

Default: Vosk for STT (lightweight, offline, works on Pi)
"""

import os
import sys
import json
import queue
import threading
import time
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

# Lazy imports for optional dependencies
_vosk = None
_sounddevice = None
_porcupine = None

def _get_vosk():
    global _vosk
    if _vosk is None:
        import vosk
        _vosk = vosk
    return _vosk

def _get_sounddevice():
    global _sounddevice
    if _sounddevice is None:
        import sounddevice as sd
        _sounddevice = sd
    return _sounddevice


@dataclass
class VoiceInputConfig:
    """Configuration for voice input."""
    # STT engine: "vosk" or "whisper" (whisper requires more resources)
    stt_engine: str = "vosk"
    
    # Path to Vosk model directory
    vosk_model_path: str = "./models/vosk-model-small-en-us-0.15"
    
    # Wake word settings (optional)
    wake_word_enabled: bool = False
    wake_word_engine: str = "porcupine"  # "porcupine" or "openwakeword"
    porcupine_access_key: str = ""  # Get free key at picovoice.ai
    wake_word: str = "picovoice"  # Custom wake word or built-in
    
    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    
    # Recording settings
    max_record_seconds: float = 5.0  # Max recording length
    silence_threshold: float = 0.01  # RMS threshold for silence detection
    silence_duration: float = 1.0    # Seconds of silence to stop recording


class VoskSTT:
    """Vosk-based speech-to-text (lightweight, offline)."""
    
    def __init__(self, model_path: str):
        vosk = _get_vosk()
        
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Vosk model not found at {model_path}\n"
                "Download from: https://alphacephei.com/vosk/models\n"
                "Recommended: vosk-model-small-en-us-0.15 (~50MB)"
            )
        
        vosk.SetLogLevel(-1)  # Suppress Vosk logging
        self.model = vosk.Model(model_path)
        self.sample_rate = 16000
        
    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio bytes to text."""
        vosk = _get_vosk()
        
        recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
        recognizer.AcceptWaveform(audio_data)
        result = json.loads(recognizer.FinalResult())
        
        return result.get("text", "").strip()


class AudioRecorder:
    """Record audio from microphone."""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._audio_queue = queue.Queue()
        
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice stream."""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)
        self._audio_queue.put(bytes(indata))
        
    def record(self, duration: float) -> bytes:
        """Record audio for specified duration."""
        sd = _get_sounddevice()
        
        self._audio_queue = queue.Queue()
        audio_chunks = []
        
        with sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.1),  # 100ms blocks
        ):
            start = time.time()
            while time.time() - start < duration:
                try:
                    chunk = self._audio_queue.get(timeout=0.1)
                    audio_chunks.append(chunk)
                except queue.Empty:
                    continue
                    
        return b''.join(audio_chunks)
    
    def record_until_silence(
        self, 
        max_duration: float = 5.0,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.0,
    ) -> bytes:
        """Record until silence is detected or max duration reached."""
        sd = _get_sounddevice()
        import numpy as np
        
        self._audio_queue = queue.Queue()
        audio_chunks = []
        silence_start = None
        
        with sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.1),
        ):
            start = time.time()
            while time.time() - start < max_duration:
                try:
                    chunk = self._audio_queue.get(timeout=0.1)
                    audio_chunks.append(chunk)
                    
                    # Check for silence
                    audio_array = np.frombuffer(chunk, dtype=np.int16)
                    rms = np.sqrt(np.mean(audio_array.astype(float) ** 2)) / 32768
                    
                    if rms < silence_threshold:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= silence_duration:
                            break  # Silence detected, stop recording
                    else:
                        silence_start = None
                        
                except queue.Empty:
                    continue
                    
        return b''.join(audio_chunks)


class VoiceInput:
    """
    Main voice input handler for Pii-chan.
    
    Usage:
        voice_input = VoiceInput(config)
        
        # Push-to-talk mode
        text = voice_input.listen()  # Blocks, records, transcribes
        
        # Or with callback
        voice_input.start_listening(callback=on_speech)
    """
    
    def __init__(self, config: Optional[VoiceInputConfig] = None):
        self.config = config or VoiceInputConfig()
        self._stt = None
        self._recorder = None
        self._wake_word_detector = None
        self._listening = False
        self._callback = None
        
    def _ensure_initialized(self):
        """Lazy initialization of components."""
        if self._stt is None:
            if self.config.stt_engine == "vosk":
                self._stt = VoskSTT(self.config.vosk_model_path)
            else:
                raise ValueError(f"Unknown STT engine: {self.config.stt_engine}")
                
        if self._recorder is None:
            self._recorder = AudioRecorder(
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
            )
            
    def listen(self, prompt: bool = True) -> str:
        """
        Record and transcribe speech (push-to-talk mode).
        
        Args:
            prompt: If True, print a prompt before recording
            
        Returns:
            Transcribed text
        """
        self._ensure_initialized()
        
        if prompt:
            print("🎤 Listening... (speak now)")
            
        # Record with silence detection
        audio = self._recorder.record_until_silence(
            max_duration=self.config.max_record_seconds,
            silence_threshold=self.config.silence_threshold,
            silence_duration=self.config.silence_duration,
        )
        
        if prompt:
            print("🔄 Transcribing...")
            
        text = self._stt.transcribe(audio)
        
        if prompt:
            print(f"📝 Heard: \"{text}\"")
            
        return text
    
    def listen_once(self) -> str:
        """Record and transcribe without prompts."""
        return self.listen(prompt=False)
        
    def start_continuous(self, callback: Callable[[str], None]):
        """
        Start continuous listening with wake word (if enabled) or push-to-talk.
        
        Args:
            callback: Function to call with transcribed text
        """
        self._ensure_initialized()
        self._listening = True
        self._callback = callback
        
        if self.config.wake_word_enabled:
            self._start_wake_word_listening()
        else:
            print("⚠️ Wake word not enabled. Use listen() for push-to-talk.")
            
    def stop_continuous(self):
        """Stop continuous listening."""
        self._listening = False
        
    def _start_wake_word_listening(self):
        """Start wake word detection loop."""
        # TODO: Implement wake word with Porcupine or OpenWakeWord
        # This is a placeholder for now
        raise NotImplementedError(
            "Wake word listening not yet implemented.\n"
            "For now, use push-to-talk mode with listen()"
        )
        
    @staticmethod
    def check_dependencies() -> dict:
        """Check which voice input dependencies are available."""
        results = {}
        
        try:
            import vosk
            results["vosk"] = True
        except ImportError:
            results["vosk"] = False
            
        try:
            import sounddevice
            results["sounddevice"] = True
        except ImportError:
            results["sounddevice"] = False
            
        try:
            import pvporcupine
            results["porcupine"] = True
        except ImportError:
            results["porcupine"] = False
            
        try:
            import numpy
            results["numpy"] = True
        except ImportError:
            results["numpy"] = False
            
        return results
    
    @staticmethod
    def print_setup_instructions():
        """Print setup instructions for voice input."""
        deps = VoiceInput.check_dependencies()
        
        print("\n=== Voice Input Setup ===\n")
        
        # Check dependencies
        print("Dependencies:")
        for dep, installed in deps.items():
            status = "✅" if installed else "❌"
            print(f"  {status} {dep}")
            
        if not all(deps.values()):
            print("\nInstall missing dependencies:")
            print("  pip install vosk sounddevice numpy")
            
        print("\nDownload Vosk model (~50MB):")
        print("  mkdir -p models")
        print("  cd models")
        print("  wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")
        print("  unzip vosk-model-small-en-us-0.15.zip")
        print()


# Convenience function
def listen() -> str:
    """Quick helper to record and transcribe speech."""
    voice_input = VoiceInput()
    return voice_input.listen()


if __name__ == "__main__":
    # Test voice input
    print("Testing voice input...")
    VoiceInput.print_setup_instructions()
    
    deps = VoiceInput.check_dependencies()
    if all(deps.values()):
        print("\nAll dependencies installed! Testing recording...\n")
        try:
            text = listen()
            print(f"\nYou said: {text}")
        except FileNotFoundError as e:
            print(f"\n{e}")
    else:
        print("\nInstall dependencies first.")
