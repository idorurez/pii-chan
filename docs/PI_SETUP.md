# Pi Setup Guide

Get your Raspberry Pi running as an OpenClaw node connected to your gateway.

## Prerequisites

- Raspberry Pi 5 (or Pi 4 with 4GB+ RAM)
- SD card (32GB+ recommended)
- Your gateway already running (see GATEWAY_SETUP.md)
- Tailscale installed on both gateway and Pi (for secure connectivity)

---

## Phase 1: Headless Bootstrap (No Display Needed)

### Flash the SD Card

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Choose:
   - **OS:** Raspberry Pi OS (64-bit) — the full version, not Lite
   - **Storage:** Your SD card
3. Click ⚙️ (gear icon) **before writing** and configure:
   - ✅ Set hostname: `piichan`
   - ✅ Enable SSH (use password authentication)
   - ✅ Set username: `piichan` (match the hostname for simplicity)
   - ✅ Set password: (pick something secure)
   - ✅ Configure WiFi: your home network SSID + password
   - ✅ Set locale: your timezone
4. Write the image

### First Boot

1. Insert SD card into Pi
2. Connect power
3. Wait 2-3 minutes for first boot

### Connect via SSH

```bash
# Try mDNS first
ssh piichan@piichan.local

# If that doesn't work, find the IP from your router or scan:
nmap -sn 192.168.1.0/24 | grep -B2 "raspberry\|piichan"
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

---

## Phase 2: Tailscale (Secure Connectivity)

Use Tailscale for secure gateway connectivity. This encrypts all traffic and avoids exposing ports to the internet.

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate (will give you a URL to authorize)
sudo tailscale up

# Get your Tailscale IP
tailscale ip -4
# Example: 100.76.12.120
```

Note your Tailscale IP — you'll need it for the gateway to identify the Pi.

---

## Phase 3: Install OpenClaw Node

```bash
# Install OpenClaw
curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

### Fix PATH (if `openclaw` command not found)

The npm global bin directory may not be in your PATH:

```bash
# Add npm global bin to PATH
mkdir -p ~/.npm-global/bin
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
which openclaw  # should show ~/.npm-global/bin/openclaw
openclaw --version
```

---

## Phase 4: Create the Systemd Service

⚠️ **IMPORTANT:** The service file MUST have proper section headers (`[Unit]`, `[Service]`, `[Install]`). Missing brackets will silently fail!

```bash
sudo tee /etc/systemd/system/piichan.service << 'EOF'
[Unit]
Description=Pii-chan OpenClaw Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=piichan
Environment=OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1
Environment=OPENCLAW_GATEWAY_TOKEN=YOUR_GATEWAY_TOKEN_HERE
ExecStart=/home/piichan/.npm-global/bin/openclaw node run --host YOUR_GATEWAY_TAILSCALE_IP --port 18789 --display-name piichan
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

Replace:
- `YOUR_GATEWAY_TOKEN_HERE` — the token from `gateway.auth.token` in your gateway config
- `YOUR_GATEWAY_TAILSCALE_IP` — your gateway's Tailscale IP (e.g., `100.112.61.98`)

**Why `OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1`?**  
Tailscale encrypts the transport, so we don't need TLS on the WebSocket. This env var allows non-TLS connections over private IPs.

### Enable the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable piichan
```

**Don't start it yet** — we need to approve the pairing first.

---

## Phase 5: Initial Pairing

### Start the Service

```bash
sudo systemctl start piichan
sudo journalctl -u piichan -f
```

The first connection will fail with "pairing required" — this is expected.

### Approve on Gateway

On your gateway server:

```bash
# Check pending requests
docker exec wintermute cat /home/node/.openclaw/devices/pending.json
```

You'll see something like:
```json
{
  "abc123-request-id": {
    "requestId": "abc123-request-id",
    "deviceId": "9ebb2619f0d0e278...",
    "publicKey": "pPvuYs_I1uk...",
    "displayName": "piichan",
    "role": "node",
    ...
  }
}
```

**Option A: CLI Approval (if it works)**
```bash
docker exec -w /app wintermute node dist/index.js devices approve abc123-request-id
```

**Option B: Manual Approval (if CLI has auth issues)**

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#manual-device-approval) for the manual approval process.

### Verify Connection

On the Pi:
```bash
# Check for established TCP connection
ss -tnp | grep 18789
# Should show: ESTAB ... 100.76.12.120:xxxxx 100.112.61.98:18789
```

On the gateway:
```bash
docker exec wintermute cat /home/node/.openclaw/devices/paired.json | grep -A5 "tokens"
# Should show a token entry with createdAtMs timestamp
```

---

## Understanding the Identity System

OpenClaw uses a cryptographic identity system:

```
~/.openclaw/
├── identity/
│   └── device.json       # Permanent device identity (DO NOT DELETE)
│       ├── deviceId      # Hash of public key
│       ├── publicKeyPem  # Ed25519 public key
│       └── privateKeyPem # Ed25519 private key (keep secret!)
└── node.json             # Connection config
    ├── nodeId            # Session UUID (can change)
    ├── displayName       # Human-readable name
    └── gateway           # Gateway connection info
