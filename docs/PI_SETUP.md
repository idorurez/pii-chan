# Pi Setup Guide

Getting Pii-chan running on your Raspberry Pi 5.

## Prerequisites

- Raspberry Pi 5 8GB
- SD Card with Raspberry Pi OS (64-bit) flashed
- Network connection (ethernet or WiFi)
- Your AWS gateway running OpenClaw

## Step 1: Basic Pi Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
    git \
    python3-pip \
    python3-venv \
    bluetooth \
    bluez \
    can-utils \
    portaudio19-dev \
    libsndfile1

# Enable SPI (for CAN HAT)
sudo raspi-config nonint do_spi 0

# Reboot
sudo reboot
```

## Step 2: Install Node.js 22

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs
node --version  # Should show v22.x
```

## Step 3: Install OpenClaw

```bash
sudo npm install -g openclaw
```

## Step 4: Connect to Your Gateway

```bash
# Set your gateway token
export OPENCLAW_GATEWAY_TOKEN="<your-token-from-aws-gateway>"

# Test connection
openclaw node run --host <your-aws-ip> --port 18789 --display-name "pii-chan"
```

On your AWS gateway, approve the node:
```bash
openclaw nodes pending
openclaw nodes approve <requestId>
```

If this works, OpenClaw on Pi is validated! ✅

## Step 5: Clone Pii-chan Repo

```bash
cd ~
git clone https://github.com/idorurez/pii-chan.git
cd pii-chan

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

## Step 6: Test Voice Components

### Test Vosk (STT)
```bash
pip install vosk sounddevice

# Download model
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
cd ..

# Test
python -c "
from vosk import Model
model = Model('models/vosk-model-small-en-us-0.15')
print('Vosk loaded successfully!')
"
```

### Test Piper (TTS)
```bash
pip install piper-tts

# Test
echo 'Hello, I am Pii-chan!' | piper --model en_US-lessac-medium --output_file test.wav
aplay test.wav
```

### Test OpenWakeWord
```bash
pip install openwakeword

# Test
python -c "
from openwakeword import Model
model = Model()
print('OpenWakeWord loaded successfully!')
print('Available models:', model.models)
"
```

## Step 7: Setup CAN HAT (If Installed)

```bash
# Add to /boot/config.txt
sudo nano /boot/config.txt

# Add these lines:
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=24

# Reboot
sudo reboot

# Bring up CAN interface
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 500000

# Test
candump can0
```

## Step 8: Test Presence Detection

```bash
cd ~/pii-chan
source venv/bin/activate

# Find your phone's Bluetooth MAC
bluetoothctl scan on
# Look for your phone, note the MAC address
# Press Ctrl+C to stop

# Edit presence.py with your phone's MAC
nano src/presence.py
# Add your MAC to OWNER_DEVICES_MAC list

# Test
python src/presence.py
```

## Step 9: Install as Services (Optional)

```bash
# Copy service files
sudo cp systemd/*.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable piichan-node piichan-presence
sudo systemctl start piichan-node piichan-presence

# Check status
sudo systemctl status piichan-node
```

## Validation Checklist

- [ ] Pi boots and connects to network
- [ ] Node.js 22 installed
- [ ] `openclaw node run` connects to AWS gateway
- [ ] Node approved on gateway
- [ ] Vosk STT works
- [ ] Piper TTS works  
- [ ] OpenWakeWord loads
- [ ] CAN interface comes up (if HAT installed)
- [ ] Presence detection sees your phone

## Troubleshooting

### OpenClaw node won't connect
```bash
# Check network
ping <your-aws-ip>

# Check token
echo $OPENCLAW_GATEWAY_TOKEN

# Run with verbose
openclaw node run --host <ip> --port 18789 --verbose
```

### CAN interface not found
```bash
# Check SPI enabled
ls /dev/spi*

# Check dmesg for errors
dmesg | grep -i can
dmesg | grep -i mcp

# Verify config.txt changes took effect
cat /boot/config.txt | grep mcp
```

### Audio not working
```bash
# List audio devices
arecord -l
aplay -l

# Test recording
arecord -d 5 test.wav
aplay test.wav
```

## Next Steps

Once validation passes:
1. Set up the full voice pipeline
2. Configure personality
3. Set up display UI
4. Test in car with hotspot

See `PRODUCT.md` for full Phase 1 checklist.
