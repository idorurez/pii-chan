#!/usr/bin/env python3
"""
ミラ - Main Entry Point

Usage:
    python -m src.main              # Full voice loop (wake word + STT + TTS)
    python -m src.main --simulate   # Text mode with simulated CAN
    python -m src.main --simulator  # Interactive pygame simulator
    python -m src.main --no-voice   # Disable voice output
    python -m src.main --no-mic     # Disable voice input (wake word + STT)
    python -m src.main --no-gateway # Disable OpenClaw gateway (local brain only)
"""

import argparse
import asyncio
import queue
import re
import time
import signal
import sys
import threading
from pathlib import Path

import os
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from .config import Config
from .can_reader import CANReader, CarState, Gear
from .brain import PiiBrain
from .voice import Voice
from .memory import SessionMemory
from .face_server import FaceServer
from .face import Expression

# Global for clean shutdown
running = True

def signal_handler(sig, frame):
    global running
    print("\nShutting down ミラ...")
    running = False


def init_components(args, config):
    """Initialize all ミラ components. Returns (can, voice, voice_input, brain, memory)."""
    print("=" * 50)
    print("ミラ v0.2.0")
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
    print(f"  CAN: {interface}")

    # Voice output (TTS)
    voice_input = None
    if args.no_voice:
        voice = Voice(engine="mock")
        print(f"  TTS: disabled (mock)")
    else:
        voice = Voice(
            engine=config.voice.engine,
            output_device=config.audio.output_device,
            kokoro_voice=config.voice.kokoro_voice,
            piper_model=config.voice.piper_model,
            speaker_id=config.voice.speaker_id,
            speed=config.voice.speed,
            volume=config.voice.volume,
        )
        if voice.is_available():
            print(f"  TTS: {config.voice.engine}")
        else:
            print(f"  TTS: {config.voice.engine} not available, falling back to mock")
            voice = Voice(engine="mock")

    # Voice input (wake word + STT)
    if not args.no_mic and config.voice_input.enabled:
        try:
            from .voice_input import VoiceInput
            voice_input = VoiceInput(
                vosk_model_path=config.voice_input.vosk_model_path,
                wake_word=config.voice_input.wake_word,
                wake_word_model_path=config.voice_input.wake_word_model_path,
                wake_threshold=config.voice_input.wake_word_threshold,
                input_device=config.audio.input_device,
                max_record_seconds=config.voice_input.max_record_seconds,
                silence_threshold=config.voice_input.silence_threshold,
                silence_duration=config.voice_input.silence_duration,
            )
            print(f"  STT: vosk | Wake: {config.voice_input.wake_word}")
        except Exception as e:
            print(f"  STT: failed to init ({e})")
            voice_input = None
    else:
        print(f"  STT: disabled")

    # Brain
    model_path = None if args.no_model else config.llm.model_path
    if model_path and not Path(model_path).exists():
        print(f"  Brain: model not found ({model_path}), using rule-based")
        model_path = None

    brain = PiiBrain(
        model_path=model_path,
        personality_path=config.brain.personality_path,
        context_size=config.llm.context_size,
        max_tokens=config.llm.max_tokens,
        temperature=config.llm.temperature
    )
    print(f"  Brain: {'LLM' if model_path else 'rule-based'}")

    # Memory
    memory = SessionMemory(config.db_path)
    brain.set_memory(memory)
    print(f"  Memory: {config.db_path}")

    # Connect brain to CAN events
    can.add_callback(brain.on_can_event)

    return can, voice, voice_input, brain, memory


def _speak(voice, brain, memory, text):
    """Speak and log (non-blocking)."""
    voice.speak(text, blocking=False)
    if brain.current_session:
        memory.log_speech(text, brain.current_session.session_id)


def think_loop(brain, can, voice, memory, config):
    """Background thread that runs ミラ's think cycle."""
    global running
    think_interval = config.brain.think_interval
    last_think = 0

    while running:
        now = time.time()

        # Check for event-driven responses frequently
        event_response = brain.react_to_event(can.state)
        if event_response:
            _speak(voice, brain, memory, event_response)

        # Idle chatter on longer interval
        elif now - last_think >= think_interval:
            response = brain.think(can.state, cooldown=config.brain.speech_cooldown)
            if response:
                _speak(voice, brain, memory, response)
            last_think = now

        time.sleep(0.2)


