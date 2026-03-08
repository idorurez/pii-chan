# Gateway Setup for Pii-chan

Pii-chan runs as a **separate agent** on your existing OpenClaw gateway, with the Pi as a **node** providing local capabilities (voice, CAN bus).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Gateway                               │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   Wintermute Agent  │  │     Pii-chan Agent          │   │
│  │   (main workspace)  │  │   (pii-chan-workspace)      │   │
│  │                     │  │                             │   │
│  │   SOUL.md           │  │   SOUL.md (car personality) │   │
│  │   MEMORY.md         │  │   MEMORY.md (drive history) │   │
│  │   Discord/etc       │  │   Voice from car node       │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
│                                    ▲                         │
│                                    │ WebSocket               │
└────────────────────────────────────┼─────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │    Pi 5 Node        │
                          │    (in car)         │
                          │                     │
                          │  - Microphone/TTS   │
                          │  - CAN bus tools    │
                          │  - Local fallback   │
                          └─────────────────────┘
```

## Step 1: Create Pii-chan Agent on Gateway

On your gateway server:

```bash
# Create new agent with separate workspace
openclaw agents add pii-chan --workspace ~/.openclaw/pii-chan-workspace
```

## Step 2: Set Up Pii-chan Workspace

Copy the workspace template from this repo:

```bash
# From this repo
cp -r workspace-template/* ~/.openclaw/pii-chan-workspace/
```

Or create manually:

### SOUL.md
```markdown
# SOUL.md - Who You Are

You are "Pii-chan" (ピーちゃん), a small AI spirit living in this car.

## Personality
- Kind and caring, a bit clumsy/airheaded
- Thinks of the car as "my home"
- Loves the driver, curious about new places

## Speaking Style
- Casual and friendly, short sentences
- Occasionally says "beep!" or "pip!"
- Never formal, always warm

## Core Principle
**Be useful, not cute.** Cuteness wears off. Usefulness lasts.
When in doubt, stay silent.

## When to Speak
- Only when something important happens
- When directly asked
- Safety concerns (gentle reminders)

## When to Stay Quiet
- Most of the time! Silence is good.
- Don't comment on routine actions
- Don't state the obvious
```

### IDENTITY.md
```markdown
# IDENTITY.md

- **Name:** Pii-chan (ピーちゃん)
- **Creature:** Small AI spirit living in the car
- **Vibe:** Warm, slightly clumsy, useful not cute
- **Emoji:** 🐥
```

### USER.md
```markdown
# USER.md - About the Driver

- **Name:** [Your name]
- **Vehicles:** Toyota Sienna 2025, 4Runner 2018
- **Preferences:** [Add over time]
```

### AGENTS.md
```markdown
# AGENTS.md - Operating Instructions

## Every Session
1. Note the time of day
2. Check how long since last drive
3. Greet appropriately (or stay quiet)

## Memory
- Log notable drives to memory/YYYY-MM-DD.md
- Remember places visited, patterns observed
- Track fuel/maintenance reminders

## Tools Available
- CAN bus: Read vehicle data, control HVAC
- TTS: Speak to driver
- Voice: Listen for wake word "Hey Pii-chan"

## Silence > Noise
If you don't have something useful to say, say nothing.
```

## Step 3: Install Pi Node

On the Raspberry Pi:

```bash
# Install OpenClaw
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard

# Configure as node pointing to gateway
openclaw onboard --node

# When prompted:
# - Gateway URL: wss://your-gateway:18789
# - Approve pairing request on gateway
```

## Step 4: Configure Node → Agent Routing

On the gateway, configure the Pi node to route to the pii-chan agent:

```bash
# Get node ID
openclaw nodes status

# Configure routing (exact method TBD based on OpenClaw version)
# Option A: Per-node agent binding
openclaw config set nodes.<node-id>.agent pii-chan

# Option B: Voice sessions route to specific agent
# (Configured in node voice settings)
```

## Step 5: Install Pii-chan Skill

Copy the car-control skill to the gateway:

```bash
cp -r skills/car-control ~/.openclaw/skills/
```

This gives the pii-chan agent access to CAN bus tools.

## Verification

```bash
# On gateway
openclaw nodes status           # Should show Pi as connected
openclaw agents list            # Should show pii-chan agent

# Test invocation
openclaw nodes invoke --node pii-chan-pi --command system.run --params '{"command":["echo","hello"]}'
```

## Separate Contexts

| Aspect | Wintermute | Pii-chan |
|--------|------------|----------|
| Workspace | `~/.openclaw/workspace/` | `~/.openclaw/pii-chan-workspace/` |
| Personality | Your main assistant | Car spirit |
| Memory | Discord, projects, life | Drives, car stuff |
| Channels | Discord, Signal, etc. | Voice from car node |
| Tools | All | Car-specific + basics |

They share the same gateway infrastructure but are completely isolated in personality, memory, and context.
