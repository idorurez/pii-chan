# 🐣 ピーちゃん (Pii-chan)

**Your AI copilot in the car — not a toy, an actual assistant.**

Pii-chan is an OpenClaw node that lives in your vehicle. Full Claude intelligence, voice control, CAN bus integration. It's not a novelty chatbot with canned responses — it's your actual AI assistant, just in your car.

> "Set rear climate to feet only" → *does it*  
> "What's my first meeting today?" → *checks calendar*  
> "Read my unread messages" → *reads them aloud*  
> "Remind me to get gas on the way home" → *sets reminder*

**Target vehicle:** 2025 Toyota Sienna (adaptable to others)

## Why This Exists

Most "car AI" projects are demos. Talk to a local LLM, get dumb responses, novelty wears off in a week.

Pii-chan is different:
- **Full Claude access** via OpenClaw — not a 1.5B model pretending to understand
- **All OpenClaw capabilities** — calendar, messages, reminders, web search, memory
- **CAN bus as a skill** — climate control is a bonus feature, not the whole product
- **Actually useful daily** — you'd miss it if it was gone

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Your Car                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Raspberry Pi 5 (OpenClaw Node)           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │  │
│  │  │ Voice In    │  │ Voice Out   │  │ CAN Interface │  │  │
│  │  │ (Whisper)   │  │ (TTS)       │  │ (Read/Write)  │  │  │
│  │  └──────┬──────┘  └──────▲──────┘  └───────┬───────┘  │  │
│  │         │                │                  │          │  │
│  │         └────────────────┼──────────────────┘          │  │
│  │                          │                              │  │
│  │              ┌───────────┴───────────┐                 │  │
│  │              │   OpenClaw Gateway    │                 │  │
│  │              │   (local daemon)      │                 │  │
│  │              └───────────┬───────────┘                 │  │
│  └──────────────────────────┼────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────┘
                              │ Phone tether / Car WiFi
                              ▼
                    ┌───────────────────┐
                    │   Claude (API)    │
                    │   Full LLM power  │
                    └───────────────────┘
```

**Key insight:** The Pi is just the interface layer. All the smarts come from Claude via OpenClaw. CAN bus reading/writing is exposed as tools that Claude can use.

## What Pii-chan Can Do

### 🚗 Car Stuff (CAN Bus)
- Read vehicle state (speed, gear, doors, battery, etc.)
- Voice-controlled climate ("I'm cold" → adjusts HVAC)
- Event awareness (engine start, hard brake, fuel low)
- Trip context for relevant suggestions

### 📅 Assistant Stuff (OpenClaw)
- Calendar queries and reminders
- Read/send messages
- Weather and traffic
- Web search
- Todo lists
- Anything OpenClaw can do

### 🎤 Voice Control
- Wake word or push-to-talk
- Natural conversation while driving
- Hands-free everything

## Quick Start (Development)

### 1. Clone and Setup

```bash
git clone git@github.com:idorurez/pii-chan.git
cd pii-chan
./setup.sh
source venv/bin/activate
```

### 2. Run in Simulation Mode

```bash
# Text-based testing
python -m src.main --simulate

# Visual simulator (requires pygame)
python -m src.main --simulator
```

### 3. Connect to OpenClaw

(Coming soon — node registration flow)

## Hardware (~$200)

| Component | Purpose | Price |
|-----------|---------|-------|
| Raspberry Pi 5 8GB | Compute | ~$80 |
| Waveshare 2-CH CAN HAT | CAN bus interface | ~$25 |
| HyperPixel 4.0 | Display (optional) | ~$55 |
| MAX98357A + Speaker | Audio output | ~$11 |
| USB Mic | Voice input | ~$15 |
| 12V→5V Converter | Power | ~$10 |
| **Total** | | **~$200** |

Plus CAN adapter for sniffing: WiCAN OBD ~$50

## Project Structure

```
pii-chan/
├── src/
│   ├── main.py              # Entry point
│   ├── node.py              # OpenClaw node integration
│   ├── can_interface.py     # CAN read/write (exposed as tools)
│   ├── voice_io.py          # STT + TTS
│   └── config.py            # Configuration
├── skills/
│   └── can-control/         # CAN bus skill for OpenClaw
│       ├── SKILL.md
│       ├── can_reader.py
│       └── can_writer.py
├── data/
│   ├── toyota_sienna.dbc    # CAN message definitions
│   └── personality.md       # Pii-chan's voice/style
├── docs/
│   ├── CAN_SNIFFING_GUIDE.md
│   ├── NODE_SETUP.md
│   └── HARDWARE.md
└── config.yaml
```

## CAN Bus Integration

CAN reading/writing is exposed as OpenClaw tools:

```yaml
# Tools available to Claude when Pii-chan node is active
can_read:
  description: Read current vehicle state
  returns: speed, gear, doors, battery, climate, etc.

can_climate:
  description: Control HVAC
  params: zone, temp, fan, mode, sync
```

### Climate Control Status

The 2025 Sienna uses Toyota SecOC for safety messages, but HVAC is on the body CAN (likely unprotected). We need to:

1. ✅ Get CAN hardware (WiCAN OBD recommended)
2. ⏳ Sniff HVAC messages while using controls
3. ⏳ Decode message IDs and values
4. ⏳ Implement write commands

See [docs/CAN_SNIFFING_GUIDE.md](docs/CAN_SNIFFING_GUIDE.md) for the procedure.

## Roadmap

### Phase 1: Foundation ✅
- [x] CAN bus reading prototype
- [x] Voice output (TTS)
- [x] Simulator for testing
- [x] Basic event reactions

### Phase 2: OpenClaw Integration 🔄
- [ ] Pi as OpenClaw node
- [ ] CAN exposed as tools
- [ ] Voice input (STT)
- [ ] Full Claude access

### Phase 3: Climate Control
- [ ] Decode Sienna HVAC CAN messages
- [ ] Implement climate commands
- [ ] Natural language → CAN writes

### Phase 4: Polish
- [ ] Wake word detection
- [ ] Display UI (optional)
- [ ] Car installation guide
- [ ] Multi-vehicle support

## Philosophy

**Useful, not cute.** Pii-chan only speaks when it adds value. No constant chatter. No "Did you know?" trivia. Just an assistant that happens to live in your car.

**OpenClaw first, car second.** The CAN stuff is a capability enhancement. Even without climate control, Pii-chan is useful because it's a full AI assistant with voice I/O.

**Local processing where it matters.** Voice capture and TTS run locally for low latency. The thinking happens in Claude for quality.

## License

MIT

---

*Pii-chan: Your car, smarter.*
