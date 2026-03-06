---
name: car-control
description: Control vehicle CAN bus for climate, read vehicle state, and assist with CAN reverse engineering. Use when user asks about car temperature, HVAC settings, vehicle state (speed, battery, gear), or wants to decode CAN messages. Requires pii-chan node to be online.
---

# Car Control Skill

Controls the vehicle via CAN bus through the pii-chan node.

## Prerequisites

- Pii-chan node must be connected (`openclaw nodes status`)
- Node name: `pii-chan` (or as configured)

## Available Commands

All commands run via `nodes run --node pii-chan`:

### Read Vehicle State

```bash
openclaw nodes run --node pii-chan -- piichan state
```

Returns JSON with:
- `engine_running`, `speed_kmh`, `gear`
- `battery_soc`, `fuel_level`
- `climate`: `{driver_temp, passenger_temp, rear_temp, fan, mode, sync}`
- `doors`: `{fl, fr, rl, rr, trunk}`

### Set Climate

```bash
openclaw nodes run --node pii-chan -- piichan climate [options]
```

Options:
- `--zone <driver|passenger|rear|all>` - Which zone to control
- `--temp <60-85>` - Temperature in Fahrenheit
- `--fan <0-7>` - Fan speed (0 = auto)
- `--mode <auto|face|feet|both|defrost>` - Airflow direction
- `--sync <on|off>` - Sync all zones to driver

Examples:
```bash
# Set rear to feet only, 72°F
piichan climate --zone rear --mode feet --temp 72 --sync off

# Turn on defrost
piichan climate --mode defrost --fan 5

# "I'm cold" → raise driver temp
piichan climate --zone driver --temp 74
```

### Turn Climate Off

```bash
openclaw nodes run --node pii-chan -- piichan climate-off
```

### Sniff CAN Traffic (Reverse Engineering)

```bash
openclaw nodes run --node pii-chan -- piichan sniff [options]
```

Options:
- `--duration <seconds>` - How long to capture (default: 30)
- `--filter <hex-id>` - Only capture specific arbitration ID
- `--output <file>` - Save raw capture to file

Returns summary of all captured message IDs with sample data.

## CAN Reverse Engineering Workflow

When user wants to decode a new CAN message:

1. **Baseline capture**: `piichan sniff --duration 30 > baseline.json`
2. **Prompt user**: "Toggle the control you want to decode"
3. **Action capture**: `piichan sniff --duration 30 > action.json`
4. **Diff analysis**: Compare captures to find changed messages
5. **Identify candidates**: Messages that changed during action
6. **Test replay**: `piichan can-write <id> <data>` to validate

## Known CAN IDs (Toyota Sienna 2025)

See `references/toyota_sienna.md` for decoded messages:
- Engine state, speed, RPM
- Gear position
- Battery SOC
- Door status

HVAC messages: See `references/hvac_commands.md` (to be decoded via sniffing)

## Conversation Patterns

**User says** → **Action**

| User Input | Command |
|------------|---------|
| "How's the car?" | `piichan state` |
| "I'm cold" / "I'm hot" | Adjust climate ±2-3°F |
| "Set rear to feet" | `piichan climate --zone rear --mode feet --sync off` |
| "Turn off climate" | `piichan climate-off` |
| "Sync climate" | `piichan climate --sync on` |
| "What's my battery at?" | `piichan state` → report battery_soc |

## Error Handling

- **Node offline**: "Pii-chan isn't connected. Is the car on?"
- **CAN timeout**: "Can't reach the car's CAN bus. Check the connection."
- **Unknown command**: "That climate control isn't decoded yet. Want to sniff it?"
