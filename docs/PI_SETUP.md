# Pi Setup Guide

Get your Pi 5 running as an OpenClaw node.

## Phase 1: Headless Bootstrap (No Display Needed)

### Flash the SD Card

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Choose:
   - **OS:** Raspberry Pi OS (64-bit) — the full version, not Lite
   - **Storage:** Your SD card
3. Click ⚙️ (gear icon) **before writing** and configure:
   - ✅ Set hostname: `piichan`
   - ✅ Enable SSH (use password authentication)
   - ✅ Set username: `pi` (or whatever you want)
   - ✅ Set password: (pick something)
   - ✅ Configure WiFi: your home network SSID + password
   - ✅ Set locale: your timezone
4. Write the image

### First Boot

1. Insert SD card into Pi
2. Connect power
3. Wait 2-3 minutes for first boot

### Connect via SSH

From your laptop:

```bash
# Try mDNS first
ssh pi@piichan.local

# If that doesn't work, find the IP from your router
# or scan:
nmap -sn 192.168.1.0/24 | grep -i raspberry
```

### Initial System Setup

```bash
# Update everything
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y git curl build-essential

# Verify you're on 64-bit
uname -m  # should show "aarch64"
```

## Phase 2: Install OpenClaw Node

```bash
# Install OpenClaw
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard

# Configure as a node (not a gateway)
openclaw onboard --node
```

When prompted:
- **Gateway URL:** `wss://your-gateway-ip:18789` (or your AWS hostname)
- Complete the pairing process

### Approve on Gateway

On your AWS server:
```bash
openclaw nodes pending
openclaw nodes approve <requestId>
```

Verify connection:
```bash
openclaw nodes status  # should show piichan as connected
```

## Phase 3: Voice Stack

### Install Vosk (Speech-to-Text)

```bash
pip3 install vosk

# Download model (~50MB)
mkdir -p ~/models
cd ~/models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
```

### Install Piper (Text-to-Speech)

```bash
pip3 install piper-tts

# Download a voice
mkdir -p ~/piper-voices
cd ~/piper-voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### Install OpenWakeWord

```bash
pip3 install openwakework

# Test it
python3 -c "import openwakeword; print('OK')"
```

### Audio Setup

```bash
# List audio devices
arecord -l  # microphones
aplay -l    # speakers

# Test recording
arecord -d 3 -f cd test.wav
aplay test.wav
```

## Phase 4: CAN HAT Setup

### Enable SPI

```bash
sudo raspi-config
# Interface Options → SPI → Enable
```

Or edit `/boot/firmware/config.txt`:
```
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=24
```

Reboot:
```bash
sudo reboot
```

### Bring Up CAN Interface

```bash
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 500000

# Verify
ip link show can0
```

### Install CAN Tools

```bash
sudo apt install -y can-utils

# Test (will show nothing until connected to car)
candump can0
```

## Phase 5: Display Setup (When Adapter Arrives)

Check your Waveshare model and follow their specific guide:
- **DSI displays:** Just connect the ribbon cable
- **HDMI displays:** Connect micro HDMI → adapter → display HDMI

Test:
```bash
# Should show display info
DISPLAY=:0 xrandr
```

## Validation Checklist

Run these to confirm everything works:

```bash
# OpenClaw node connected
openclaw nodes status  # from gateway

# Voice input
arecord -d 3 test.wav && aplay test.wav

# Voice output
echo "Hello from Pii-chan" | piper --model ~/piper-voices/en_US-lessac-medium.onnx --output_file test.wav && aplay test.wav

# CAN interface (won't show traffic until in car)
ip link show can0

# Full system
python3 -c "import vosk, openwakeword; print('Voice stack OK')"
```

## Troubleshooting

### SSH connection refused
- Wait longer (first boot takes time)
- Check WiFi credentials were correct
- Connect monitor temporarily to see boot errors

### OpenClaw node won't connect
- Check gateway URL is correct (wss:// not ws://)
- Verify gateway is accessible from Pi's network
- Check firewall allows port 18789

### No audio devices
- USB mic/speaker might need `pulseaudio` or `pipewire`
- Run `sudo apt install pulseaudio` and reboot

### CAN interface missing
- Verify SPI is enabled
- Check dtoverlay lines in config.txt
- Verify HAT is seated properly

---

*Next: Connect to car and start sniffing CAN!*
