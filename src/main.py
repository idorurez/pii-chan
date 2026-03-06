#!/usr/bin/env python3
"""
ピーちゃん (Pii-chan) - Main Entry Point

Usage:
    python -m src.main              # Run with real CAN (requires hardware)
    python -m src.main --simulate   # Run with simulated CAN data
    python -m src.main --simulator  # Run interactive driving simulator
"""

import argparse
import time
import signal
import sys
import threading
from pathlib import Path

# Fix Windows console encoding for Japanese/emoji output
import os
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from .config import Config
from .can_reader import CANReader, CarState, Gear
from .brain import PiiBrain
from .voice import Voice, VoiceConfig
from .memory import SessionMemory

# Global for clean shutdown
running = True

def signal_handler(sig, frame):
    global running
    print("\n👋 Shutting down Pii-chan...")
    running = False


def init_components(args, config):
    """Initialize all Pii-chan components. Returns (can, voice, brain, memory)."""
    print("=" * 50)
    print("🐣 ピーちゃん (Pii-chan) v0.1.0")
    print("=" * 50)
    print()
    print("Initializing components...")

    # CAN reader
    interface = "mock" if args.simulate else config.can.interface
    can = CANReader(
        interface=interface,
        channel=config.can.channel,
        dbc_path=config.can.dbc_path
    )
    print(f"  ✓ CAN interface: {interface}")

    # Voice
    if args.no_voice:
        voice = Voice(VoiceConfig(engine="mock"))
        print("  ✓ Voice: disabled (mock)")
    else:
        voice = Voice(VoiceConfig(
            engine=config.voice.engine,
            voicevox_url=config.voice.voicevox_url,
            speaker_id=config.voice.speaker_id,
            speed=config.voice.speed
        ))
        if voice.is_available():
            print(f"  ✓ Voice: {config.voice.engine}")
        else:
            print(f"  ⚠ Voice: VOICEVOX not available, using mock")
            voice = Voice(VoiceConfig(engine="mock"))

    # Brain
    model_path = None if args.no_model else config.llm.model_path
    if model_path and not Path(model_path).exists():
        print(f"  ⚠ Model not found: {model_path}")
        print("    Running in rule-based mode")
        model_path = None

    brain = PiiBrain(
        model_path=model_path,
        personality_path=config.brain.personality_path,
        context_size=config.llm.context_size,
        max_tokens=config.llm.max_tokens,
        temperature=config.llm.temperature
    )
    print(f"  ✓ Brain: {'LLM' if model_path else 'rule-based'}")

    # Memory
    memory = SessionMemory(config.db_path)
    brain.set_memory(memory)
    print(f"  ✓ Memory: {config.db_path}")

    # Connect brain to CAN events
    can.add_callback(brain.on_can_event)

    return can, voice, brain, memory


def print_help():
    """Print available text-mode commands."""
    print()
    print("Commands:")
    print("  engine          - Toggle engine on/off")
    print("  gear p/r/n/d    - Change gear (park/reverse/neutral/drive)")
    print("  speed <kmh>     - Set speed (e.g. 'speed 60')")
    print("  brake           - Toggle brake")
    print("  brake hard      - Hard brake")
    print("  door            - Toggle driver door open/close")
    print("  talk            - Force Pii-chan to speak")
    print("  voice           - Talk to Pii-chan with your voice (push-to-talk)")
    print("  shush           - Toggle idle chatter on/off")
    print("  state           - Show current car state")
    print("  help            - Show this help")
    print("  quit / exit     - Exit")
    print()
    print("Or just type anything else to chat with Pii-chan!")
    print()


def print_state(state: CarState):
    """Print current car state summary."""
    gear_names = {
        Gear.PARK: "P", Gear.REVERSE: "R",
        Gear.NEUTRAL: "N", Gear.DRIVE: "D", Gear.BRAKE: "B",
    }
    print()
    print(f"  Engine:  {'ON (RPM: {:.0f})'.format(state.engine_rpm) if state.engine_running else 'OFF'}")
    print(f"  Gear:    {gear_names.get(state.gear, '?')}")
    print(f"  Speed:   {state.speed_kmh:.0f} km/h")
    print(f"  Brake:   {'PRESSED' if state.brake_pressed else 'released'}")
    print(f"  Door:    {'OPEN' if state.any_door_open else 'closed'}")
    print(f"  Battery: {state.battery_soc:.0f}%")
    print()


def _speak(voice, brain, memory, text):
    """Speak and log (non-blocking)."""
    voice.speak(text, blocking=False)
    if brain.current_session:
        memory.log_speech(text, brain.current_session.session_id)


def think_loop(brain, can, voice, memory, config):
    """Background thread that runs Pii-chan's think cycle."""
    global running
    think_interval = config.brain.think_interval
    last_think = 0

    while running:
        now = time.time()

        # Check for event-driven responses frequently (every tick)
        event_response = brain.react_to_event(can.state)
        if event_response:
            _speak(voice, brain, memory, event_response)

        # Idle chatter on longer interval
        elif now - last_think >= think_interval:
            response = brain.think(
                can.state,
                cooldown=config.brain.speech_cooldown
            )
            if response:
                _speak(voice, brain, memory, response)
            last_think = now

        time.sleep(0.2)


