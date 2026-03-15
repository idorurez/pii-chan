# OpenClaw Node Setup Guide

Connecting your Pi to your AWS OpenClaw gateway.

## Prerequisites

- Raspberry Pi 5 with Raspberry Pi OS (64-bit)
- AWS instance running OpenClaw gateway
- Tailscale installed on both (optional but recommended)
- Gateway auth token

---

## Option A: With Tailscale (Recommended)

Tailscale creates a secure mesh VPN — your Pi and AWS gateway can talk directly via Tailscale IPs, no port forwarding or SSH tunnels needed.

### Step 1: Install Tailscale on Pi

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Note your Tailscale IP
tailscale ip -4
# Example: 100.x.y.z
```

### Step 2: Verify Tailscale on AWS Gateway

```bash
# On AWS, check Tailscale IP
tailscale ip -4
# Example: 100.a.b.c

# Test connectivity from Pi
ping 100.a.b.c  # Your AWS Tailscale IP
```

### Step 3: Get Gateway Token (On AWS)

The gateway auth token is in `~/.openclaw/openclaw.json`:

```bash
# On AWS gateway
cat ~/.openclaw/openclaw.json | grep -A2 '"auth"'
```

Look for:
```json
"auth": {
  "token": "your-gateway-token-here"
}
```

Or use the CLI:
```bash
openclaw config get gateway.auth.token
```

**Save this token — you'll need it on the Pi.**

### Step 4: Check Gateway Binding (On AWS)

The gateway must be accessible from Tailscale. Check the bind setting:

```bash
# On AWS
openclaw config get gateway.bind
```

- If `loopback` or `127.0.0.1`: Gateway only accepts local connections
- If `0.0.0.0` or your Tailscale IP: Gateway accepts remote connections

**To allow Tailscale connections:**
```bash
# Option 1: Bind to all interfaces
openclaw config set gateway.bind "0.0.0.0"
openclaw gateway restart

# Option 2: Bind to Tailscale IP specifically
openclaw config set gateway.bind "100.a.b.c"  # Your AWS Tailscale IP
openclaw gateway restart
```

### Step 5: Install OpenClaw on Pi

```bash
# Install Node.js 22
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs

# Install OpenClaw CLI
sudo npm install -g openclaw

# Verify
openclaw --version
```

### Step 6: Connect Node to Gateway (On Pi)

```bash
# Set the gateway token
export OPENCLAW_GATEWAY_TOKEN="your-gateway-token-here"

# Connect to gateway via Tailscale IP
openclaw node run \
  --host 100.a.b.c \
  --port 18789 \
  --display-name "mira"
```

You should see:
```
[Node] Connecting to ws://100.a.b.c:18789...
[Node] Connected!
[Node] Awaiting pairing approval...
```

### Step 7: Approve the Node (On AWS)

```bash
# List pending pairing requests
openclaw nodes pending

# Approve
openclaw nodes approve <requestId>

# Verify
openclaw nodes status
```

You should see `mira` listed as paired.

### Step 8: Test the Connection

From AWS gateway:
```bash
# Run a command on the Pi
openclaw nodes run --node mira -- uname -a
# Should return: Linux raspberrypi 6.x.x-v8+ aarch64 GNU/Linux

openclaw nodes run --node mira -- hostname
# Should return: raspberrypi (or your hostname)
```

---

## Option B: Without Tailscale (SSH Tunnel)

If you're not using Tailscale, you need an SSH tunnel.

### Step 1: Create SSH Tunnel (On Pi)

```bash
# Forward local port 18790 to gateway's localhost:18789
ssh -N -L 18790:127.0.0.1:18789 user@your-aws-public-ip
```

Keep this terminal open.

### Step 2: Connect Node Through Tunnel

In another terminal on Pi:
```bash
export OPENCLAW_GATEWAY_TOKEN="your-gateway-token-here"
openclaw node run \
  --host 127.0.0.1 \
  --port 18790 \
  --display-name "mira"
