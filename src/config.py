"""
Pii-chan Configuration
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
    temperature: float = 0.8
    top_p: float = 0.9
    
@dataclass
class VoiceConfig:
    engine: str = "mock"  # "voicevox" or "mock"
    voicevox_url: str = "http://localhost:50021"
    speaker_id: int = 1  # VOICEVOX character ID
    speed: float = 1.1

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
    voice: VoiceConfig = field(default_factory=VoiceConfig)
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
                    setattr(config.voice, k, v)
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
            "can": self.can.__dict__,
            "display": self.display.__dict__,
            "brain": self.brain.__dict__,
            "db_path": self.db_path,
        }
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
