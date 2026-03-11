# Pii-chan Product Specification

## Vision

Pii-chan is your AI copilot in the car — an OpenClaw node with a face, voice, and awareness of your vehicle. Not a novelty chatbot, but your actual assistant that happens to live in your car.

## Core Value Proposition

**"OpenClaw, but in your car, with car superpowers."**

Everything you can do with OpenClaw (calendar, messages, reminders, web search, memory) plus:
- Awareness of vehicle state (speed, battery, doors, climate)
- Ability to control vehicle systems (climate, eventually more)
- A persistent presence with personality
- Hands-free interaction while driving

---

## Strategic Positioning

### Why Not a Phone App?

A phone app would compete with Android Auto / CarPlay — a losing battle:

| AA/CarPlay | Pii-chan |
|------------|----------|
| Navigation (Google/Apple Maps) | ❌ Don't compete |
| Music (Spotify, etc.) | ❌ Don't compete |
| CAN bus access | ❌ Impossible for phones | ✅ Unique |
| Climate control | ❌ Impossible for phones | ✅ Unique |
| Custom AI personality | ❌ Generic assistants | ✅ Unique |
| Your data/context | ❌ Limited | ✅ Full OpenClaw |
| Car state awareness | ❌ None | ✅ Unique |

**Users are deeply habituated to AA/CarPlay.** Asking them to switch = DOA.

### Coexistence, Not Competition

```
Head Unit: AA/CarPlay
├── Navigation
├── Music  
├── Messages
└── What Google/Apple do best

Pii-chan (Pi + Display): Your AI copilot
├── CAN bus control
├── Vehicle awareness
├── AI personality
└── What they CAN'T do
```

**Pii-chan doesn't fight for the head unit. It creates a new category.**

Like a dashcam or radar detector — it does its own thing, complements the existing setup.

### The Moat

Pii-chan's defensible advantages:
1. **CAN bus access** — Phones literally cannot do this
2. **Write capability** — Control climate, not just read data
3. **Persistent presence** — Dedicated display, always there
4. **Full OpenClaw** — Your AI, your memory, your integrations
5. **Tunable personality** — Not a generic assistant

---

## MVP Scope

### Must Have (Day One)

**1. OpenClaw Node**
- Connects to existing OpenClaw gateway
- Full access to all OpenClaw capabilities
- Works via WiFi hotspot or Bluetooth PAN

**2. Greeting & Presence**
- Greets you when you enter the car
- Visual presence on dedicated display
- Can be toggled visible/hidden based on mood

**3. Voice Interaction**
- Wake word activation ("Hey Pii-chan" or configurable)
- Natural conversation via Claude
- Variable voice (can tune TTS voice/style)
- Can be muted when desired

**4. Personality**
- Tunable personality via prompt/config
- Consistent character across sessions
- Remembers conversation context

**5. Car Data Awareness (Read Only)**
- Reads vehicle state via CAN bus
- Knows: engine status, speed, gear, battery, doors
- Can reference car state in conversation
- "How's my battery?" → actual answer

**6. State Memory**
- Remembers actions it has taken
- Supports "undo" / "nevermind" / "change that back"
- Doesn't forget what it just did

### Cut from MVP

- **Multi-user**: Same personality for everyone (for now)
- **CAN Write / Climate Control**: Architecture supports it, but requires sniffing first
- **Always-listening**: Start with wake word only
- **4G connectivity**: Start with hotspot, upgrade path available

---

## User Experience

### Daily Flow

1. **Get in car** → Pi auto-boots from 12V power
2. **Phone connects** → AA/CarPlay to head unit (separate)
3. **Pii-chan wakes** → Connects via phone WiFi hotspot
4. **Greeting** → "Good morning! You've got two meetings today and traffic looks light."
5. **Drive** → Pii-chan visible on dedicated screen, responds to wake word
6. **Interaction** → "Hey Pii-chan, remind me to call mom when I get home"
7. **Arrive** → "See you later!"

### Interaction Modes

| Mode | Display | Voice | Wake Word |
|------|---------|-------|-----------|
| **Active** | Visible, animated | On | Listening |
| **Quiet** | Visible, calm | Muted | Listening |
| **Hidden** | Off | Muted | Listening |
| **Sleep** | Off | Off | Off |

User can switch modes via voice: "Pii-chan, go quiet" / "Pii-chan, hide" / "Pii-chan, wake up"

### Personality Tuning

Personality defined in config file (`personality.md` or YAML):

```yaml
personality:
  name: "Pii-chan"
  style: "helpful, slightly playful, concise"
  voice: "warm, feminine"  # or masculine, neutral, robotic, etc.
  greeting_style: "casual"
  verbosity: "low"  # low, medium, high
  japanese_mode: false  # toggle for Japanese responses/voice
```

