# Pii-chan Deployment Plan

How to make Pii-chan a real OpenClaw node that you can just get in the car and use.

## 1. Architecture: Pi as OpenClaw Node

The Pi runs as a **headless OpenClaw node** that connects to your existing OpenClaw gateway.

```
┌──────────────────────────────────────────────────────────────┐
│  Your Car (Pi 5)                                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  openclaw node run --host <gateway> --port 18789       │  │
│  │                                                        │  │
│  │  Exposes:                                              │  │
│  │  - system.run (execute commands)                       │  │
│  │  - Custom CAN tools via command wrapper                │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│              ┌───────────┴───────────┐                       │
│              │  CAN Interface        │                       │
│              │  (Waveshare HAT)      │                       │
│              └───────────────────────┘                       │
└──────────────────────────────────────────────────────────────┘
                           │
                    Internet (4G/WiFi)
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  Your Gateway (home server / VPS / wherever)                 │
│  - Claude API access                                         │
│  - All your channels (Discord, etc.)                         │
│  - Memory, calendar, skills                                  │
└──────────────────────────────────────────────────────────────┘
```

### How It Works

1. Pi boots → connects to gateway as a node
2. You talk to OpenClaw (via Discord, voice, whatever)
3. Gateway routes CAN commands to the Pi node
4. Pi executes commands locally, returns results

### CAN as a Skill

Create a skill that knows about the CAN tools:

```
skills/car-control/
├── SKILL.md
├── scripts/
│   ├── can_read.py      # Read vehicle state
│   ├── can_climate.py   # Control HVAC
│   └── can_sniff.py     # Capture CAN traffic
└── references/
    ├── toyota_sienna.md # Known CAN IDs
    └── hvac_commands.md # Decoded climate messages
```

The skill teaches Claude how to use the CAN tools:

```markdown
# SKILL.md
---
name: car-control
description: Control vehicle CAN bus (climate, state). Use when user asks about car temperature, HVAC, or vehicle state. Requires pii-chan node to be connected.
---

## Tools Available (via node exec)

### Read Vehicle State
`piichan read-state`
Returns: JSON with speed, gear, battery, climate settings, etc.

### Set Climate
`piichan climate --zone <driver|passenger|rear|all> --temp <60-85> --mode <auto|face|feet|both|defrost> --sync <on|off>`

### Sniff CAN Traffic
`piichan sniff --duration 30 --filter <hex-id>`
Captures CAN messages for reverse engineering.
```

---

## 2. Self-Sniffing CAN Messages

The skill can guide Claude through discovering new CAN messages:

### Sniffing Workflow

1. **Baseline capture**: Record CAN traffic with no changes
2. **Action capture**: Record while toggling a control (e.g., rear climate)
3. **Diff analysis**: Claude compares captures to find changed messages
4. **Validation**: Test by replaying suspected messages

### Implementation

```python
#!/usr/bin/env python3
# scripts/can_sniff.py

import can
import json
import sys
from collections import defaultdict

def sniff(duration_sec=30, filter_id=None):
    """Capture CAN traffic and return summary."""
    bus = can.Bus(channel='can0', bustype='socketcan')
    messages = defaultdict(list)
    
    start = time.time()
    while time.time() - start < duration_sec:
        msg = bus.recv(timeout=0.1)
        if msg and (filter_id is None or msg.arbitration_id == filter_id):
            messages[hex(msg.arbitration_id)].append({
                'time': time.time() - start,
                'data': msg.data.hex()
            })
    
    # Return summary
    summary = {}
    for arb_id, msgs in messages.items():
        unique_data = set(m['data'] for m in msgs)
        summary[arb_id] = {
            'count': len(msgs),
            'unique_values': len(unique_data),
            'samples': list(unique_data)[:5]
        }
    
    return json.dumps(summary, indent=2)

if __name__ == '__main__':
    print(sniff())
```

### Claude-Assisted Decoding

You: "Hey, I'm going to toggle the rear climate mode. Help me figure out which CAN message controls it."

Claude:
1. Starts baseline capture
2. Prompts you to toggle the control
3. Starts action capture
4. Diffs the results
5. Identifies candidate message IDs
6. Suggests validation commands

---

## 3. Easy Car Setup (Hit a Few Buttons)

### Boot Sequence

When Pi powers on:

1. **Network auto-connect** (tries in order):
   - USB tether (if phone plugged in)
   - WiFi hotspot from phone
   - Car's built-in WiFi (if available)
   - 4G HAT (if installed)

2. **OpenClaw node start**:
   - Connects to gateway automatically
   - Announces itself: "Pii-chan online"

3. **Voice ready**:
   - Wake word listener active
   - Or push-to-talk button

### systemd Service

