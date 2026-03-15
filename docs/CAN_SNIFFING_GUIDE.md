# CAN Bus Sniffing Guide for Toyota Sienna

This guide covers how to reverse engineer CAN bus messages on your 2025 Toyota Sienna, specifically targeting HVAC (climate control) for Mira integration.

## Goal

Find the CAN message IDs and byte patterns for:
- Temperature control (driver/passenger)
- Fan speed
- AC on/off
- Vent mode (face/feet/defrost)
- Seat heaters (if equipped)

## Hardware Options

### Option 1: WiCAN OBD (~$50) ⭐ Recommended for beginners
- Plugs into OBD-II port
- WiFi interface — use from phone or laptop
- Works with RealDash, SavvyCAN
- Buy: [meatpi.com](https://www.meatpi.com) or [Crowd Supply](https://www.crowdsupply.com/meatpi-electronics)

### Option 2: comma.ai Panda (~$100)
- USB CAN interface
- Well-supported, known to work with Toyota
- Can also run openpilot
- Buy: [comma.ai shop](https://comma.ai/shop/panda)

### Option 3: CANable (~$25-40)
- USB-CAN adapter
- Works with Linux socketcan
- DIY-friendly
- Buy: [canable.io](https://canable.io) or clone on Amazon/AliExpress

### Option 4: Raspberry Pi + CAN HAT
- If you already have the Mira Pi setup
- Waveshare 2-CH CAN HAT
- Direct socketcan integration

## Software Setup

### On Linux (Raspberry Pi or laptop)

```bash
# Install can-utils
sudo apt install can-utils

# For USB adapters (CANable, Panda)
sudo modprobe can
sudo modprobe can_raw
sudo modprobe slcan  # for serial adapters

# Bring up CAN interface (adjust bitrate if needed)
# Toyota typically uses 500kbps
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up

# Verify
ip link show can0
```

### SavvyCAN (GUI - recommended for analysis)

```bash
# Install Qt dependencies
sudo apt install qtbase5-dev qtserialbus5-dev

# Clone and build
git clone https://github.com/collin80/SavvyCAN.git
cd SavvyCAN
qmake
make
./SavvyCAN
```

Or download pre-built: [SavvyCAN releases](https://github.com/collin80/SavvyCAN/releases)

### Python (for scripting)

```bash
pip install python-can cantools
```

## Sniffing Procedure

### Step 1: Baseline Capture

With the car running (engine on or READY mode for hybrid):

```bash
# Start logging ALL CAN traffic
candump -l can0
# This creates a log file: candump-YYYY-MM-DD_HHMMSS.log

# Let it run for 30 seconds without touching anything
# This establishes baseline traffic
```

### Step 2: Capture While Changing Climate

```bash
# Start a new capture
candump -l can0

# While capturing, do these ONE AT A TIME with 5-second pauses:
# 1. Increase driver temp from 70°F to 75°F
# 2. Wait 5 sec
# 3. Decrease driver temp back to 70°F
# 4. Wait 5 sec
# 5. Increase fan speed one notch
# 6. Wait 5 sec
# 7. Turn AC off
# 8. Wait 5 sec
# 9. Turn AC on
# 10. Change vent mode (face -> feet -> defrost)

# Stop capture with Ctrl+C
```

### Step 3: Analyze with SavvyCAN

1. Open SavvyCAN
2. Load your candump log file
3. Go to **Analysis > Range State Analyzer**
4. Look for message IDs that changed during your climate adjustments
5. Common HVAC message IDs on Toyota: `0x540-0x5FF` range

### Step 4: Identify Byte Meanings

Once you find a candidate message ID:

```bash
# Filter to just that ID
candump can0,540:7FF

# While watching, adjust temperature
# Note which byte position changes and by how much
```

Example discovery:
```
# ID 0x540, 8 bytes
# Byte 0: Driver temp (0x00-0x3F maps to 60°F-90°F)
# Byte 1: Passenger temp
# Byte 2: Fan speed (0x00=off, 0x01-0x07 = speeds)
# Byte 3: Mode (0x01=face, 0x02=feet, 0x04=defrost)
# Byte 4: Flags (bit 0 = AC on)
```

### Step 5: Test Write (BE CAREFUL)

⚠️ **WARNING:** Only test write on non-safety systems like HVAC. Never inject steering, brake, or throttle messages.

```bash
# Send a single test frame
# Replace with your discovered message format
cansend can0 540#1B18040100000000

# Watch for:
# - Did the climate display change?
# - Did the AC turn on/off?
# - Did temperature adjust?
```

## What to Document

When you find a message, document it like this:

```
Message ID: 0x540
Name: CLIMATE_CONTROL
Length: 8 bytes
Bus: Body CAN (or OBD-II filtered?)

Byte 0: driver_temp
  - Range: 0x00-0x3F
  - Formula: temp_f = (value * 0.5) + 60
  - Unit: °F

Byte 1: passenger_temp
  - Same as byte 0

Byte 2: fan_speed
  - 0x00 = Off
  - 0x01-0x07 = Speed 1-7
  - 0x08 = Auto

Byte 3: vent_mode
  - 0x01 = Face
  - 0x02 = Bi-level
  - 0x04 = Feet
  - 0x08 = Feet+Defrost
  - 0x10 = Defrost

Byte 4: flags
  - Bit 0: AC compressor request
  - Bit 1: Recirculation
  - Bit 2: Auto mode

Byte 5-7: Unknown/reserved
```

## Potential Issues

### 1. Security Gateway Filtering
The 2025 Sienna has a security gateway that may filter OBD-II port access. If you can't see HVAC messages through OBD:

**Solutions:**
- Direct CAN tap behind the gateway (requires finding body CAN wires)
- Look for body CAN on the OBD connector pins that bypass gateway
- Some aftermarket harnesses provide direct access

### 2. CAN-FD
Newer Toyotas may use CAN-FD (flexible data rate) instead of classic CAN. If you see garbled data:

```bash
# Try CAN-FD mode
sudo ip link set can0 type can bitrate 500000 dbitrate 2000000 fd on
```

### 3. Multiple CAN Buses
The car has multiple buses:
- **Powertrain CAN** — Engine, transmission
- **Body CAN** — HVAC, doors, lights ← We want this
- **Chassis CAN** — ABS, steering

OBD-II port typically connects to powertrain CAN. You may need to find body CAN access point.

## Adding to Mira

Once you've documented the HVAC messages, add them to the DBC file:

```dbc
BO_ 1344 CLIMATE_CONTROL: 8 XXX
 SG_ DRIVER_TEMP : 7|8@0+ (0.5,60) [60|90] "degF" XXX
 SG_ PASSENGER_TEMP : 15|8@0+ (0.5,60) [60|90] "degF" XXX
 SG_ FAN_SPEED : 23|8@0+ (1,0) [0|8] "" XXX
 SG_ VENT_MODE : 31|8@0+ (1,0) [0|31] "" XXX
 SG_ AC_ON : 32|1@0+ (1,0) [0|1] "" XXX
 SG_ RECIRC : 33|1@0+ (1,0) [0|1] "" XXX
```

Then add CAN write capability to Mira:

```python
# In can_reader.py, add write method
def send_climate_command(self, driver_temp=None, fan_speed=None, ac_on=None):
    """Send climate control command."""
    # Build message from current state + changes
    data = self._build_climate_message(driver_temp, fan_speed, ac_on)
    msg = can.Message(arbitration_id=0x540, data=data)
    self.bus.send(msg)
```

## Resources

- [SavvyCAN documentation](https://github.com/collin80/SavvyCAN/wiki)
- [can-utils man pages](https://manpages.debian.org/testing/can-utils/candump.1.en.html)
- [Car Hacking Village Discord](https://discord.gg/carhacking)
- [comma.ai Discord #toyota](https://discord.comma.ai)

## Safety Reminder

🚨 **DO NOT:**
- Inject steering, brake, or throttle messages
- Sniff while actively driving (park safely first)
- Disable any safety systems

✅ **SAFE TO EXPERIMENT:**
- Climate control (HVAC)
- Interior lights
- Door lock status (read-only!)
- Entertainment system

---

*Document your findings! If you successfully decode Sienna HVAC messages, please contribute back to this repo.*
