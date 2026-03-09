# Command Reference

Quick reference for all Pii-chan setup and maintenance commands.

---

## Gateway Commands (Docker)

### Control UI Access

```bash
# Set up Tailscale Serve for HTTPS (permanent)
sudo tailscale serve --bg --https=443 http://localhost:18789

# Check serve status
tailscale serve status

# Get your Tailscale hostname
tailscale status | head -1

# Access URL: https://YOUR-HOSTNAME.tail<id>.ts.net/
```

First-time Control UI setup:
1. Open the HTTPS URL in browser
2. Enter gateway token when prompted
3. Approve browser device when prompted: `docker exec wintermute openclaw devices approve <id>`

### Container Management

```bash
# Start/stop/restart gateway
docker compose up -d
docker compose down
docker compose restart wintermute

# View logs
docker logs wintermute --tail 50
docker logs -f wintermute  # live tail

# Execute commands inside container
docker exec -w /app wintermute node dist/index.js <command>
```

### Agent Management

```bash
# List agents
docker exec wintermute openclaw agents list

# Add pii-chan agent
docker exec wintermute openclaw agents add pii-chan \
  --workspace /home/node/.openclaw/pii-chan-workspace

# Remove agent
docker exec wintermute openclaw agents remove pii-chan
```

### Device Management

```bash
# List all devices (paired and pending)
docker exec wintermute openclaw devices list

# Approve device by request ID
docker exec wintermute openclaw devices approve <requestId>

# View paired devices (raw JSON)
docker exec wintermute cat /home/node/.openclaw/devices/paired.json

# View pending devices (raw JSON)
docker exec wintermute cat /home/node/.openclaw/devices/pending.json
```

### Node Status

```bash
# List connected nodes
docker exec wintermute openclaw nodes status

# Invoke command on node
docker exec wintermute openclaw nodes invoke \
  --node piichan \
  --command system.run \
  --params '{"command":["echo","hello"]}'
```

### Config Management

```bash
# View gateway config
docker exec wintermute cat /home/node/.openclaw/openclaw.json

# View specific section
docker exec wintermute cat /home/node/.openclaw/openclaw.json | grep -A10 '"gateway"'
```

### File Operations (Host ↔ Container)

```bash
# Copy file into container
docker cp /tmp/file.json wintermute:/home/node/.openclaw/devices/paired.json

# Copy file from container
docker exec wintermute cat /home/node/.openclaw/devices/paired.json > /tmp/paired.json
```

---

## Pi Commands

### Systemd Service

```bash
# Service control
sudo systemctl start piichan
sudo systemctl stop piichan
sudo systemctl restart piichan
sudo systemctl status piichan

# Enable/disable auto-start
sudo systemctl enable piichan
sudo systemctl disable piichan

# Reload after editing service file
sudo systemctl daemon-reload
```

### Logs

```bash
# Recent logs
sudo journalctl -u piichan --no-pager -n 50

# Live tail
sudo journalctl -u piichan -f

# Logs since time
sudo journalctl -u piichan --since "1 hour ago"

# Logs with grep
sudo journalctl -u piichan | grep -i error
```

### Connection Verification

```bash
# Check TCP connection (most reliable)
ss -tnp | grep 18789

# Check process is running
ps aux | grep openclaw

# Test gateway reachability
curl -v http://100.112.61.98:18789/health
```

### Identity & Config Files

```bash
# View device identity
cat ~/.openclaw/identity/device.json

# View node config
cat ~/.openclaw/node.json

# View service file
cat /etc/systemd/system/piichan.service
```

### Manual Node Run (for debugging)

```bash
# Stop service first
sudo systemctl stop piichan

# Run manually with full output
OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1 \
OPENCLAW_GATEWAY_TOKEN="69d05e0c49fa731be1ebcb8ed9812305" \
/home/piichan/.npm-global/bin/openclaw node run \
  --host 100.112.61.98 \
  --port 18789 \
  --display-name piichan 2>&1
```

---

## Tailscale Commands

```bash
# Check status
tailscale status

# Get your IP
tailscale ip -4

# Reconnect
sudo tailscale up

# Update Tailscale
sudo tailscale update

# View network map
tailscale netcheck
```

---

## OpenClaw CLI (on Pi)

```bash
# Check version
openclaw --version

# View help
openclaw --help
openclaw node --help

# Run node (normally via systemd)
openclaw node run --host <gateway-ip> --port 18789 --display-name piichan
```

---

## Voice Stack Commands

### Audio Testing

```bash
# List audio devices
arecord -l  # microphones
aplay -l    # speakers

# Test recording
arecord -d 3 -f cd test.wav
aplay test.wav

# Test volume
alsamixer
```

### Vosk (Speech-to-Text)

```bash
# Install
pip3 install vosk

# Download model
mkdir -p ~/models && cd ~/models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip

# Test
python3 -c "import vosk; print('Vosk OK')"
```

### Piper (Text-to-Speech)

```bash
# Install
pip3 install piper-tts

# Download voice
mkdir -p ~/piper-voices && cd ~/piper-voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# Test
echo "Hello from Pii-chan" | piper \
  --model ~/piper-voices/en_US-lessac-medium.onnx \
  --output_file test.wav && aplay test.wav
```

### OpenWakeWord

```bash
# Install
pip3 install openwakeword

# Test
python3 -c "import openwakeword; print('OpenWakeWord OK')"
```

---

## CAN Bus Commands

### Interface Setup

```bash
# Bring up interface
sudo ip link set can0 up type can bitrate 500000
sudo ip link set can1 up type can bitrate 500000

# Check status
ip link show can0

# Bring down
sudo ip link set can0 down
```

### CAN Tools

```bash
# Install
sudo apt install -y can-utils

# Dump all traffic
candump can0

# Dump with timestamps
candump -t d can0

# Send a message
cansend can0 123#DEADBEEF

# Filter specific IDs
candump can0,0x123:0x7FF
```

---

## File Locations Reference

### Gateway (Docker)

| File | Path |
|------|------|
| Main config | `/home/node/.openclaw/openclaw.json` |
| Paired devices | `/home/node/.openclaw/devices/paired.json` |
| Pending devices | `/home/node/.openclaw/devices/pending.json` |
| Gateway identity | `/home/node/.openclaw/identity/device.json` |
| Pii-chan workspace | `/home/node/.openclaw/pii-chan-workspace/` |
| Skills | `/home/node/.openclaw/skills/` |

### Pi

| File | Path |
|------|------|
| Node config | `~/.openclaw/node.json` |
| Device identity | `~/.openclaw/identity/device.json` |
| Systemd service | `/etc/systemd/system/piichan.service` |
| OpenClaw binary | `~/.npm-global/bin/openclaw` |
| Vosk models | `~/models/` |
| Piper voices | `~/piper-voices/` |

---

## Quick Diagnostics

### "Is it connected?"

```bash
# On Pi
ss -tnp | grep 18789 && echo "✅ Connected" || echo "❌ Not connected"
```

### "Is the service running?"

```bash
# On Pi
systemctl is-active piichan && echo "✅ Running" || echo "❌ Not running"
```

### "Can Pi reach gateway?"

```bash
# On Pi
curl -s http://100.112.61.98:18789/health | grep -q '"ok":true' && echo "✅ Reachable" || echo "❌ Unreachable"
```

### "What's my identity?"

```bash
# On Pi
cat ~/.openclaw/identity/device.json | grep deviceId
```

### "What devices are paired?"

```bash
# On Gateway
docker exec wintermute cat /home/node/.openclaw/devices/paired.json | grep displayName
```
