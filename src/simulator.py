"""
Desktop Driving Simulator - Test Pii-chan without a car

Pygame GUI mode:
    SPACE       Engine on/off
    P/R/N/D     Gear
    UP/DOWN     Accelerate / Brake
    B           Hard brake
    O           Toggle door
    S           Toggle idle chatter (shush)
    F           Force Pii-chan to speak
    C           Chat (type a message)
    ESC         Quit

Falls back to text mode if pygame is not installed.
"""
import sys
import time
import threading
from typing import Optional

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

from .can_reader import CANReader, CarState, Gear
from .brain import PiiBrain
from .voice import Voice
from .memory import SessionMemory
from .config import Config
from .main import init_components, think_loop, _speak, print_help, print_state


def _find_japanese_font():
    """Find a system font that supports Japanese characters."""
    if not PYGAME_AVAILABLE:
        return None

    # Try common Japanese font names across platforms
    jp_fonts = [
        # Windows
        "yugothic", "yu gothic", "meiryo", "ms gothic", "msgothic",
        "ms pgothic", "mspgothic", "ms mincho",
        # macOS
        "hiragino sans", "hiragino kaku gothic pro",
        # Linux
        "noto sans cjk jp", "noto sans cjk", "takao gothic",
        "ipa gothic", "ipagothic", "vlgothic",
    ]

    available = pygame.font.get_fonts()
    for name in jp_fonts:
        # pygame normalises font names (lowercase, no spaces)
        normalised = name.replace(" ", "").lower()
        if normalised in available:
            return pygame.font.SysFont(normalised, 22)

    # Last resort: try matching substring
    for avail in available:
        if any(k in avail for k in ("gothic", "meiryo", "cjk", "mincho")):
            return pygame.font.SysFont(avail, 22)

    return None


