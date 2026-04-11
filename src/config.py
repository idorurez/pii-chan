"""
Mira Configuration
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

@dataclass
class LLMConfig:
    model_path: str = "./models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    context_size: int = 8192
    max_tokens: int = 100
    temperature: float = 0.9
    top_p: float = 0.9
    
@dataclass
class VoiceOutputConfig:
    engine: str = "auto"  # "auto", "kokoro", "piper", "edge", "voicevox", or "mock"
    # Kokoro settings (English)
    kokoro_voice: str = "af_jessica"  # Kokoro voice name
    # Piper settings (English)
    piper_model: str = "./models/piper/en_US-lessac-medium.onnx"
    # Edge TTS settings (English, cloud)
    edge_voice: str = "en-US-AnaNeural"  # Microsoft neural voice
    # VOICEVOX settings (Japanese)
    speaker_id: int = 3  # ずんだもん ノーマル
    speed: float = 1.0
    volume: float = 0.3  # 0.0 - 1.0

@dataclass
class VoiceInputConfig:
    enabled: bool = True
    stt_engine: str = "vosk"
    vosk_model_path: str = "./models/vosk-model-small-en-us-0.15"
    wake_word_engine: str = "openwakeword"
    wake_word: str = "hey_jarvis"  # openwakeword model name
    wake_word_model_path: Optional[str] = None  # path to custom .tflite model
    wake_word_threshold: float = 0.5
    max_record_seconds: float = 5.0
    silence_threshold: float = 0.20
    silence_duration: float = 1.0

@dataclass
class AudioConfig:
    input_device: Optional[int] = None   # sounddevice device index for mic
    output_device: Optional[int] = None  # sounddevice device index for speaker

@dataclass
class CANConfig:
    interface: str = "mock"  # "socketcan" or "mock"
    channel: str = "can0"
    dbc_path: str = "./data/toyota_sienna.dbc"
    bitrate: int = 500000

@dataclass
class DisplayConfig:
    enabled: bool = True
    width: int = 800
    height: int = 480
    fullscreen: bool = False
    fps: int = 30

@dataclass
class BrainConfig:
    # How often to consider speaking (seconds)
    think_interval: float = 3.0
    # Minimum seconds between speeches
    speech_cooldown: float = 30.0
    # Context window for recent events
    recent_events_window: int = 300  # 5 minutes
    # Personality file
    personality_path: str = "./data/personality.md"

@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    voice: VoiceOutputConfig = field(default_factory=VoiceOutputConfig)
    voice_input: VoiceInputConfig = field(default_factory=VoiceInputConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    can: CANConfig = field(default_factory=CANConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    brain: BrainConfig = field(default_factory=BrainConfig)

    # Database
    db_path: str = "./data/sessions.db"
    
    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        """Load config from YAML file, with defaults for missing values."""
        config = cls()
        
        config_path = Path(path)
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            
            # Merge loaded values
            if "llm" in data:
                for k, v in data["llm"].items():
                    setattr(config.llm, k, v)
            if "voice" in data:
                for k, v in data["voice"].items():
                    if hasattr(config.voice, k):
                        setattr(config.voice, k, v)
            if "voice_input" in data:
                for k, v in data["voice_input"].items():
                    setattr(config.voice_input, k, v)
            if "audio" in data:
                for k, v in data["audio"].items():
                    setattr(config.audio, k, v)
            if "can" in data:
                for k, v in data["can"].items():
                    setattr(config.can, k, v)
            if "display" in data:
                for k, v in data["display"].items():
                    setattr(config.display, k, v)
            if "brain" in data:
                for k, v in data["brain"].items():
                    setattr(config.brain, k, v)
            if "db_path" in data:
                config.db_path = data["db_path"]
                
        return config
    
    def save(self, path: str = "config.yaml"):
        """Save current config to YAML."""
        data = {
            "llm": self.llm.__dict__,
            "voice": self.voice.__dict__,
            "voice_input": self.voice_input.__dict__,
            "audio": self.audio.__dict__,
            "can": self.can.__dict__,
            "display": self.display.__dict__,
            "brain": self.brain.__dict__,
            "db_path": self.db_path,
        }
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
