"""
Face Display - Animated expression system for Mira

Manages character expressions and animations for display on screen.
Designed to be rendered via HTML/JS on the Pi's display.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, List
import json
import time


class Expression(Enum):
    """Available facial expressions."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    THINKING = "thinking"
    SURPRISED = "surprised"
    SLEEPY = "sleepy"
    TALKING = "talking"
    CONFUSED = "confused"
    EXCITED = "excited"
    SAD = "sad"
    ANGRY = "angry"  # for fun


class IdleAnimation(Enum):
    """Subtle idle animations that play on top of expressions."""
    NONE = "none"
    BLINK = "blink"
    BREATHE = "breathe"
    LOOK_AROUND = "look_around"
    EAR_TWITCH = "ear_twitch"  # if character has ears


@dataclass
class FaceState:
    """Current state of the face display."""
    expression: Expression = Expression.NEUTRAL
    idle_animation: IdleAnimation = IdleAnimation.BREATHE
    is_speaking: bool = False
    mouth_open: float = 0.0  # 0.0-1.0 for lip sync
    eye_target_x: float = 0.0  # -1.0 to 1.0, for eye tracking
    eye_target_y: float = 0.0
    transition_duration_ms: int = 200  # smooth transition time
    
    def to_dict(self) -> dict:
        return {
            "expression": self.expression.value,
            "idleAnimation": self.idle_animation.value,
            "isSpeaking": self.is_speaking,
            "mouthOpen": self.mouth_open,
            "eyeTargetX": self.eye_target_x,
            "eyeTargetY": self.eye_target_y,
            "transitionDurationMs": self.transition_duration_ms,
            "timestamp": int(time.time() * 1000),
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class FaceController:
    """
    Controls the face display state and sends updates to the renderer.
    
    The renderer is a separate process (HTML/JS in browser) that receives
    state updates via WebSocket or file polling.
    """
    
    def __init__(self, on_state_change: Optional[Callable[[FaceState], None]] = None):
        self.state = FaceState()
        self._on_state_change = on_state_change
        self._speaking_start_time: Optional[float] = None
        
    def set_expression(self, expression: Expression, transition_ms: int = 200):
        """Change facial expression with smooth transition."""
        self.state.expression = expression
        self.state.transition_duration_ms = transition_ms
        self._notify()
        
    def start_speaking(self):
        """Called when TTS starts - enables talking animation."""
        self.state.is_speaking = True
        self.state.expression = Expression.TALKING
        self._speaking_start_time = time.time()
        self._notify()
        
    def stop_speaking(self):
        """Called when TTS ends - return to previous expression."""
        self.state.is_speaking = False
        self.state.mouth_open = 0.0
        self.state.expression = Expression.NEUTRAL
        self._speaking_start_time = None
        self._notify()
        
    def set_mouth_open(self, amount: float):
        """Set mouth openness for lip sync (0.0-1.0)."""
        self.state.mouth_open = max(0.0, min(1.0, amount))
        self._notify()
        
    def look_at(self, x: float, y: float):
        """Set eye target position (-1.0 to 1.0 for each axis)."""
        self.state.eye_target_x = max(-1.0, min(1.0, x))
        self.state.eye_target_y = max(-1.0, min(1.0, y))
        self._notify()
        
    def set_idle_animation(self, animation: IdleAnimation):
        """Change the idle animation style."""
        self.state.idle_animation = animation
        self._notify()
        
    def _notify(self):
        """Notify renderer of state change."""
        if self._on_state_change:
            self._on_state_change(self.state)
    
    # Convenience methods for common state transitions
    
    def thinking(self):
        """Show thinking expression (when waiting for LLM)."""
        self.set_expression(Expression.THINKING)
        self.look_at(0.3, 0.2)  # look slightly up-right
        
    def listening(self):
        """Show attentive expression (during voice input)."""
        self.set_expression(Expression.NEUTRAL)
        self.look_at(0.0, 0.0)  # look straight ahead
        
    def react_happy(self):
        """Quick happy reaction."""
        self.set_expression(Expression.HAPPY, transition_ms=100)
        
    def react_surprised(self):
        """Quick surprise reaction."""
        self.set_expression(Expression.SURPRISED, transition_ms=50)
        
    def go_sleepy(self):
        """Transition to sleepy state (idle for long time)."""
        self.set_expression(Expression.SLEEPY, transition_ms=1000)
        self.set_idle_animation(IdleAnimation.BREATHE)


# Expression mappings for automatic state changes
EMOTION_TO_EXPRESSION = {
    "happy": Expression.HAPPY,
    "sad": Expression.SAD,
    "angry": Expression.ANGRY,
    "surprised": Expression.SURPRISED,
    "confused": Expression.CONFUSED,
    "excited": Expression.EXCITED,
    "thinking": Expression.THINKING,
    "neutral": Expression.NEUTRAL,
}


def expression_from_text(text: str) -> Optional[Expression]:
    """
    Detect expression from response text (simple heuristics).
    Returns None if no clear emotion detected.
    """
    text_lower = text.lower()
    
    # Excited indicators
    if any(w in text_lower for w in ["!", "wow", "amazing", "awesome", "yay"]):
        if text.count("!") >= 2:
            return Expression.EXCITED
        return Expression.HAPPY
    
    # Question/confusion
    if "?" in text and any(w in text_lower for w in ["hmm", "um", "not sure", "maybe"]):
        return Expression.CONFUSED
    
    # Sad indicators
    if any(w in text_lower for w in ["sorry", "sad", "unfortunately", "can't"]):
        return Expression.SAD
    
    # Happy indicators
    if any(w in text_lower for w in ["great", "good", "nice", "happy", "glad", ":)", "hehe"]):
        return Expression.HAPPY
        
    return None