```

**Critical:** The `identity/` folder is your Pi's permanent identity. If you delete it:
- A new identity is generated
- The old pairing on the gateway becomes invalid
- You must re-approve the new identity

---

## Phase 6: Voice Stack

### Create Python Virtual Environment

Raspberry Pi OS requires a venv for pip packages:

```bash
cd ~/pii-chan
python3 -m venv venv
source venv/bin/activate

# Install all voice dependencies
pip install piper-tts vosk openwakeword
```

**Always activate the venv before running voice scripts:**
```bash
source ~/pii-chan/venv/bin/activate
```

### Download Vosk Model (Speech-to-Text)

```bash
cd ~/pii-chan
mkdir -p models && cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
rm vosk-model-small-en-us-0.15.zip
cd ..
```

### Download Piper Voice (Text-to-Speech)

```bash
cd ~/pii-chan
mkdir -p voices && cd voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
cd ..
```

### Audio Hardware Setup

```bash
# List capture devices (microphones)
arecord -l

# List playback devices (speakers)
aplay -l

# Test recording (3 seconds)
arecord -D plughw:2,0 -f cd -d 3 test.wav

# Test playback
aplay test.wav
```

**Note:** The USB mic is typically `plughw:2,0`. Adjust based on `arecord -l` output.

### Test TTS (Piper)

```bash
cd ~/pii-chan
source venv/bin/activate
echo "Hello! I am Pii-chan, your car companion." | piper --model voices/en_US-lessac-medium.onnx --output_file hello.wav
aplay hello.wav  # if speakers connected
```

### Test STT (Vosk)

```bash
cd ~/pii-chan
source venv/bin/activate

# Record 3 seconds
arecord -D plughw:2,0 -f cd -d 3 test.wav

# Test recognition
cat > test_vosk.py << 'EOF'
from vosk import Model, KaldiRecognizer
import wave, json

model = Model("models/vosk-model-small-en-us-0.15")
wf = wave.open("test.wav", "rb")
rec = KaldiRecognizer(model, wf.getframerate())

while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    rec.AcceptWaveform(data)

result = json.loads(rec.FinalResult())
print("Recognized:", result.get("text", ""))
EOF

python test_vosk.py
```

---

## Phase 7: CAN HAT Setup (For Car Integration)

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

---

## Configure Exec Approvals

Remote commands from the gateway require an allowlist on the Pi. Edit `~/.openclaw/exec-approvals.json`:

```json
{
  "version": 1,
  "agents": {
    "*": {
      "allowlist": [
        {"pattern": "/usr/bin/echo"},
        {"pattern": "/usr/bin/cat"},
        {"pattern": "/usr/bin/ls"},
        {"pattern": "/usr/bin/uname"},
        {"pattern": "/usr/bin/whoami"},
        {"pattern": "/usr/bin/hostname"},
        {"pattern": "/usr/bin/date"},
        {"pattern": "/usr/bin/uptime"},
        {"pattern": "/usr/bin/lsusb"},
        {"pattern": "/usr/bin/file"},
        {"pattern": "/usr/bin/head"},
        {"pattern": "/usr/bin/tail"},
        {"pattern": "/usr/bin/wc"},
        {"pattern": "/usr/bin/grep"},
        {"pattern": "/usr/bin/which"},
        {"pattern": "/usr/bin/pip3"},
        {"pattern": "/usr/bin/git"},
        {"pattern": "/usr/bin/ip"},
        {"pattern": "/usr/bin/curl"},
        {"pattern": "/usr/bin/python3"},
        {"pattern": "/usr/bin/arecord"},
        {"pattern": "/usr/bin/aplay"},
        {"pattern": "/usr/bin/candump"},
        {"pattern": "/usr/bin/cansend"},
        {"pattern": "/usr/sbin/alsactl"},
        {"pattern": "/home/piichan/.local/bin/*"}
      ]
    }
  }
}
```

The wildcard `*` allows any command in that directory (useful for pip-installed tools like piper).

---

## Validation Checklist

```bash
# 1. Service running
sudo systemctl status piichan

# 2. TCP connection established
ss -tnp | grep 18789

# 3. Identity file exists
cat ~/.openclaw/identity/device.json | head -3

# 4. Voice input (if configured)
arecord -d 3 test.wav && aplay test.wav

# 5. Voice output (if configured)  
echo "Hello from Pii-chan" | piper --model ~/piper-voices/en_US-lessac-medium.onnx --output_file test.wav && aplay test.wav

# 6. CAN interface (if HAT installed)
ip link show can0
```

---

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues:
- Service won't start
- Pairing failures
- Connection drops
- Identity mismatches

---

*Next: Connect to car and start sniffing CAN! See [CAN_SNIFFING_GUIDE.md](./CAN_SNIFFING_GUIDE.md)*
