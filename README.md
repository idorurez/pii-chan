# 🐣 ピーちゃん (Pii-chan)

**Your AI copilot in the car — OpenClaw with a face and vehicle awareness.**

Pii-chan is an OpenClaw node that lives in your vehicle. Full Claude intelligence, voice control, tunable personality, and awareness of your car's state.

> "Good morning! Traffic looks light today. You've got a meeting at 10."

**Target vehicles:** Toyota Sienna 2025, 4Runner 2018 (adaptable to others)

## What Is This?

Not another car chatbot. Pii-chan is:

- **Your actual OpenClaw** — calendar, messages, reminders, web search, memory
- **Car-aware** — knows speed, battery, doors, climate state
- **Persistent presence** — dedicated display, greets you, has personality
- **Hands-free** — wake word activation, voice control

## Documentation

| Doc | Purpose |
|-----|---------|
| [PRODUCT.md](PRODUCT.md) | Full product spec, MVP scope, architecture |
| [docs/GATEWAY_SETUP.md](docs/GATEWAY_SETUP.md) | Agent + token setup on your OpenClaw gateway |
| [docs/PI_SETUP.md](docs/PI_SETUP.md) | Raspberry Pi node setup (Tailscale, systemd, voice) |
| [docs/COMMANDS.md](docs/COMMANDS.md) | All commands reference (gateway, Pi, CAN, voice) |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [docs/RECONNECTION.md](docs/RECONNECTION.md) | Resilience, auto-recovery, monitoring |
| [docs/CAN_SNIFFING_GUIDE.md](docs/CAN_SNIFFING_GUIDE.md) | Reverse engineering HVAC CAN |
| [workspace-template/](workspace-template/) | Ready-to-deploy Pii-chan personality files |

## MVP Scope

**In:**
- OpenClaw node (full Claude access)
- Voice I/O with wake word
- Dedicated display with toggleable visibility
- Tunable personality
- CAN read (vehicle state awareness)
- State memory (can undo commands)

**Out (for now):**
- CAN write / climate control (needs sniffing first)
- Multi-user
- Always-listening (wake word only for MVP)
- Dedicated 4G (hotspot first, upgrade later)

## Hardware (~$200)

| Component | Purpose | Status |
|-----------|---------|--------|
| Raspberry Pi 5 8GB | Compute | Working |
| USB PnP Sound Device | Microphone input | Working |
| USB PnP Audio Device | Speaker output | Working |
| Waveshare 2-CH CAN HAT | CAN bus | Pending |
| HyperPixel 4.0 | Display | Pending |
| 12V→5V 5A Converter | Power | Pending |

## Architecture

```
┌─────────────────────────────────────┐
│         Car (Pi 5)                  │
│  ┌───────────┐  ┌────────────────┐  │
│  │ Voice I/O │  │ Display (Face) │  │
│  └─────┬─────┘  └───────┬────────┘  │
│        └────────┬───────┘           │
│                 │                   │
│        ┌────────┴────────┐          │
│        │  OpenClaw Node  │          │
│        └────────┬────────┘          │
│                 │                   │
│        ┌────────┴────────┐          │
│        │   CAN Reader    │          │
│        └─────────────────┘          │
└─────────────────────────────────────┘
                  │
           WiFi (hotspot)
                  │
                  ▼
         ┌───────────────┐
         │ Your Gateway  │
         │ (Claude API)  │
         └───────────────┘
```

## Project Structure

```
pii-chan/
├── PRODUCT.md              # Product spec (start here)
├── README.md               # This file
├── config.example.yaml     # Example configuration
├── src/                    # Source code
│   ├── main.py             # Entry point (voice mode, text mode, simulator)
│   ├── brain.py            # AI brain (LLM + rule-based)
│   ├── voice.py            # TTS output (Piper + VOICEVOX, auto-detect)
│   ├── voice_input.py      # Wake word + STT input
│   ├── can_reader.py       # CAN bus reading
│   ├── config.py           # Configuration dataclasses
│   ├── memory.py           # Session memory (SQLite)
│   └── node.py             # OpenClaw node integration
├── models/                 # Downloaded models (not in git)
│   ├── vosk-model-small-en-us-0.15/
│   └── voicevox/           # VOICEVOX Core files
├── voices/                 # Piper TTS voice models
├── data/
│   ├── personality.md      # Personality definition
│   └── toyota_sienna.dbc   # CAN message definitions
├── docs/
│   ├── VOICE_INPUT.md      # Voice input setup + troubleshooting
│   ├── VOICEVOX_SETUP.md   # Japanese TTS setup
│   ├── MODEL_SETUP.md      # LLM model setup
│   ├── PI_SETUP.md         # Raspberry Pi setup
│   ├── GATEWAY_SETUP.md    # OpenClaw gateway setup
│   └── CAN_SNIFFING_GUIDE.md
└── workspace-template/     # Pii-chan agent workspace files
```

## Status

🔄 **Voice loop working! Next: VOICEVOX Core integration + display**

- [x] Product spec defined
- [x] Architecture designed
- [x] Skill structure created
- [x] OpenClaw gateway configured (Docker, Tailscale)
- [x] Raspberry Pi node connected to gateway
- [x] Systemd service with auto-reconnect
- [x] Comprehensive troubleshooting docs
- [x] Hardware: Pi 5 + USB soundcard (mic + speaker)
- [x] Wake word detection (OpenWakeWord, "hey Jarvis")
- [x] Speech-to-text (Vosk, offline)
- [x] English TTS (Piper, local)
- [x] Full voice loop: wake word → STT → brain → TTS
- [x] Auto-detect dual TTS engine (English → Piper, Japanese → VOICEVOX)
- [ ] Japanese TTS (VOICEVOX Core local synthesis — in progress)
- [ ] Display + face
- [ ] CAN reading with real hardware
- [ ] Daily driver testing

## Quick Links

- [Product Spec](PRODUCT.md) — Full MVP definition
- [Gateway Setup](docs/GATEWAY_SETUP.md) — Configure your OpenClaw gateway
- [Pi Setup](docs/PI_SETUP.md) — Get the node running
- [Commands Reference](docs/COMMANDS.md) — All commands in one place
- [Troubleshooting](docs/TROUBLESHOOTING.md) — When things go wrong
- [Reconnection](docs/RECONNECTION.md) — Auto-recovery behavior
- [CAN Sniffing](docs/CAN_SNIFFING_GUIDE.md) — For climate control later

## License

MIT

---

*Pii-chan: OpenClaw in your car.*
