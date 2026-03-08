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
| [docs/GATEWAY_SETUP.md](docs/GATEWAY_SETUP.md) | Agent setup on your OpenClaw gateway |
| [docs/DEPLOYMENT_PLAN.md](docs/DEPLOYMENT_PLAN.md) | Technical deployment details |
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

| Component | Purpose |
|-----------|---------|
| Raspberry Pi 5 8GB | Compute |
| Waveshare 2-CH CAN HAT | CAN bus |
| HyperPixel 4.0 | Display |
| USB Microphone | Voice input |
| MAX98357A + Speaker | Voice output |
| 12V→5V 5A Converter | Power |

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
├── src/                    # Source code
│   ├── node.py             # OpenClaw node integration
│   ├── main.py             # Entry point
│   ├── can_reader.py       # CAN bus reading
│   └── voice.py            # TTS
├── skills/
│   └── car-control/        # OpenClaw skill for car commands
├── workspace-template/     # Pii-chan agent workspace files
│   ├── SOUL.md             # Personality definition
│   ├── IDENTITY.md         # Name, emoji, vibe
│   ├── AGENTS.md           # Operating instructions
│   ├── USER.md             # Driver profile template
│   ├── MEMORY.md           # Long-term memory
│   └── HEARTBEAT.md        # Periodic check config
├── data/
│   ├── personality.md      # Personality reference (legacy)
│   └── toyota_sienna.dbc   # CAN message definitions
└── docs/
    ├── GATEWAY_SETUP.md    # Agent + node deployment
    ├── DEPLOYMENT_PLAN.md  # Technical details
    └── CAN_SNIFFING_GUIDE.md
```

## Status

🔄 **Planning complete, entering build phase**

- [x] Product spec defined
- [x] Architecture designed
- [x] Skill structure created
- [ ] Hardware acquired
- [ ] OpenClaw node running on Pi
- [ ] Voice I/O working
- [ ] Display + face
- [ ] CAN reading integrated
- [ ] Daily driver testing

## Quick Links

- [Product Spec](PRODUCT.md) — Full MVP definition
- [Deployment Plan](docs/DEPLOYMENT_PLAN.md) — How it all connects
- [CAN Sniffing Guide](docs/CAN_SNIFFING_GUIDE.md) — For climate control later

## License

MIT

---

*Pii-chan: OpenClaw in your car.*