def print_help():
    print()
    print("Commands:")
    print("  engine          - Toggle engine on/off")
    print("  gear p/r/n/d    - Change gear")
    print("  speed <kmh>     - Set speed")
    print("  brake           - Toggle brake")
    print("  brake hard      - Hard brake")
    print("  door            - Toggle driver door")
    print("  talk            - Force ミラ to speak")
    print("  voice           - Push-to-talk (record once)")
    print("  shush           - Toggle idle chatter")
    print("  state           - Show car state")
    print("  help            - This help")
    print("  quit / exit     - Exit")
    print()
    print("Or type anything to chat with ミラ!")
    print()


def print_state(state: CarState):
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


class GatewayBridge:
    """Bridges sync voice callbacks to the async OpenClaw gateway node.

    Supports two modes:
    - send_and_wait(): Block until full response (legacy)
    - send_streamed(): Stream deltas via callbacks, push sentences to a queue for TTS
    """

    # Sentence-ending punctuation for chunking streamed text
    _SENTENCE_END = re.compile(r'[.!?]\s|[.!?]$')

    def __init__(self, on_connection_change=None):
        self.node = None
        self._loop = None
        self._thread = None
        self._response_text = None
        self._response_event = threading.Event()
        self._on_connection_change = on_connection_change

        # Streaming state
        self._delta_callback = None
        self._sentence_queue = None
        self._stream_buffer = ""

    def start(self):
        """Try to connect to the OpenClaw gateway. Returns True if connected."""
        try:
            from .node import OpenClawNode
        except ImportError as e:
            print(f"  Gateway: import failed ({e})")
            return False

        self._response_event = threading.Event()

        def on_response(text):
            # Flush any remaining buffered text as final sentence
            if self._sentence_queue is not None:
                remaining = self._stream_buffer.strip()
                if remaining:
                    self._sentence_queue.put(remaining)
                self._sentence_queue.put(None)  # Sentinel: stream done
                self._stream_buffer = ""
            self._response_text = text
            self._response_event.set()

        def on_delta(delta):
            if self._delta_callback:
                self._delta_callback(delta)
            if self._sentence_queue is not None:
                self._stream_buffer += delta
                # Check for complete sentences to push to TTS
                while True:
                    m = self._SENTENCE_END.search(self._stream_buffer)
                    if not m:
                        break
                    # Split at the sentence boundary
                    end = m.end()
                    sentence = self._stream_buffer[:end].strip()
                    self._stream_buffer = self._stream_buffer[end:]
                    if sentence:
                        self._sentence_queue.put(sentence)

        try:
            self.node = OpenClawNode(
                on_response=on_response,
                on_delta=on_delta,
                on_connection_change=self._on_connection_change,
            )
            self.node.load_config()
        except Exception as e:
            print(f"  Gateway: config error ({e})")
            self.node = None
            return False

        # Run the node event loop in a background thread
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True
        )
        self._thread.start()

        # Wait for connection (up to 15s)
        for _ in range(30):
            if self.node.connected:
                print(f"  Gateway: connected")
                return True
            time.sleep(0.5)

        print(f"  Gateway: connection timed out, using local brain")
        return False

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.node.run())

    @property
    def connected(self):
        return self.node is not None and self.node.connected

    def send_and_wait(self, text, timeout=30):
        """Send a voice transcript and wait for the response. Returns text or None."""
        if not self.connected or self._loop is None:
            return None

        self._response_text = None
        self._response_event.clear()
        self._sentence_queue = None
        self._delta_callback = None
        self._stream_buffer = ""

        # Schedule the send on the node's event loop
        future = asyncio.run_coroutine_threadsafe(
            self.node.send_voice_transcript(text), self._loop
        )
        try:
            future.result(timeout=5)
        except Exception as e:
            print(f"  [gateway send error: {e}]")
            return None

        if self._response_event.wait(timeout=timeout):
            return self._response_text
        else:
            print("  [gateway response timeout]")
            return None

    def send_streamed(self, text, sentence_queue, on_delta=None, timeout=30):
        """Send a message and stream the response.

        Deltas are passed to on_delta for display.
        Complete sentences are pushed to sentence_queue for TTS.
        A None sentinel is pushed when the response is complete.
        Returns the full response text, or None on timeout.
        """
        if not self.connected or self._loop is None:
            return None

        self._response_text = None
        self._response_event.clear()
        self._sentence_queue = sentence_queue
        self._delta_callback = on_delta
        self._stream_buffer = ""

        future = asyncio.run_coroutine_threadsafe(
            self.node.send_voice_transcript(text), self._loop
        )
        try:
            future.result(timeout=5)
        except Exception as e:
            print(f"  [gateway send error: {e}]")
            sentence_queue.put(None)
            return None

        if self._response_event.wait(timeout=timeout):
            return self._response_text
        else:
            print("  [gateway response timeout]")
            sentence_queue.put(None)
            return None

    def stop(self):
        if self.node and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.node.disconnect(), self._loop
                ).result(timeout=3)
            except Exception:
                pass