```

Then approve on AWS (same as Option A, Step 7).

---

## Option C: Direct Public IP (Not Recommended)

If your AWS gateway has a public IP and port 18789 is open:

```bash
export OPENCLAW_GATEWAY_TOKEN="your-gateway-token-here"
openclaw node run \
  --host your-aws-public-ip \
  --port 18789 \
  --display-name "mira"
```

⚠️ **Security warning:** This exposes your gateway to the internet. Use Tailscale instead.

---

## Install as Systemd Service

Once connection works, install as a service for auto-start:

### Step 1: Create Environment File

```bash
sudo mkdir -p /etc/openclaw
sudo nano /etc/openclaw/node.env
```

Add:
```
OPENCLAW_GATEWAY_TOKEN=your-gateway-token-here
```

Secure it:
```bash
sudo chmod 600 /etc/openclaw/node.env
```

### Step 2: Create Service File

```bash
sudo nano /etc/systemd/system/openclaw-node.service
```

```ini
[Unit]
Description=OpenClaw Node (Mira)
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=simple
User=pi
EnvironmentFile=/etc/openclaw/node.env
ExecStart=/usr/bin/openclaw node run --host 100.a.b.c --port 18789 --display-name "mira"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Replace `100.a.b.c` with your AWS Tailscale IP.**

### Step 3: Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable openclaw-node
sudo systemctl start openclaw-node

# Check status
sudo systemctl status openclaw-node

# View logs
journalctl -u openclaw-node -f
```

---

## Configure Exec Allowlist

By default, the node won't execute arbitrary commands. Add allowlist entries for Mira tools:

### On the Pi (Node Host)

Create or edit `~/.openclaw/exec-approvals.json`:

```json
{
  "mode": "allowlist",
  "allowlist": [
    "/usr/bin/candump",
    "/usr/bin/cansend",
    "/usr/bin/ip",
    "/home/pi/mira/mira",
    "/home/pi/mira/venv/bin/python"
  ]
}
```

### Or Via Gateway CLI

```bash
# On AWS gateway
openclaw approvals allowlist add --node mira "/usr/bin/candump"
openclaw approvals allowlist add --node mira "/usr/bin/cansend"
openclaw approvals allowlist add --node mira "/home/pi/mira/mira"
```

---

## Set Node as Default Exec Target

To make Claude automatically run commands on the Pi:

```bash
# On AWS gateway
openclaw config set tools.exec.host node
openclaw config set tools.exec.node "mira"
openclaw config set tools.exec.security allowlist
```

Now when Claude calls `exec`, it runs on the Pi.

---

## Verify Everything Works

### From Discord/Chat (via Claude)

Ask Claude:
> "Run `hostname` on mira"

Claude should execute and return the Pi's hostname.

### Test CAN (if HAT installed)

Ask Claude:
> "Run `ip link show can0` on mira"

---

## Troubleshooting

### "Connection refused"
- Check gateway is running: `systemctl status openclaw` (on AWS)
- Check bind setting: `openclaw config get gateway.bind`
- Check firewall: `sudo ufw status` (on AWS)
- Check Tailscale: `tailscale status`

### "Invalid token"
- Verify token matches: `openclaw config get gateway.auth.token` (on AWS)
- Check for typos or extra whitespace

### Node connects but commands fail
- Check exec approvals: `cat ~/.openclaw/exec-approvals.json` (on Pi)
- Check command is in allowlist
- Check command exists: `which candump`

### Node disconnects frequently
- Check network stability
- Check for IP changes (Tailscale IPs are stable)
- View logs: `journalctl -u openclaw-node -f`

---

## Summary

| Step | Command |
|------|---------|
| Get token (AWS) | `openclaw config get gateway.auth.token` |
| Install CLI (Pi) | `sudo npm install -g openclaw` |
| Connect (Pi) | `openclaw node run --host <IP> --port 18789` |
| Approve (AWS) | `openclaw nodes approve <id>` |
| Test (AWS) | `openclaw nodes run --node mira -- hostname` |
| Install service (Pi) | See systemd section above |

---

## Next Steps

Once node is connected:
1. Follow `PI_SETUP.md` for voice components
2. Test CAN HAT
3. Set up presence detection
4. Build voice pipeline