```ini
# /etc/systemd/system/piichan.service
[Unit]
Description=Pii-chan OpenClaw Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Environment=OPENCLAW_GATEWAY_TOKEN=<token>
ExecStart=/usr/local/bin/openclaw node run --host gateway.example.com --port 18789 --display-name "Pii-chan"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### First-Time Pairing (One-Time)

1. Put Pi on same network as gateway (home WiFi)
2. Run: `openclaw node run --host <gateway> --port 18789`
3. On gateway: `openclaw devices approve <requestId>`
4. Pi saves credentials to `~/.openclaw/node.json`
5. Future boots auto-connect

### The "Few Buttons" Experience

After initial setup, daily use is:

1. **Get in car** → Pi auto-boots from 12V power
2. **Say wake word** or press button → "Hey Pii-chan"
3. **Talk** → Full OpenClaw via voice

No app to open, no pairing to do, no settings to configure.

---

## 4. Connectivity Options

### Option A: Phone USB Tether (Simplest)

**Setup**: Plug phone into Pi USB port

**How it works**:
- Android/iPhone provides RNDIS network interface
- Pi auto-detects and uses for internet
- No additional hardware

**Pros**:
- No extra cost
- Phone charges from car
- Most reliable connection

**Cons**:
- Must plug in phone every time
- Uses phone data plan

**Auto-config** (systemd-networkd):

```ini
# /etc/systemd/network/50-usb-tether.network
[Match]
Name=usb*
Driver=rndis_host

[Network]
DHCP=yes
```

**udev rule** (auto-symlink):

```
# /etc/udev/rules.d/90-usb-tether.rules
ACTION=="add", SUBSYSTEM=="net", DRIVERS=="rndis_host", SYMLINK+="usb-tether"
```

---

### Option B: Phone WiFi Hotspot

**Setup**: Enable hotspot on phone, configure Pi to connect

**How it works**:
- Pi connects to phone's WiFi hotspot
- Can auto-connect when hotspot detected

**Pros**:
- Wireless, no cable
- Phone can stay in pocket

**Cons**:
- Must remember to enable hotspot
- More battery drain on phone
- Hotspot sometimes sleeps

**Config** (`/etc/wpa_supplicant/wpa_supplicant.conf`):

```
network={
    ssid="iPhone-Hotspot"
    psk="password"
    priority=10
}

network={
    ssid="HomeWiFi"
    psk="password"
    priority=5
}
```

---

### Option C: Sienna's Built-in WiFi

**Does 2025 Sienna have WiFi?**: Yes, via Toyota's Audio Multimedia system. But:

- It's consumer WiFi (join as client), not infrastructure
- May require active subscription
- Connection handled via infotainment, not automatic

**Verdict**: Probably not reliable enough for always-on Pi connection.

---

### Option D: Dedicated 4G HAT (Fully Tetherless)

**Hardware**: 
- Waveshare SIM7600G-H 4G HAT (~$60-80)
- Or Sixfab 4G/LTE Modem Kit (~$100)

**How it works**:
- Pi has its own cellular modem
- Uses separate SIM card / data plan
- Completely independent of phone

**Pros**:
- True always-on connectivity
- No phone required
- GPS built into most 4G modules

**Cons**:
- Extra monthly cost (~$10-20/mo for data plan)
- More complex setup
- Another SIM to manage

**Data plans**:
- T-Mobile prepaid data: ~$10/mo for 2GB
- Sixfab IoT SIM: Pay-as-you-go
- Google Fi data-only SIM: ~$10/GB

**Good for**: If you want Pii-chan to work without any phone interaction ever.

---

### Option E: Android Auto / CarPlay Bridge (Experimental)

**Idea**: Use Android Auto / CarPlay connection for both display AND internet

**Reality**: 
- AA/CarPlay protocols don't expose internet to external devices
- The data flows phone → head unit, not phone → Pi
- Would need to intercept/proxy the connection

**Verdict**: Not practical. Stick with USB tether or dedicated 4G.

---

## Recommended Setup

### Phase 1: Development (Now)

- **USB tether** when in car
- Pi on home WiFi for dev
- Test CAN reading with WiCAN

### Phase 2: Daily Driver

- **USB tether** as primary (plug phone in when driving anyway)
- **WiFi hotspot** as backup
- Systemd auto-reconnect

### Phase 3: Fully Autonomous (Optional)

- **4G HAT** with cheap data plan
- Works even without phone
- Good for trips where phone might die

---

## Hardware Shopping List (Updated)

| Component | Purpose | Price | Priority |
|-----------|---------|-------|----------|
| Raspberry Pi 5 8GB | Compute | ~$80 | Required |
| Waveshare 2-CH CAN HAT | CAN interface | ~$25 | Required |
| 12V→5V 5A Converter | Power | ~$15 | Required |
| USB Mic | Voice input | ~$15 | Required |
| MAX98357A + Speaker | Audio output | ~$11 | Required |
| WiCAN OBD | CAN sniffing | ~$50 | For HVAC decode |
| HyperPixel 4.0 | Display | ~$55 | Optional |
| Waveshare SIM7600 4G HAT | Cellular | ~$70 | Optional |

**Minimum Required**: ~$150 (Pi + CAN + power + audio)
**With Sniffing**: ~$200 (add WiCAN)
**Fully Loaded**: ~$320 (add display + 4G)

---

## Next Steps

1. ✅ Document architecture (this file)
2. ⏳ Create car-control skill
3. ⏳ Build `piichan` CLI wrapper for CAN operations
4. ⏳ Test node connection flow
5. ⏳ Order hardware
6. ⏳ Sniff HVAC CAN messages
7. ⏳ Implement climate control

---

*Last updated: 2025-02-28*