def run_text_mode(args, config):
    """Interactive text-based mode for testing without pygame."""
    global running

    can, voice, brain, memory = init_components(args, config)

    print()
    print("Text mode ready! Type 'help' for commands.")
    print_help()

    # Start session and CAN
    brain.start_session()
    can.start()

    # Greeting
    voice.speak("Beep! Pii-chan online. Ready when you are!")

    # Start background think loop
    thinker = threading.Thread(target=think_loop, args=(brain, can, voice, memory, config), daemon=True)
    thinker.start()

    try:
        while running:
            try:
                cmd = input("pii> ").strip().lower()
            except EOFError:
                break

            if not cmd:
                continue

            parts = cmd.split()
            verb = parts[0]

            if verb in ("quit", "exit", "q"):
                break

            elif verb == "help":
                print_help()

            elif verb == "engine":
                new_state = not can.state.engine_running
                can.mock_set_engine(new_state, rpm=800 if new_state else 0)
                print(f"  Engine {'ON' if new_state else 'OFF'}")

            elif verb == "gear":
                if len(parts) < 2:
                    print("  Usage: gear p/r/n/d")
                    continue
                gear_map = {
                    "p": Gear.PARK, "park": Gear.PARK,
                    "r": Gear.REVERSE, "reverse": Gear.REVERSE,
                    "n": Gear.NEUTRAL, "neutral": Gear.NEUTRAL,
                    "d": Gear.DRIVE, "drive": Gear.DRIVE,
                    "b": Gear.BRAKE, "brake": Gear.BRAKE,
                }
                g = gear_map.get(parts[1])
                if g is None:
                    print(f"  Unknown gear '{parts[1]}'. Use p/r/n/d/b")
                else:
                    can.mock_set_gear(g)
                    print(f"  Gear -> {g.name}")

            elif verb == "speed":
                if len(parts) < 2:
                    print("  Usage: speed <kmh>")
                    continue
                try:
                    spd = float(parts[1])
                    can.mock_set_speed(max(0, spd))
                    print(f"  Speed -> {spd:.0f} km/h")
                except ValueError:
                    print(f"  Invalid speed '{parts[1]}'")

            elif verb == "brake":
                if len(parts) >= 2 and parts[1] == "hard":
                    can.mock_set_brake(True, pressure=150)
                    print("  HARD BRAKE!")
                else:
                    new_brake = not can.state.brake_pressed
                    can.mock_set_brake(new_brake)
                    print(f"  Brake {'PRESSED' if new_brake else 'released'}")

            elif verb == "door":
                new_door = not can.state.door_fl_open
                can.mock_set_doors(fl=new_door)
                print(f"  Driver door {'OPEN' if new_door else 'CLOSED'}")

            elif verb == "talk":
                response = brain.force_response(can.state)
                voice.speak(response)

            elif verb == "voice":
                # Push-to-talk voice input
                try:
                    from .voice_input import VoiceInput
                    vi = VoiceInput()
                    text = vi.listen()
                    if text:
                        response = brain.chat(text, can.state)
                        voice.speak(response)
                    else:
                        print("  (Didn't catch that)")
                except ImportError as e:
                    print(f"  Voice input not available: {e}")
                    print("  Run: pip install vosk sounddevice numpy")
                    print("  See docs/VOICE_INPUT.md for setup")
                except FileNotFoundError as e:
                    print(f"  {e}")

            elif verb == "shush":
                brain.idle_chatter = not brain.idle_chatter
                if brain.idle_chatter:
                    print("  Idle chatter ON (Pii-chan will talk unprompted)")
                else:
                    print("  Idle chatter OFF (events only)")

            elif verb == "state":
                print_state(can.state)

            else:
                # Not a command — talk to Pii-chan
                response = brain.chat(cmd, can.state)
                voice.speak(response)

    finally:
        running = False
        print("\nStopping...")
        brain.end_session()
        can.stop()
        voice.speak("See you next time!")
        print("👋 Goodbye!")


def run_passive_mode(args, config):
    """Passive mode — just listens to CAN and speaks. For real hardware."""
    global running

    can, voice, brain, memory = init_components(args, config)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print()
    print("Passive mode — listening to CAN bus...")
    print("(Press Ctrl+C to stop)")
    print()

    brain.start_session()
    can.start()
    voice.speak("Beep! Pii-chan online. Ready when you are!")

    try:
        think_loop(brain, can, voice, memory, config)
    finally:
        print("\nStopping...")
        brain.end_session()
        can.stop()
        voice.speak("See you next time!")
        print("👋 Goodbye!")


def main():
    global running

    parser = argparse.ArgumentParser(description="Pii-chan - AI Car Companion")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--simulate", action="store_true", help="Use simulated CAN data (text mode)")
    parser.add_argument("--simulator", action="store_true", help="Run interactive pygame simulator")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice output")
    parser.add_argument("--no-model", action="store_true", help="Use rule-based responses (no LLM)")
    args = parser.parse_args()

    config = Config.load(args.config)

    if args.simulator:
        from .simulator import DrivingSimulator
        sim = DrivingSimulator(config)
        sim.start()
    elif args.simulate:
        run_text_mode(args, config)
    else:
        run_passive_mode(args, config)


if __name__ == "__main__":
    main()