Users can adjust via conversation: "Pii-chan, be more formal" → updates config

---

## Architecture

### Hardware (MVP)

| Component | Purpose | Required |
|-----------|---------|----------|
| Raspberry Pi 5 8GB | Compute | ✓ |
| Waveshare 2-CH CAN HAT | CAN bus read | ✓ |
| HyperPixel 4.0 (or similar) | Display | ✓ |
| USB Microphone | Voice input | ✓ |
| MAX98357A + Speaker | Voice output | ✓ |
| 12V→5V 5A Converter | Power | ✓ |
| Waveshare SIM7600 4G HAT | Dedicated 4G | Optional (upgrade) |

**Estimated cost:** ~$200 (without 4G) / ~$270 (with 4G)

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Car (Pi 5)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Pii-chan Node                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │ │
│  │  │ Wake Word    │  │ Voice I/O    │  │ Display      │  │ │
│  │  │(OpenWakeWord)│  │(Vosk+Piper)  │  │ (Face)       │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │ │
│  │                         │                               │ │
│  │              ┌──────────┴──────────┐                   │ │
│  │              │  Connection Manager  │                   │ │
│  │              └──────────┬──────────┘                   │ │
│  │         ┌───────────────┴───────────────┐              │ │
│  │         ▼                               ▼              │ │
│  │  ┌─────────────┐                 ┌─────────────┐       │ │
│  │  │ AWS Gateway │ ◄── Primary     │ Local LLM   │       │ │
│  │  │ (Claude)    │                 │ (Fallback)  │       │ │
│  │  └─────────────┘                 └─────────────┘       │ │
│  │                                                        │ │
│  │              ┌──────────────────┐                      │ │
│  │              │   CAN Interface  │                      │ │
│  │              └──────────────────┘                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                       WiFi / 4G
                              │
                              ▼
                 ┌───────────────────────┐
                 │   AWS Gateway         │
                 │   (OpenClaw)          │
                 │   - Claude API        │
                 │   - Memory            │
                 │   - All integrations  │
                 └───────────────────────┘
```

### Voice Stack (No Cloud Dependencies)

All voice processing runs locally on the Pi — no API keys required:

| Component | Solution | License | Notes |
|-----------|----------|---------|-------|
| Wake Word | OpenWakeWord | Apache 2.0 | Truly offline, no key |
| Speech-to-Text | Vosk | Apache 2.0 | Offline, good accuracy |
| Text-to-Speech | Piper | MIT | Fast, multiple voices |

**Why not Porcupine/Picovoice?** Requires internet to validate AccessKey, even though processing is local. Unacceptable for a car product.

### Connection States

| State | Indicator | Behavior |
|-------|-----------|----------|
| **Connected** | 🟢 Green | Full Claude via AWS gateway |
| **Degraded** | 🟡 Yellow | Local LLM, limited capability |
| **Reconnecting** | 🟡 Blinking | Trying to restore connection |

**User notifications:**
- Visual: Status indicator on display (always visible)
- Voice: "I've lost connection, running in limited mode" / "Back online!"

### Local Fallback Model

When AWS gateway is unreachable, Pi runs a local LLM:

| Model | Size | Speed on Pi 5 | Recommendation |
|-------|------|---------------|----------------|
| Qwen 2.5 1.5B Q4 | ~1GB | ~10 tok/s | ✓ Good balance |
| Phi-3 Mini Q4 | ~2GB | ~8 tok/s | ✓ Better quality |
| Llama 3.2 3B Q4 | ~2GB | ~6 tok/s | Slower but capable |

**Fallback limitations:**
- ❌ No calendar, messages, reminders (no OpenClaw access)
- ❌ No memory/context from other sessions
- ✅ Basic conversation works
- ✅ CAN commands work (read car state, control climate)

**Graceful degradation example:**
```
User: "What's on my calendar today?"

Connected:
"You have a dentist appointment at 2pm and a team call at 4."