class DrivingSimulator:
    """Interactive driving simulator for testing Pii-chan."""

    def __init__(self, args, config: Optional[Config] = None):
        self.args = args
        self.config = config or Config()
        self.running = False
        self.speed_target = 0.0

        # Initialised by start() via init_components
        self.can = None
        self.voice = None
        self.brain = None
        self.memory = None

        # PyGame
        self.screen = None
        self.clock = None
        self.font = None
        self.font_small = None

        # Chat input state
        self._chat_active = False
        self._chat_text = ""
        self._last_chat_response = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the simulator."""
        # Simulator always uses mock CAN
        self.args.simulate = True
        self.can, self.voice, _voice_input, self.brain, self.memory = (
            init_components(self.args, self.config)
        )

        if not PYGAME_AVAILABLE:
            print("pygame not installed — running in text mode")
            self._run_text_mode()
            return

        pygame.init()
        self.screen = pygame.display.set_mode((900, 650))
        pygame.display.set_caption("Pii-chan Simulator")
        self.clock = pygame.time.Clock()

        # Try to load a Japanese-capable font; fall back to default
        self.font = _find_japanese_font() or pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)

        # Session
        self.brain.start_session()
        self.can.start()
        self.running = True

        # Greeting
        self.voice.speak("Beep! Pii-chan online. Ready when you are!", blocking=False)

        # Reuse the shared think loop from main.py
        thinker = threading.Thread(
            target=self._think_wrapper, daemon=True
        )
        thinker.start()

        try:
            self._run_pygame()
        finally:
            self.running = False
            import src.main as _main
            _main.running = False  # stop think_loop
            self.voice.speak("See you next time!", blocking=True)
            self.brain.end_session()
            self.can.stop()
            pygame.quit()

    def _think_wrapper(self):
        """Run think_loop, syncing main.running with self.running."""
        import src.main as _main
        _main.running = True
        think_loop(self.brain, self.can, self.voice, self.memory, self.config)

    # ------------------------------------------------------------------
    # Pygame main loop
    # ------------------------------------------------------------------

    def _run_pygame(self):
        """Main PyGame loop."""
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if self._chat_active:
                        self._handle_chat_key(event)
                    else:
                        self._handle_key(event.key)

            self._update_simulation()
            self._draw()
            self.clock.tick(30)

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def _handle_key(self, key):
        """Handle keyboard input (normal mode)."""
        state = self.can.state

        if key == pygame.K_ESCAPE:
            self.running = False

        elif key == pygame.K_SPACE:
            new = not state.engine_running
            self.can.mock_set_engine(new, rpm=800 if new else 0)

        elif key == pygame.K_p:
            self.can.mock_set_gear(Gear.PARK)
            self.speed_target = 0
        elif key == pygame.K_r:
            self.can.mock_set_gear(Gear.REVERSE)
        elif key == pygame.K_n:
            self.can.mock_set_gear(Gear.NEUTRAL)
        elif key == pygame.K_d:
            self.can.mock_set_gear(Gear.DRIVE)

        elif key == pygame.K_UP:
            if state.engine_running and state.gear in (Gear.DRIVE, Gear.REVERSE):
                self.speed_target = min(self.speed_target + 10, 120)
        elif key == pygame.K_DOWN:
            self.speed_target = max(self.speed_target - 20, 0)
            if self.speed_target == 0:
                self.can.mock_set_brake(True, 80)
            else:
                self.can.mock_set_brake(False)

        elif key == pygame.K_b:
            self.can.mock_set_brake(True, pressure=150)

        elif key == pygame.K_o:
            self.can.mock_set_doors(fl=not state.door_fl_open)

        elif key == pygame.K_s:
            self.brain.idle_chatter = not self.brain.idle_chatter

        elif key == pygame.K_f:
            response = self.brain.force_response(state)
            self.voice.speak(response, blocking=False)
            if self.brain.current_session:
                self.memory.log_speech(response, self.brain.current_session.session_id)

        elif key == pygame.K_c:
            self._chat_active = True
            self._chat_text = ""

    def _handle_chat_key(self, event):
        """Handle keyboard input while chat box is active."""
        if event.key == pygame.K_ESCAPE:
            self._chat_active = False
            self._chat_text = ""
        elif event.key == pygame.K_RETURN:
            if self._chat_text.strip():
                msg = self._chat_text.strip()
                self._chat_active = False
                self._chat_text = ""
                # Run chat in background so we don't block the render loop
                threading.Thread(
                    target=self._do_chat, args=(msg,), daemon=True
                ).start()
            else:
                self._chat_active = False
                self._chat_text = ""
        elif event.key == pygame.K_BACKSPACE:
            self._chat_text = self._chat_text[:-1]
        elif event.unicode and event.unicode.isprintable():
            self._chat_text += event.unicode

    def _do_chat(self, message: str):
        """Send a chat message to the brain (runs in thread)."""
        response = self.brain.chat(message, self.can.state)
        self._last_chat_response = response
        self.voice.speak(response, blocking=False)
        if self.brain.current_session:
            self.memory.log_speech(response, self.brain.current_session.session_id)

    # ------------------------------------------------------------------
    # Simulation physics
    # ------------------------------------------------------------------

    def _update_simulation(self):
        """Update simulated car state."""
        state = self.can.state
        if state.engine_running:
            diff = self.speed_target - state.speed_kmh
            if abs(diff) > 0.5:
                new_speed = state.speed_kmh + (diff * 0.1)
                self.can.mock_set_speed(max(0, new_speed))
                rpm = 800 + (state.speed_kmh * 30)
                self.can.mock_set_engine(True, rpm)
        else:
            if state.speed_kmh > 0:
                self.can.mock_set_speed(state.speed_kmh * 0.95)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self):
        """Draw the simulator UI."""
        state = self.can.state
        self.screen.fill((30, 30, 40))

        # ---- Title ----
        self._text("Pii-chan Driving Simulator", 20, 15, (255, 255, 255))

        # ---- Car state (left column) ----
        y = 60
        gear_names = {
            Gear.PARK: "P", Gear.REVERSE: "R", Gear.NEUTRAL: "N",
            Gear.DRIVE: "D", Gear.BRAKE: "B",
        }
        self._text(
            f"Engine: {'ON' if state.engine_running else 'OFF'}",
            20, y,
            (100, 255, 100) if state.engine_running else (255, 100, 100),
        )
        y += 28
        self._text(f"Gear: {gear_names.get(state.gear, '?')}", 20, y, (255, 255, 255))
        y += 28
        self._text(f"Speed: {state.speed_kmh:.0f} km/h", 20, y, (255, 255, 255))
        y += 28
        self._text(f"RPM: {state.engine_rpm:.0f}", 20, y, (200, 200, 200))
        y += 28
        self._text(
            f"Brake: {'ON' if state.brake_pressed else 'OFF'}",
            20, y,
            (255, 100, 100) if state.brake_pressed else (100, 100, 100),
        )
        y += 28
        self._text(
            f"Door: {'OPEN' if state.any_door_open else 'Closed'}",
            20, y,
            (255, 200, 100) if state.any_door_open else (100, 100, 100),
        )
        y += 28
        self._text(f"Battery: {state.battery_soc:.0f}%", 20, y, (200, 200, 200))
        y += 36

        # ---- Status ----
        chatter_label = "ON" if self.brain.idle_chatter else "OFF"
        chatter_color = (100, 255, 100) if self.brain.idle_chatter else (255, 100, 100)
        self._text(f"Idle chatter: {chatter_label}", 20, y, chatter_color)
        y += 36

        # ---- Controls ----
        self._text("Controls:", 20, y, (150, 150, 150))
        y += 22
        controls = [
            "SPACE - Engine",
            "P/R/N/D - Gear",
            "UP/DOWN - Speed",
            "B - Hard brake",
            "O - Door",
            "S - Shush (idle chatter)",
            "F - Force speak",
            "C - Chat",
            "ESC - Quit",
        ]
        for ctrl in controls:
            self._text(ctrl, 30, y, (120, 120, 120), small=True)
            y += 18

        # ---- Recent events (right column) ----
        x = 420
        y = 60
        self._text("Recent Events:", x, y, (150, 150, 150))
        y += 25
        for ev in self.brain.recent_events[-10:]:
            self._text(f"- {ev.description}", x + 10, y, (180, 180, 180), small=True)
            y += 20

        # ---- Last speech (bottom) ----
        y = 480
        self._text("Last speech:", 20, y, (150, 150, 150))
        y += 25
        speech = self.brain.last_speech_text or "(waiting...)"
        color = (100, 200, 255) if self.brain.last_speech_text else (80, 80, 80)
        self._text(speech, 30, y, color)

        # ---- Chat response ----
        if self._last_chat_response:
            y += 25
            self._text(f"Chat: {self._last_chat_response}", 30, y, (180, 255, 180))

        # ---- Chat input box ----
        if self._chat_active:
            box_y = 600
            pygame.draw.rect(self.screen, (50, 50, 70), (10, box_y, 880, 40))
            pygame.draw.rect(self.screen, (100, 200, 255), (10, box_y, 880, 40), 2)
            prompt = f"> {self._chat_text}_"
            self._text(prompt, 20, box_y + 8, (255, 255, 255))

        pygame.display.flip()

    def _text(self, text: str, x: int, y: int, color, small: bool = False):
        """Render text to screen."""
        font = self.font_small if small else self.font
        try:
            surface = font.render(text, True, color)
            self.screen.blit(surface, (x, y))
        except Exception:
            # Font can't render some chars — try without problematic chars
            safe = text.encode('ascii', 'replace').decode('ascii')
            surface = font.render(safe, True, color)
            self.screen.blit(surface, (x, y))

    # ------------------------------------------------------------------
    # Text fallback mode (no pygame)
    # ------------------------------------------------------------------

    def _run_text_mode(self):
        """Run in text-only mode without pygame."""
        import src.main as _main

        self.brain.start_session()
        self.can.start()
        self.running = True

        self.voice.speak("Beep! Pii-chan online. Ready when you are!", blocking=False)

        # Reuse shared think loop
        _main.running = True
        thinker = threading.Thread(
            target=think_loop,
            args=(self.brain, self.can, self.voice, self.memory, self.config),
            daemon=True,
        )
        thinker.start()

        print_help()

        try:
            while self.running:
                try:
                    cmd = input("pii> ").strip()
                except EOFError:
                    break

                if not cmd:
                    continue

                parts = cmd.lower().split()
                verb = parts[0]

                if verb in ("quit", "exit", "q"):
                    break
                elif verb == "help":
                    print_help()
                elif verb == "engine":
                    new = not self.can.state.engine_running
                    self.can.mock_set_engine(new, rpm=800 if new else 0)
                    print(f"  Engine {'ON' if new else 'OFF'}")
                elif verb == "gear":
                    if len(parts) < 2:
                        print("  Usage: gear p/r/n/d")
                        continue
                    gear_map = {
                        "p": Gear.PARK, "r": Gear.REVERSE,
                        "n": Gear.NEUTRAL, "d": Gear.DRIVE,
                        "b": Gear.BRAKE,
                    }
                    g = gear_map.get(parts[1])
                    if g is None:
                        print(f"  Unknown gear '{parts[1]}'")
                    else:
                        self.can.mock_set_gear(g)
                        print(f"  Gear -> {g.name}")
                elif verb == "speed":
                    if len(parts) < 2:
                        print("  Usage: speed <kmh>")
                        continue
                    try:
                        spd = float(parts[1])
                        self.can.mock_set_speed(max(0, spd))
                        print(f"  Speed -> {spd:.0f} km/h")
                    except ValueError:
                        print(f"  Invalid speed '{parts[1]}'")
                elif verb == "brake":
                    if len(parts) >= 2 and parts[1] == "hard":
                        self.can.mock_set_brake(True, pressure=150)
                        print("  HARD BRAKE!")
                    else:
                        new_brake = not self.can.state.brake_pressed
                        self.can.mock_set_brake(new_brake)
                        print(f"  Brake {'PRESSED' if new_brake else 'released'}")
                elif verb == "door":
                    new_door = not self.can.state.door_fl_open
                    self.can.mock_set_doors(fl=new_door)
                    print(f"  Door {'OPEN' if new_door else 'CLOSED'}")
                elif verb == "talk":
                    response = self.brain.force_response(self.can.state)
                    self.voice.speak(response)
                elif verb == "shush":
                    self.brain.idle_chatter = not self.brain.idle_chatter
                    status = "ON" if self.brain.idle_chatter else "OFF"
                    print(f"  Idle chatter {status}")
                elif verb == "state":
                    print_state(self.can.state)
                else:
                    # Free-form chat
                    response = self.brain.chat(cmd, self.can.state)
                    self.voice.speak(response)

        finally:
            self.running = False
            _main.running = False
            print("\nStopping...")
            self.voice.speak("See you next time!", blocking=True)
            self.brain.end_session()
            self.can.stop()
            print("Goodbye!")
