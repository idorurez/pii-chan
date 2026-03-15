"""
Tests for Mira's brain
"""
import pytest
import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.can_reader import CarState, Gear
from src.brain import PiiBrain

def test_brain_init():
    """Test brain initializes correctly."""
    brain = PiiBrain(model_path=None)
    assert brain is not None
    assert brain.speech_count == 0
    
def test_brain_event_detection():
    """Test brain detects and stores events."""
    brain = PiiBrain(model_path=None)
    
    # Add event
    brain.add_event("engine_start", "エンジンがかかった")
    
    assert len(brain.recent_events) == 1
    assert brain.recent_events[0].event_type == "engine_start"
    
def test_brain_context_building():
    """Test context is built correctly."""
    brain = PiiBrain(model_path=None)
    
    state = CarState(
        engine_running=True,
        gear=Gear.DRIVE,
        speed_kmh=50.0,
        battery_soc=75.0
    )
    
    context = brain.build_context(state)
    
    # Check context contains expected info
    assert "ドライブ" in context or "D" in context
    assert "50" in context  # Speed
    assert "75" in context  # Battery
    assert "動作中" in context  # Engine running
    
def test_brain_cooldown():
    """Test speech cooldown works."""
    brain = PiiBrain(model_path=None)
    
    state = CarState()
    
    # First thought should work (rule-based will return None without events)
    brain.add_event("engine_start", "エンジンがかかった")
    result1 = brain.think(state, cooldown=10.0)
    
    # Even with event, second thought within cooldown should be None
    brain.add_event("gear_change_drive", "ドライブに入れた")
    result2 = brain.think(state, cooldown=10.0)
    
    # First might have response, second should be None due to cooldown
    if result1 is not None:
        assert result2 is None  # Cooldown should block

def test_brain_rule_based_response():
    """Test rule-based fallback generates responses."""
    brain = PiiBrain(model_path=None)
    
    state = CarState()
    
    # Add recent event
    brain.add_event("engine_start", "エンジンがかかった")
    
    # Force response (bypasses cooldown)
    response = brain.force_response(state)
    
    assert response is not None
    assert len(response) > 0
    
def test_can_event_handling():
    """Test CAN events are processed correctly."""
    brain = PiiBrain(model_path=None)
    
    state = CarState()
    
    # Simulate CAN event
    brain.on_can_event(state, "gear_change_reverse")
    
    assert len(brain.recent_events) == 1
    assert "バック" in brain.recent_events[0].description

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