Disconnected:
"I'm offline right now and can't access your calendar. 
I can still help with car controls — want me to adjust the climate?"
```

### Connection Manager Responsibilities

1. Monitor WebSocket to AWS gateway
2. Detect disconnection (timeout, network error)
3. Switch to local LLM automatically
4. Notify user of state change
5. Keep retrying connection in background
6. Switch back when connection restored
7. Sync any offline actions when reconnected

### Pi 5 Resource Budget (8GB)

| Component | RAM | CPU | When Active |
|-----------|-----|-----|-------------|
| OS + services | ~500MB | Low | Always |
| Wake word (OpenWakeWord) | ~50MB | Low | Always |
| Display UI | ~100MB | Low | Always |
| CAN reader | ~20MB | Minimal | Always |
| STT (Vosk) | ~200MB | Medium | On wake |
| TTS (Piper) | ~100MB | Medium | On response |
| Local LLM (fallback) | ~2GB | High | When offline |
| **Total (connected)** | ~1GB | - | Normal |
| **Total (offline)** | ~3GB | - | Fallback mode |
| **Headroom** | ~5GB | - | ✓ Comfortable |

### Connectivity Priority

1. WiFi (phone hotspot or known networks)
2. Bluetooth PAN (if WiFi unavailable)
3. 4G HAT (if installed and others unavailable)

### CAN Integration

**MVP (Read Only):**
- Engine state, RPM
- Vehicle speed
- Gear position
- Battery SOC
- Door status
- Fuel level

**Future (Write - requires sniffing):**
- Climate control (temp, fan, mode, zones)
- Possibly: seat heaters, lights, locks

---

## Connectivity Strategy

### MVP: Phone WiFi Hotspot

**Flow:**
1. User enables WiFi hotspot on phone
2. Pi auto-connects to known hotspot SSID
3. OpenClaw node connects to gateway

**Friction:** Manual hotspot toggle each drive

**Mitigation:**
- Test Bluetooth PAN (might auto-connect)
- iOS Shortcut: "When CarPlay connects → enable hotspot"
- Android: Bluetooth auto-hotspot if supported by device

### Future: Dedicated 4G

**When to upgrade:**
- Tired of hotspot toggle
- Want Pii-chan to work without phone
- ~$10-15/mo acceptable

**Hardware:** Waveshare SIM7600 or Sixfab 4G HAT

---

## Phase 2 (Post-MVP)

### Climate Control
- Sniff Sienna/4Runner HVAC CAN messages
- Implement climate_set commands
- "Pii-chan, set rear to feet only"
- "I'm cold" → raises temp intelligently

### Always-Listening Mode
- Continuous speech detection
- Lower latency responses
- Optional (some prefer wake word)

### Multi-User
- Recognize who's driving (voice? phone presence?)
- Different personalities/preferences per user
- Kid-friendly mode

### Visual Enhancements
- Animated face/expressions
- Mood based on context (sleepy on highway, alert in traffic)
- Weather/time awareness in display

### Smart Integrations
- "Almost home" → prep house (lights, thermostat)
- Trip summaries in memory
- Proactive alerts based on calendar + traffic

---

## Success Metrics

### MVP Success
- [ ] Boots reliably when car starts
- [ ] Connects to gateway within 30 seconds
- [ ] Voice interaction works while driving (noise handling)
- [ ] Correctly reads and reports car state
- [ ] Personality feels consistent and tunable
- [ ] Daily driver for 2 weeks without wanting to turn it off

### Phase 2 Success
- [ ] Climate control works via voice
- [ ] Family doesn't find it annoying
- [ ] Used for more than car stuff (calendar, reminders, etc.)

---

## Decisions Made

| Question | Decision | Rationale |
|----------|----------|-----------|
| Wake word | **OpenWakeWord** | Truly offline, no API key, Apache 2.0 |
| STT | **Vosk** | Offline, good accuracy, no key |
| TTS | **Piper** | Fast, local, MIT license |
| Gateway location | **AWS instance** | Already exists, Claude API access |
| Fallback | **Local LLM (Qwen/Phi)** | Works offline for car controls |

## Open Questions

1. **Display framework:** Web-based (Electron)? Native (Qt)? Simple pygame?
2. **Face design:** Anime style? Abstract? Minimal?
3. **Local fallback model:** Qwen 2.5 1.5B or Phi-3 Mini?

---

## Build Phases

### Phase 1: Pi Validation (CRITICAL PATH)
**Goal:** Prove Pi 5 + OpenClaw node + voice stack works

This is the gating phase. Everything hinges on this working.

**What to validate:**
1. OpenClaw node connects to AWS gateway
2. OpenWakeWord detects wake word reliably
3. Vosk STT transcribes accurately  
4. Piper TTS generates audio smoothly
5. Full loop latency < 5 seconds
6. Local LLM fallback works (< 10 seconds)
7. Display renders UI

**Hardware needed:** Full kit (see Shopping List below)

**Success criteria:**
- [ ] `openclaw node run` connects to AWS gateway
- [ ] "Hey Pii-chan" wakes reliably
- [ ] Voice → Response → Audio in < 5 seconds
- [ ] Fallback mode works when disconnected
- [ ] Display shows Pii-chan face/status

**Go/No-Go:** If this fails, debug before proceeding.

---

### Phase 2: CAN Integration (Read)
**Goal:** Pii-chan knows what the car is doing

**What to build:**
- CAN HAT reading real Toyota CAN data
- Parse known message IDs (speed, battery, gear, doors)
- Expose car state to conversation context
- "How's my battery?" → real answer

**Success:** Pii-chan accurately reports vehicle state

---

### Phase 3: Personality & Polish
**Goal:** Feels like a product, not a prototype

**What to build:**
- Tunable personality system
- Face UI with expressions
- Mode switching (active/quiet/hidden)
- Context-aware greeting
- State memory (undo support)

**Success:** Daily driver for 2 weeks without annoyance

---

### Phase 4: CAN Sniffing (HVAC)
**Goal:** Decode climate control messages

**What to build:**
- Sniffing tooling (capture, diff, analyze)
- Document discovered message IDs
- Test write capability on body CAN

**Success:** Know the CAN IDs for climate control

---

### Phase 5: Climate Control
**Goal:** Voice-controlled HVAC

**What to build:**
- climate_set / climate_off commands
- Natural language → CAN writes
- "I'm cold" → intelligent adjustment

**Success:** "Set rear to feet only" actually works

---

## Phase Dependencies

```
Phase 1 (Pi Validation) ◄── CRITICAL PATH
         │
         ├──────────────────┐
         ▼                  ▼
