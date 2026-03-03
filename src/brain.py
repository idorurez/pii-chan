"""
Pii-chan's Brain - LLM integration and context building
"""
import time
import threading
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple
from pathlib import Path
from datetime import datetime
import json

from .can_reader import CarState, Gear
from .memory import SessionMemory, DrivingSession

# Lazy import llama-cpp
_llama_cpp = None
def get_llama():
    global _llama_cpp
    if _llama_cpp is None:
        from llama_cpp import Llama
        _llama_cpp = Llama
    return _llama_cpp

@dataclass
class Event:
    """A notable event during driving."""
    timestamp: float
    event_type: str
    description: str
    
class PiiBrain:
    """
    The brain of Pii-chan - decides when and what to say.
    """
    
    def __init__(self, 
                 model_path: Optional[str] = None,
                 personality_path: str = "./data/personality.md",
                 context_size: int = 4096,
                 max_tokens: int = 100,
                 temperature: float = 0.8):
        
        self.model_path = model_path
        self.context_size = context_size
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Load personality
        self.personality = self._load_personality(personality_path)
        
        # State tracking
        self.recent_events: List[Event] = []
        self.last_speech_time: float = 0
        self.last_speech_text: str = ""
        self.speech_count: int = 0

        # LLM (lazy loaded, with lock for thread-safe access)
        self._llm = None
        self._llm_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        
        # Memory
        self.memory: Optional[SessionMemory] = None
        self.current_session: Optional[DrivingSession] = None
        
    def _load_personality(self, path: str) -> str:
        """Load personality prompt from file."""
        p = Path(path)
        if p.exists():
            return p.read_text(encoding='utf-8')
        return "あなたは優しい車のAIアシスタント、ピーちゃんです。"
        
    def _get_llm(self):
        """Lazy load the LLM (thread-safe)."""
        if self._llm is None and self.model_path:
            with self._llm_lock:
                if self._llm is None:
                    print("  Loading LLM model (first time, may take a moment)...")
                    Llama = get_llama()
                    self._llm = Llama(
                        model_path=self.model_path,
                        n_ctx=self.context_size,
                        n_threads=4,
                        verbose=False
                    )
                    print("  LLM ready!")
        return self._llm
        
    def set_memory(self, memory: SessionMemory):
        """Set the memory system."""
        self.memory = memory
        
    def start_session(self):
        """Start a new driving session."""
        if self.memory:
            self.current_session = self.memory.start_session()
            
    def end_session(self):
        """End the current driving session."""
        if self.memory and self.current_session:
            self.memory.end_session(self.current_session.session_id)
            self.current_session = None
            
    def add_event(self, event_type: str, description: str):
        """Add an event to recent history."""
        event = Event(
            timestamp=time.time(),
            event_type=event_type,
            description=description
        )
        self.recent_events.append(event)
        
        # Keep only recent events (last 5 minutes)
        cutoff = time.time() - 300
        self.recent_events = [e for e in self.recent_events if e.timestamp > cutoff]
        
        # Log to memory
        if self.memory and self.current_session:
            self.memory.log_event(
                self.current_session.session_id,
                event_type,
                {"description": description}
            )
            
    def on_can_event(self, state: CarState, event_name: str):
        """Handle CAN event callback."""
        # Create human-readable description
        descriptions = {
            "engine_start": "エンジンがかかった",
            "engine_stop": "エンジンが止まった",
            "gear_change_park": "パーキングに入れた",
            "gear_change_reverse": "バックギアに入れた",
            "gear_change_drive": "ドライブに入れた",
            "gear_change_neutral": "ニュートラルに入れた",
            "start_moving": "走り始めた",
            "stopped": "停車した",
            "high_speed": "時速100km超えた",
            "door_opened": "ドアが開いた",
            "door_closed": "ドアが閉まった",
            "hard_brake": "急ブレーキをかけた",
            "bsm_left": "左の死角に車がいる",
            "bsm_right": "右の死角に車がいる",
            "fuel_low": "燃料が少なくなった",
        }
        desc = descriptions.get(event_name, event_name)
        self.add_event(event_name, desc)
        
    def build_context(self, state: CarState) -> str:
        """Build the context prompt for the LLM."""
        now = datetime.now()
        
        # Time of day
        hour = now.hour
        if 5 <= hour < 10:
            time_of_day = "朝"
        elif 10 <= hour < 17:
            time_of_day = "昼"
        elif 17 <= hour < 21:
            time_of_day = "夕方"
        else:
            time_of_day = "夜"
            
        # Gear name
        gear_names = {
            Gear.PARK: "P (駐車)",
            Gear.REVERSE: "R (バック)",
            Gear.NEUTRAL: "N (ニュートラル)",
            Gear.DRIVE: "D (ドライブ)",
            Gear.BRAKE: "B (ブレーキ)",
        }
        
        # EV mode names
        ev_modes = {0: "ノーマル", 1: "EV", 2: "ECO", 3: "パワー"}
        
        # Build current state section
        current_state = f"""【現在の状態】
- 時刻: {now.strftime('%H:%M')} ({time_of_day})
- ギア: {gear_names.get(state.gear, '不明')}
- 速度: {state.speed_kmh:.0f} km/h
- エンジン: {'動作中' if state.engine_running else '停止'}
- ハイブリッドバッテリー: {state.battery_soc:.0f}%
- 走行モード: {ev_modes.get(state.ev_mode, 'ノーマル')}
- ブレーキ: {'踏んでいる' if state.brake_pressed else '踏んでいない'}
- ドア: {'開いている' if state.any_door_open else '閉まっている'}"""
        
        # Build recent events section
        if self.recent_events:
            events_text = "\n".join([
                f"- {datetime.fromtimestamp(e.timestamp).strftime('%H:%M:%S')} {e.description}"
                for e in self.recent_events[-10:]  # Last 10 events
            ])
            events_section = f"\n\n【最近の出来事】\n{events_text}"
        else:
            events_section = "\n\n【最近の出来事】\n- 特になし"
            
        # Build history section
        history_section = ""
        if self.memory:
            recent_sessions = self.memory.get_recent_sessions(3)
            if recent_sessions:
                history_items = []
                for session in recent_sessions:
                    if session.end_time:
                        duration_min = (session.end_time - session.start_time) / 60
                        end_str = datetime.fromtimestamp(session.end_time).strftime('%H:%M')
                        history_items.append(
                            f"- {datetime.fromtimestamp(session.start_time).strftime('%m/%d %H:%M')}〜{end_str} ({duration_min:.0f}分)"
                        )
                if history_items:
                    history_section = f"\n\n【最近の運転履歴】\n" + "\n".join(history_items)
                    
        # Last speech info
        if self.last_speech_time > 0:
            seconds_ago = time.time() - self.last_speech_time
            last_speech_section = f"\n\n【ピーちゃんの最後の発言】\n- {seconds_ago:.0f}秒前: 「{self.last_speech_text}」"
        else:
            last_speech_section = "\n\n【ピーちゃんの最後の発言】\n- まだ何も話していない"
            
        # Combine situation sections
        situation = (
            current_state +
            events_section +
            history_section +
            last_speech_section
        )

        return situation
        
    def _generate(self, situation: str) -> str:
        """Send a chat completion request to the LLM and return cleaned text."""
        llm = self._get_llm()

        messages = [
            {"role": "system", "content": self.personality},
            {"role": "user", "content": situation
             + "\n\n上の状況を見て、ピーちゃんとして一言話してください。"
               "話すことがなければ「...」とだけ返してください。"
               "返答はピーちゃんのセリフだけ。短く（1〜2文）、カジュアルに。"},
        ]

        with self._inference_lock:
            response = llm.create_chat_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stop=["---", "【"],
            )

        text = response['choices'][0]['message']['content'].strip()
        # Clean common LLM artifacts
        text = re.sub(r'\(?\d{1,2}:\d{2}\)?', '', text)  # timestamps
        text = re.sub(r'^\[.*?\][:：]?\s*', '', text)     # [返答]: etc
        text = re.sub(r'^ピーちゃん[:：]\s*', '', text)    # "ピーちゃん:" prefix
        text = re.sub(r'^「|」$', '', text)                # stray brackets
        text = text.strip()
        return text

    def think(self, state: CarState, cooldown: float = 30.0) -> Optional[str]:
        """
        Think about whether to say something.
        Returns the response text, or None if staying silent.
        """
        # Check cooldown
        if time.time() - self.last_speech_time < cooldown:
            return None

        # Build context
        situation = self.build_context(state)

        # Get LLM response
        llm = self._get_llm()
        if llm is None:
            return self._rule_based_response(state)

        text = self._generate(situation)

        # Check if model chose to stay silent
        if text in ("...", "") or len(text) < 2:
            return None

        # Record speech
        self.last_speech_time = time.time()
        self.last_speech_text = text
        self.speech_count += 1

        return text
        
    def _rule_based_response(self, state: CarState) -> Optional[str]:
        """Simple rule-based fallback when no LLM is available."""
        # Only respond to significant events
        if not self.recent_events:
            return None
            
        latest = self.recent_events[-1]
        
        # Only respond if event is recent (last 5 seconds)
        if time.time() - latest.timestamp > 5:
            return None
            
        responses = {
            "engine_start": [
                "おはよう！今日もよろしくね♪",
                "ピピッ！エンジンかかったね！",
                "やった、出発だね！",
            ],
            "gear_change_reverse": [
                "バックするの？後ろ気をつけてね〜",
                "後ろ、ちゃんと見てね！",
            ],
            "hard_brake": [
                "わわっ！大丈夫？",
                "びっくりした...！",
            ],
            "fuel_low": [
                "あ、ガソリン少なくなってきたよ〜",
                "そろそろ給油した方がいいかも？",
            ],
        }
        
        import random
        options = responses.get(latest.event_type)
        if options:
            text = random.choice(options)
            self.last_speech_time = time.time()
            self.last_speech_text = text
            return text
            
        return None
        
    def force_response(self, state: CarState) -> str:
        """Force a response, ignoring cooldown. For testing."""
        llm = self._get_llm()
        if llm is None:
            return "ピピッ！テストモードだよ〜"

        situation = self.build_context(state)
        text = self._generate(situation)

        if text in ("...", "") or len(text) < 2:
            text = "ん〜、特に言うことないかな..."

        self.last_speech_time = time.time()
        self.last_speech_text = text
        return text