def _chat_with_fallback(gateway, brain, can_state, text):
    """Try gateway first, fall back to local brain. Returns (response, source)."""
    if gateway and gateway.connected:
        response = gateway.send_and_wait(text)
        if response:
            return response, "cloud"
    return brain.chat(text, can_state), "local"


def run_text_mode(args, config):
    """Interactive text-based mode for testing."""
    global running

    can, voice, voice_input, brain, memory = init_components(args, config)

    # Gateway (primary brain)
    gateway = None
    if not args.no_gateway:
        gateway = GatewayBridge()
        if not gateway.start():
            gateway = None

    print()
    print("Text mode ready! Type 'help' for commands.")
    print_help()

    brain.start_session()
    can.start()

    voice.speak("ミラ、オンライン!")

    # Start background think loop
    thinker = threading.Thread(
        target=think_loop, args=(brain, can, voice, memory, config), daemon=True
    )
    thinker.start()

    try:
        while running:
            try:
                cmd = input("mira>").strip().lower()
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
                if voice_input:
                    print("  Recording... speak now")
                    text = voice_input.listen_once()
                    if text:
                        print(f"  Heard: \"{text}\"")
                        response, src = _chat_with_fallback(gateway, brain, can.state, text)
                        print(f"  ({src})")
                        voice.speak(response)
                    else:
                        print("  (Didn't catch that)")
                else:
                    print("  Voice input not available")
            elif verb == "shush":
                brain.idle_chatter = not brain.idle_chatter
                status = "ON" if brain.idle_chatter else "OFF"
                print(f"  Idle chatter {status}")
            elif verb == "state":
                print_state(can.state)
            else:
                if gateway and gateway.connected:
                    # Stream response — print tokens as they arrive
                    sys.stdout.write("  ミラ: ")
                    sys.stdout.flush()
                    sq = queue.Queue()
                    t_send = time.time()
                    t_first = [None]
                    def on_delta(d):
                        if t_first[0] is None:
                            t_first[0] = time.time()
                        sys.stdout.write(d)
                        sys.stdout.flush()
                    response = gateway.send_streamed(cmd, sq, on_delta=on_delta)
                    # Drain the sentence queue (we don't TTS in text mode)
                    while True:
                        s = sq.get()
                        if s is None:
                            break
                    t_done = time.time()
                    ttft = (t_first[0] - t_send) if t_first[0] else 0
                    sys.stdout.write(f"\n  [TTFT: {ttft:.1f}s | total: {t_done-t_send:.1f}s]\n")
                    sys.stdout.flush()
                else:
                    response = brain.chat(cmd, can.state)
                    print(f"  ミラ (local): {response}")

    finally:
        running = False
        print("\nStopping...")
        brain.end_session()
        can.stop()
        if gateway:
            gateway.stop()
        voice.speak("またね!")
        print("Goodbye!")