Phase 2 (CAN Read)    Phase 3 (Polish)
         │                  │
         └────────┬─────────┘
                  │
                  ▼
            MVP COMPLETE
                  │
                  ▼
         Phase 4 (Sniffing)
                  │
                  ▼
         Phase 5 (Climate)
```

**Phase 1 is go/no-go.** Phases 2 & 3 can run parallel after.

---

## Shopping List

### Phase 1 Hardware (Order Tonight)

| Item | Purpose | Link/Notes | Price |
|------|---------|------------|-------|
| **Raspberry Pi 5 8GB** | Compute | Official or Adafruit | ~$80 |
| **Pi 5 27W USB-C Power Supply** | Dev power | Official recommended | ~$12 |
| **SD Card 128GB A2** | Storage (fast) | Samsung EVO or SanDisk Extreme | ~$15 |
| **Pi 5 Active Cooler** | Thermal | Official or Argon | ~$8 |
| **Waveshare 7" Touchscreen** | Display + config + face | 1024x600, HDMI+USB touch | ~$55 |
| **USB Microphone** | Voice input | ReSpeaker or similar | ~$20 |
| **USB Speaker** | Voice output | Any small USB/3.5mm | ~$15 |
| **Waveshare 2-CH CAN HAT** | CAN bus | SPI, MCP2515 | ~$25 |
| **WiCAN OBD-II** | CAN sniffing/injection | WiFi, supports Toyota | ~$55 |
| **Subtotal** | | | **~$285** |

### Car Installation (Phase 2+)

| Item | Purpose | Price |
|------|---------|-------|
| **12V→5V 5A Buck Converter** | Car power | ~$12 |
| **OBD-II Splitter** | Connect WiCAN + keep OBD | ~$10 |
| **Display Mount** | Dashboard mounting | ~$15 |
| **Cable management** | Clean install | ~$10 |
| **Subtotal** | | **~$47** |

### Optional Upgrades (Later)

| Item | Purpose | Price |
|------|---------|-------|
| Waveshare SIM7600 4G HAT | Dedicated cellular | ~$70 |
| T-Mobile prepaid SIM | Data plan | ~$10/mo |
| HyperPixel 4.0 | Smaller display option | ~$55 |

---

### Recommended Vendors

- **Pi 5 + accessories:** [Adafruit](https://adafruit.com), [PiShop.us](https://pishop.us), [CanaKit](https://canakit.com)
- **Waveshare displays/HATs:** [Waveshare](https://waveshare.com), [Amazon](https://amazon.com)
- **WiCAN:** [MeatPi](https://meatpi.com/products/wican) or Amazon

---

### Shopping Links (Amazon)

For quick purchase tonight:

1. **Pi 5 8GB Kit** - Search "Raspberry Pi 5 8GB starter kit" (~$100 with case/power/SD)
2. **Waveshare 7" 1024x600** - ASIN: varies, ~$55
3. **Waveshare 2-CH CAN HAT** - ASIN: B07VMB1ZKH or similar, ~$25
4. **WiCAN Pro** - [meatpi.com](https://meatpi.com) or Amazon ~$55
5. **USB Mic** - ReSpeaker USB Mic Array or any decent USB mic ~$20
6. **USB Speaker** - Any small USB-powered speaker ~$15

---

## Latency Budget (Reference)

| Stage | Target | Notes |
|-------|--------|-------|
| Wake word detection | < 100ms | OpenWakeWord |
| STT (Vosk) | < 1000ms | Depends on phrase length |
| Network to AWS | < 300ms | Hotspot/LTE |
| Claude API | < 3000ms | Variable |
| TTS (Piper) | < 500ms | Medium quality voice |
| **Total (connected)** | **< 5 sec** | Acceptable |
| **Total (fallback)** | **< 10 sec** | Local LLM slower |

---

*Last updated: 2026-03-10*
