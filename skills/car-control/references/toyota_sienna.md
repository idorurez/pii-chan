# Toyota Sienna 2025 CAN Reference

## Known CAN IDs

These are common Toyota CAN IDs. Exact values need validation on your vehicle.

### Engine / Powertrain

| ID | Name | Bytes | Notes |
|----|------|-------|-------|
| 0x2C4 | Engine RPM | B0-1 | RPM = value / 4 |
| 0x0B4 | Vehicle Speed | B0-1 | km/h |
| 0x3B7 | Gear Position | B0 | P=0, R=1, N=2, D=3 |
| 0x3CB | Hybrid Battery | B0 | SOC % |

### Body

| ID | Name | Bytes | Notes |
|----|------|-------|-------|
| 0x620 | Door Status | B0 | Bitfield: FL/FR/RL/RR/Trunk |
| 0x621 | Light Status | B0 | Headlights, turn signals |

### Climate (TO BE DECODED)

HVAC messages are not publicly documented. Use sniffing workflow to decode:

1. `piichan sniff --duration 30 > baseline.json`
2. Toggle climate control
3. `piichan sniff --duration 30 > with_change.json`
4. Diff to find changed message IDs

Suspected range: 0x500-0x5FF (body CAN)

## CAN Bus Notes

- **HS-CAN**: Engine/powertrain, 500 kbps
- **MS-CAN**: Body/comfort, 125 kbps (HVAC likely here)
- **OBD port**: Usually HS-CAN only, may need direct tap for HVAC

## SecOC Status

Toyota uses SecOC (Security Onboard Communication) for safety-critical messages:

- ✅ **Reading**: Works fine (messages signed, not encrypted)
- ⚠️ **Writing safety messages**: Blocked (steering, braking, ADAS)
- ✅ **Writing body messages**: Should work (HVAC, lights, etc.)

HVAC is on body CAN and should NOT be SecOC protected.