def run_voice_mode(args, config):
    """Full voice loop: wake word -> STT -> gateway/brain -> TTS."""
    global running

    can, voice, voice_input, brain, memory = init_components(args, config)

    if voice_input is None:
        print("\nError: Voice input not available. Check mic and dependencies.")
        print("Run with --no-mic for passive mode, or --simulate for text mode.")
        return

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Face display server
    face = FaceServer(port=18793, ui_port=8080)
    face.start()

    # Gateway (primary brain — Claude via OpenClaw)
    gateway = None
    if not args.no_gateway:
        def on_gw_connection_change(connected):
            face.controller.state.gateway_connected = connected
            if connected and gateway and gateway.node:
                face.controller.state.gateway_last_connected = gateway.node.last_connected_at or 0
            face.controller._notify()

        gateway = GatewayBridge(on_connection_change=on_gw_connection_change)
        if not gateway.start():
            gateway = None
    face.controller.state.gateway_connected = gateway is not None and gateway.connected
    if gateway and gateway.node and gateway.node.last_connected_at:
        face.controller.state.gateway_last_connected = gateway.node.last_connected_at

    brain.start_session()
    can.start()

    print()
    face.set_expression(Expression.HAPPY)
    voice.speak("ミラ、オンライン!", blocking=True)
    face.set_expression(Expression.NEUTRAL)

    _state = {"post_tts": False}

    def on_wake():
        """Called when wake word is detected."""
        if _state["post_tts"]:
            print("  [wake — suppressed (post-TTS)]")
            return
        print("  [wake]")
        face.listening()
        voice.speak("はい!", blocking=True)

    def on_speech(text):
        """Called when speech is transcribed after wake word."""
        print(f"  You: \"{text}\"")
        face.thinking()
        voice_input.muted = True
        t0 = time.time()

        if gateway and gateway.connected:
            # Streamed: TTS starts on first complete sentence while Claude keeps generating
            sq = queue.Queue()
            _timing = {"first_token": None, "first_sentence": None, "tts_start": None}

            def on_delta(d):
                if _timing["first_token"] is None:
                    _timing["first_token"] = time.time()

            def tts_worker():
                voice.speak_streamed(
                    sq,
                    on_start=lambda: (face.start_speaking(), _timing.__setitem__("tts_start", time.time())),
                    on_done=lambda: face.stop_speaking(),
                )

            tts_thread = threading.Thread(target=tts_worker, daemon=True)
            tts_thread.start()

            response = gateway.send_streamed(text, sq, on_delta=on_delta)
            tts_thread.join(timeout=60)

            t1 = time.time()
            if response is None:
                response = "Sorry, I couldn't reach the gateway."
            print(f"  ミラ: \"{response}\"")
            ttft = (_timing["first_token"] - t0) if _timing["first_token"] else 0
            tts_t = (t1 - _timing["tts_start"]) if _timing["tts_start"] else 0
            print(f"  [TTFT: {ttft:.1f}s | TTS: {tts_t:.1f}s | total: {t1-t0:.1f}s]")
        else:
            response = "Sorry, I couldn't reach the gateway. Try again."
            print(f"  ミラ: \"{response}\"")
            face.start_speaking()
            voice.speak(response, blocking=True)
            face.stop_speaking()

        # Cooldown to avoid self-triggering from speaker audio
        _state["post_tts"] = True
        time.sleep(3.0)
        voice_input.drain_queue()
        time.sleep(0.5)
        voice_input.drain_queue()
        voice_input.muted = False
        # Suppress false wakes for a bit after unmuting
        time.sleep(2.0)
        _state["post_tts"] = False
        # No chime — just return to neutral silently
        face.set_expression(Expression.NEUTRAL)

        if brain.current_session:
            memory.log_speech(response, brain.current_session.session_id)

    def on_speech_fail():
        """Called when wake triggered but no usable speech captured."""
        face.set_expression(Expression.NEUTRAL)

    # Wire up callbacks and start listening
    voice_input.on_wake = on_wake
    voice_input.on_speech = on_speech
    voice_input.on_speech_fail = on_speech_fail
    voice_input.start()

    # Start background think loop (CAN events, idle chatter)
    thinker = threading.Thread(
        target=think_loop, args=(brain, can, voice, memory, config), daemon=True
    )
    thinker.start()

    brain_label = "gateway + local fallback" if gateway else "local only"
    print(f"Voice mode active ({brain_label}). Ctrl+C to stop.\n")

    try:
        while running:
            time.sleep(0.5)
    finally:
        running = False
        print("\nStopping...")
        face.set_expression(Expression.SAD)
        voice_input.stop()
        brain.end_session()
        can.stop()
        if gateway:
            gateway.stop()
        voice.speak("またね!", blocking=True)
        face.stop()
        print("Goodbye!")


def main():
    global running

    parser = argparse.ArgumentParser(description="ミラ - AI Car Companion")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--simulate", action="store_true", help="Text mode with simulated CAN")
    parser.add_argument("--simulator", action="store_true", help="Interactive pygame simulator")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice output (TTS)")
    parser.add_argument("--no-mic", action="store_true", help="Disable voice input (wake word + STT)")
    parser.add_argument("--no-model", action="store_true", help="Rule-based responses (no LLM)")
    parser.add_argument("--no-gateway", action="store_true", help="Disable OpenClaw gateway (local brain only)")
    args = parser.parse_args()

    config = Config.load(args.config)

    if args.simulator:
        from .simulator import DrivingSimulator
        sim = DrivingSimulator(args, config)
        sim.start()
    elif args.simulate:
        run_text_mode(args, config)
    else:
        # Default: full voice mode
        run_voice_mode(args, config)


if __name__ == "__main__":
    main()
