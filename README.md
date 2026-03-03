# 🐣 ピーちゃん (Pii-chan)

An AI car companion that lives in your vehicle, understands your driving, and provides natural Japanese commentary.

> *"後ろ、気をつけてね〜"* — Pii-chan, when you shift into reverse

## What is this?

Pii-chan is an AI spirit that lives in your car. She reads CAN bus data to understand what's happening — speed, gear, doors, engine state — and comments naturally in Japanese. She's not a soundboard with canned responses; she actually thinks about the context and decides when and what to say.

**Target vehicle:** 2025 Toyota Sienna (but adaptable to other CAN-equipped cars)

## Features

- 🚗 **Real-time CAN monitoring** — Speed, RPM, gear, doors, hybrid battery, and more
- 🧠 **LLM-powered responses** — Natural, context-aware Japanese speech (not scripted)
- 💾 **Session memory** — Remembers past drives and references them naturally
- 🔊 **Japanese TTS** — VOICEVOX for cute, natural Japanese voice
- 😊 **Personality** — Kind, helpful, slightly clumsy AI spirit who loves her "home"

## Quick Start

### 1. Clone and Setup

```bash
git clone git@github.com:idorurez/pii-chan.git
cd pii-chan
./setup.sh
source venv/bin/activate
```

### 2. Test Without Model (Rule-Based Mode)

```bash
# Text-based testing (no pygame required)
python -m src.main --simulate --no-model
```

Commands in text mode:
- `engine` — Toggle engine on/off
- `gear p/r/n/d` — Change gear
- `speed 50` — Set speed
- `door` — Toggle door
- `talk` — Force Pii-chan to speak
- `state` — Show current car state
- `quit` — Exit

### 3. Run the Visual Simulator

```bash
# Requires pygame
pip install pygame
python -m src.main --simulator
```

Simulator controls:
- `SPACE` — Engine on/off
- `P/R/N/D` — Gear selection
- `↑/↓` — Accelerate/brake
- `O` — Open/close door
- `F` — Force Pii-chan to speak
- `ESC` — Quit

### 4. Add LLM for Natural Responses

```bash
# Download Qwen 2.5 1.5B (~1GB)
mkdir -p models
wget -O models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"

# Run with LLM
python -m src.main --simulate
```

See [docs/MODEL_SETUP.md](docs/MODEL_SETUP.md) for more model options.

### 5. Add Voice Output

Install and run [VOICEVOX](https://voicevox.hiroshiba.jp/), then update `config.yaml`:

```yaml
voice:
  engine: voicevox
  speaker_id: 3  # ずんだもん
```

See [docs/VOICEVOX_SETUP.md](docs/VOICEVOX_SETUP.md) for setup guide.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                      Pii-chan                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  CAN Bus    │  │  History    │  │ Personality │ │
│  │  (live)     │  │  (SQLite)   │  │  (prompt)   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         └────────────────┼────────────────┘        │
│                          ▼                         │
│              ┌───────────────────┐                 │
│              │   Context Builder │                 │
│              └─────────┬─────────┘                 │
│                        ▼                           │
│              ┌───────────────────┐                 │
│              │   LLM (Qwen 1.5B) │                 │
│              │  "What should I   │                 │
│              │   say right now?" │                 │
│              └─────────┬─────────┘                 │
│                        ▼                           │
│         ┌──────────────┴──────────────┐            │
│         ▼                             ▼            │
│  ┌─────────────┐               ┌─────────────┐    │
│  │  VOICEVOX   │               │   Display   │    │
│  │  (speech)   │               │   (face)    │    │
│  └─────────────┘               └─────────────┘    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Key insight:** Pii-chan doesn't have scripted responses. Every few seconds, she looks at:
- Current car state (speed, gear, engine, etc.)
- Recent events (what just happened)
- Session history (past drives)
- Her personality definition

And asks the LLM: *"Given all this context, should I say something? If so, what?"*

## Project Structure

```
pii-chan/
├── src/
│   ├── main.py          # Entry point
│   ├── simulator.py     # Interactive driving simulator
│   ├── brain.py         # LLM integration + context building
│   ├── can_reader.py    # CAN bus interface (real + mock)
│   ├── voice.py         # VOICEVOX TTS wrapper
│   ├── memory.py        # Session history (SQLite)
│   └── config.py        # Configuration management
├── data/
│   ├── toyota_sienna.dbc    # CAN message definitions
│   ├── personality.md       # Pii-chan's personality prompt
│   └── sessions.db          # History database (auto-created)
├── docs/
│   ├── MODEL_SETUP.md       # LLM installation guide
│   └── VOICEVOX_SETUP.md    # Voice setup guide
├── tests/
│   └── test_brain.py
├── config.example.yaml
├── requirements.txt
├── setup.sh
└── README.md
```

## Configuration

Copy `config.example.yaml` to `config.yaml`:

```yaml
llm:
  model_path: ./models/qwen2.5-1.5b-instruct-q4_k_m.gguf
  context_size: 4096
  temperature: 0.8

voice:
  engine: mock          # or 'voicevox'
  speaker_id: 3         # VOICEVOX character
  speed: 1.1

can:
  interface: mock       # or 'socketcan' for real hardware
  dbc_path: ./data/toyota_sienna.dbc

brain:
  think_interval: 3.0   # Seconds between "should I speak?" checks
  speech_cooldown: 30.0 # Minimum seconds between speeches
```

## Hardware (For Car Deployment)

| Component | Purpose | Price |
|-----------|---------|-------|
| Raspberry Pi 5 8GB | Compute | ~$80 |
| Waveshare 2-CH CAN HAT | CAN bus interface | ~$25 |
| HyperPixel 4.0 | Display (4" IPS) | ~$55 |
| MAX98357A + Speaker | Audio output | ~$11 |
| 12V→5V Converter | Power | ~$10 |
| **Total** | | **~$180** |

## CAN Bus Notes

The 2025 Sienna uses Toyota's Security Key (TSK/SecOC) which signs safety-critical CAN messages. However:

- ✅ **Reading is fine** — Messages are signed, not encrypted
- ✅ **We only read** — Pii-chan doesn't send commands
- ⚠️ **OBD-II is filtered** — May need direct CAN tap for full data

## Personality

Pii-chan's personality is defined in `data/personality.md`. She's:

- 優しくて思いやりがある (Kind and caring)
- ちょっとおっちょこちょい (A bit clumsy)
- ドライバーのことが大好き (Loves the driver)
- 車を「私のおうち」と思っている (Thinks of the car as "my home")

Feel free to customize her personality!

## Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## Roadmap

- [x] Desktop prototype with mock CAN
- [x] LLM integration
- [x] VOICEVOX TTS
- [x] Session memory
- [ ] Face/expression display
- [ ] Real CAN bus testing
- [ ] Raspberry Pi deployment
- [ ] Car installation guide

## Contributing

PRs welcome! This is a fun hobby project. Ideas:

- More personality variations
- Face animations
- Multi-language support
- Integration with car cameras
- Trip summarization

## License

MIT — Do what you want, but please share cool improvements! 🐣
