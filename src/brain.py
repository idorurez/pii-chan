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
        self._recent_speeches: List[str] = []  # last N speeches for anti-repeat

        # Conversation history for chat mode
        self._chat_history: List[dict] = []

        # LLM (lazy loaded, with lock for thread-safe access)
        self._llm = None
        self._llm_lock = threading.Lock()
        self._inference_lock = threading.Lock()

        # Event-driven speech
        self._pending_events: list = []
        self._event_batch_deadline: float = 0  # when to process batched events
        self._event_batch_window: float = 0.3  # wait this long to batch rapid events

        # Idle chatter control
        self.idle_chatter: bool = True  # False = only respond to events, no unprompted speech

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
            
    # Events that should trigger an immediate response
    REACTIVE_EVENTS = {
        "engine_start", "engine_stop",
        "gear_change_reverse", "gear_change_park", "gear_change_drive",
        "door_opened", "door_closed",
        "hard_brake", "high_speed", "fuel_low",
        "start_moving", "stopped",
        "bsm_left", "bsm_right",
    }

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

        # Queue reactive events — batch rapid events together
        if event_name in self.REACTIVE_EVENTS:
            if not self._pending_events:
                # First event: set a deadline to batch
                self._event_batch_deadline = time.time() + self._event_batch_window
            self._pending_events.append(event_name)
        
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
                    
        # Last speech info — include recent speeches to avoid repeats
        speech_section = ""
        if self._recent_speeches:
            speech_lines = "\n".join(
                f"- 「{s}」" for s in self._recent_speeches[-5:]
            )
            speech_section = f"\n\n【ピーちゃんが最近言ったこと（繰り返さないで！）】\n{speech_lines}"

        # Combine situation sections
        situation = (
            current_state +
            events_section +
            history_section +
            speech_section
        )

        return situation
        
    def _generate(self, situation: str, event_hint: Optional[str] = None) -> str:
        """Send a chat completion request to the LLM and return cleaned text."""
        llm = self._get_llm()

        if event_hint:
            prompt = (
                f"【たった今起きたこと】\n- {event_hint}\n\n"
                + situation
                + "\n\n上の出来事に対してピーちゃんとして一言リアクションしてください。"
                  "返答はセリフだけ。短く（1文）、カジュアルに。"
            )
        else:
            prompt = (
                situation
                + "\n\n上の状況を見て、ピーちゃんとして一言話してください。"
                  "話すことがなければ「...」とだけ返してください。"
                  "返答はセリフだけ。短く（1文）、カジュアルに。"
            )

        # Build system prompt with anti-repeat constraint
        system = self.personality
        if self._recent_speeches:
            forbidden = "、".join(f"「{s}」" for s in self._recent_speeches[-5:])
            system += f"\n\n【重要】以下のセリフは既に使ったので絶対に使わないで。似た表現もダメ：\n{forbidden}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        # Try up to 3 times to get a non-repeated response
        max_attempts = 3
        for attempt in range(max_attempts):
            with self._inference_lock:
                response = llm.create_chat_completion(
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=min(1.2, self.temperature + (attempt * 0.15)),
                    repeat_penalty=1.3,
                    stop=["---", "【"],
                )

            text = response['choices'][0]['message']['content'].strip()
            text = self._clean_response(text)

            # Check if it's a repeat (normalize punctuation for comparison)
            normalized = re.sub(r'[。、♪〜！？!?…]+$', '', text)
            recent_normalized = [
                re.sub(r'[。、♪〜！？!?…]+$', '', s) for s in self._recent_speeches
            ]
            if text and normalized not in recent_normalized:
                return text

        # All attempts repeated — return last attempt anyway
        return text

    @staticmethod
    def _clean_response(text: str) -> str:
        """Clean common LLM artifacts from response text."""
        text = re.sub(r'\(?\d{1,2}:\d{2}\)?', '', text)  # timestamps
        text = re.sub(r'^\[.*?\][:：]?\s*', '', text)     # [返答]: etc
        text = re.sub(r'^ピーちゃん[:：]\s*', '', text)    # "ピーちゃん:" prefix
        text = re.sub(r'^「|」$', '', text)                # stray brackets
        # Kill degenerate repetition (same char 5+ times)
        text = re.sub(r'(.)\1{4,}', r'\1\1', text)
        return text.strip()

    def _record_speech(self, text: str):
        """Record a speech for tracking."""
        self.last_speech_time = time.time()
        self.last_speech_text = text
        self.speech_count += 1
        self._recent_speeches.append(text)
        if len(self._recent_speeches) > 10:
            self._recent_speeches.pop(0)

    # Priority order — higher priority events win when batched
    EVENT_PRIORITY = {
        "hard_brake": 10,
        "bsm_left": 9, "bsm_right": 9,
        "fuel_low": 8,
        "high_speed": 7,
        "gear_change_reverse": 6,
        "engine_start": 5, "engine_stop": 5,
        "door_opened": 4,
        "gear_change_drive": 3, "gear_change_park": 3,
        "start_moving": 2, "stopped": 2,
        "door_closed": 1,
    }

    # Event descriptions for LLM hint
    EVENT_DESCRIPTIONS = {
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

    def react_to_event(self, state: CarState) -> Optional[str]:
        """React to pending events after batch window expires."""
        if not self._pending_events:
            return None

        # Wait for batch window to close (more events might come)
        now = time.time()
        if now < self._event_batch_deadline:
            return None

        # Pick highest-priority event from the batch
        events = self._pending_events[:]
        self._pending_events.clear()

        best = max(events, key=lambda e: self.EVENT_PRIORITY.get(e, 0))

        llm = self._get_llm()
        if llm is None:
            return self._rule_based_response_for(best)

        situation = self.build_context(state)
        event_hint = self.EVENT_DESCRIPTIONS.get(best, best)
        text = self._generate(situation, event_hint=event_hint)

        if text in ("...", "") or len(text) < 2:
            return None

        self._record_speech(text)
        return text

    def think(self, state: CarState, cooldown: float = 30.0) -> Optional[str]:
        """
        Think about whether to say something.
        Returns the response text, or None if staying silent.
        """
        # Idle chatter disabled
        if not self.idle_chatter:
            return None

        # Idle chatter — longer cooldown
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

        self._record_speech(text)

        return text
        
    RULE_BASED_RESPONSES = {
        "engine_start": [
            "おはよう！今日もよろしくね♪",
            "ピピッ！エンジンかかったね！",
            "やった、出発だね！",
        ],
        "engine_stop": [
            "お疲れさま〜！",
            "到着かな？お疲れさま！",
        ],
        "gear_change_reverse": [
            "バックするの？後ろ気をつけてね〜",
            "後ろ、ちゃんと見てね！",
        ],
        "gear_change_drive": [
            "出発だね！",
            "行こう行こう〜！",
        ],
        "gear_change_park": [
            "パーキングだね",
            "停まるのかな？",
        ],
        "start_moving": [
            "動き出したね〜",
            "しゅっぱーつ！",
        ],
        "stopped": [
            "止まったね",
        ],
        "high_speed": [
            "ちょっと速いかも...？",
            "スピード出てるよ〜気をつけてね",
        ],
        "door_opened": [
            "ドア開いてるよ〜",
            "あ、ドア開いた！",
        ],
        "door_closed": [
            "ドア閉まったね、OK！",
        ],
        "hard_brake": [
            "わわっ！大丈夫？",
            "びっくりした...！",
        ],
        "fuel_low": [
            "あ、ガソリン少なくなってきたよ〜",
            "そろそろ給油した方がいいかも？",
        ],
        "bsm_left": [
            "左に車いるよ！気をつけて！",
        ],
        "bsm_right": [
            "右に車いるよ！気をつけて！",
        ],
    }

    def _rule_based_response_for(self, event_type: str) -> Optional[str]:
        """Get a rule-based response for a specific event."""
        import random
        options = self.RULE_BASED_RESPONSES.get(event_type)
        if options:
            text = random.choice(options)
            self.last_speech_time = time.time()
            self.last_speech_text = text
            return text
        return None

    def _rule_based_response(self, state: CarState) -> Optional[str]:
        """Rule-based fallback for idle think (no specific event)."""
        if not self.recent_events:
            return None
        latest = self.recent_events[-1]
        if time.time() - latest.timestamp > 10:
            return None
        return self._rule_based_response_for(latest.event_type)
        
    def force_response(self, state: CarState) -> str:
        """Force a response, ignoring cooldown. For testing."""
        llm = self._get_llm()
        if llm is None:
            return "ピピッ！テストモードだよ〜"

        situation = self.build_context(state)
        text = self._generate(situation)

        if text in ("...", "") or len(text) < 2:
            text = "ん〜、特に言うことないかな..."

        self._record_speech(text)
        return text

    def chat(self, user_message: str, state: CarState) -> str:
        """Have a conversation with the driver."""
        llm = self._get_llm()
        if llm is None:
            return "ピピッ！ごめんね、今はお話モードじゃないの〜"

        situation = self.build_context(state)

        # Build messages with conversation history
        messages = [
            {"role": "system", "content": self.personality
             + "\n\nドライバーが話しかけてきました。車の状況を踏まえて、"
               "ピーちゃんとして自然に会話してください。"
               "返答は短く（1〜3文）、カジュアルに。\n\n" + situation},
        ]

        # Add recent conversation history (last 6 turns)
        for msg in self._chat_history[-6:]:
            messages.append(msg)

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        with self._inference_lock:
            response = llm.create_chat_completion(
                messages=messages,
                max_tokens=60,
                temperature=self.temperature,
                repeat_penalty=1.3,
                stop=["---", "【", "\n\n"],
            )

        text = response['choices'][0]['message']['content'].strip()
        # Take only the first line if multi-line
        text = text.split('\n')[0].strip()
        text = self._clean_response(text)

        if not text or len(text) < 2:
            text = "ん？なんだろ〜"

        # Save to conversation history
        self._chat_history.append({"role": "user", "content": user_message})
        self._chat_history.append({"role": "assistant", "content": text})
        # Keep history bounded
        if len(self._chat_history) > 20:
            self._chat_history = self._chat_history[-12:]

        self._record_speech(text)
        return text
