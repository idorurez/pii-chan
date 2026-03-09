# Troubleshooting Guide

Common issues and solutions for Pii-chan node setup.

---

## Table of Contents

- [Service Issues](#service-issues)
- [Pairing & Authentication](#pairing--authentication)
- [Connection Issues](#connection-issues)
- [Manual Device Approval](#manual-device-approval)
- [Gateway CLI Issues](#gateway-cli-issues)
- [Verification Commands](#verification-commands)

---

## Service Issues

### "Assignment outside of section" in journalctl

**Symptom:**
```
systemd[1]: /etc/systemd/system/piichan.service:1: Assignment outside of section. Ignoring.
```

**Cause:** The service file is missing section brackets.

**Wrong:**
```ini
Unit
Description=Pii-chan
```

**Correct:**
```ini
[Unit]
Description=Pii-chan
```

**Fix:**
```bash
# Recreate the service file with proper brackets
sudo tee /etc/systemd/system/piichan.service << 'EOF'
[Unit]
Description=Pii-chan OpenClaw Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=piichan
Environment=OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1
Environment=OPENCLAW_GATEWAY_TOKEN=YOUR_TOKEN
ExecStart=/home/piichan/.npm-global/bin/openclaw node run --host YOUR_GATEWAY_IP --port 18789 --display-name piichan
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart piichan
```

### Service Shows "node host PATH" Then Exits

**Symptom:** Service starts, prints "node host PATH: ..." and nothing else.

**Cause:** The service is running but logging is minimal. Check if it's actually connected.

**Verify:**
```bash
# Check if process is running
ps aux | grep openclaw

# Check for TCP connection
ss -tnp | grep 18789
```

If no TCP connection, the node is failing silently. Run manually to see errors:
```bash
sudo systemctl stop piichan
OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1 OPENCLAW_GATEWAY_TOKEN="your-token" \
  /home/piichan/.npm-global/bin/openclaw node run \
  --host YOUR_GATEWAY_IP --port 18789 --display-name piichan 2>&1
```

---

## Pairing & Authentication

### "pairing required" Error

**Symptom:** Node keeps reconnecting with "pairing required" errors.

**Cause:** The gateway doesn't recognize this device's identity.

**Fix:**
1. Check if there's a pending request on the gateway
2. Approve it (see [Manual Device Approval](#manual-device-approval))

### Device ID Mismatch

**Symptom:** Approved a device but node still fails with "pairing required".

**Cause:** The `deviceId` in the gateway's `paired.json` doesn't match the Pi's identity.

**Diagnose:**
```bash
# On Pi - get current deviceId
cat ~/.openclaw/identity/device.json | grep deviceId

# On Gateway - check what's approved
docker exec wintermute cat /home/node/.openclaw/devices/paired.json | grep deviceId
```

If they don't match, the Pi has a different identity than what you approved.

**Fix:** Either:
1. Re-approve the current Pi identity (see [Manual Device Approval](#manual-device-approval))
2. Or restore the Pi's old identity (if you have a backup)

### Identity Keeps Regenerating

**Symptom:** Every restart generates a new deviceId.

**Cause:** The `~/.openclaw/identity/` folder is being deleted or doesn't exist.

**Fix:**
```bash
# Check identity exists
ls -la ~/.openclaw/identity/

# If missing, let the node generate one, then NEVER delete it
# The identity folder must persist across restarts
```

---

## Connection Issues

### Can't Reach Gateway

**Symptom:** Node can't connect at all.

**Verify connectivity:**
```bash
# Test HTTP health endpoint
curl -v http://YOUR_GATEWAY_IP:18789/health
# Should return: {"ok":true,"status":"live"}
```

If this fails:
- Check Tailscale is connected: `tailscale status`
- Verify gateway is running: `docker ps | grep wintermute`
- Check gateway is bound to the right interface: `docker logs wintermute | grep bind`

### Connection Drops Frequently

**Symptom:** Node connects, works for a while, then disconnects.

**Common causes:**
- Network instability (WiFi issues)
- Gateway restarts (node will auto-reconnect)
- Token expiration (shouldn't happen normally)

**The node has built-in reconnection:**
```ini
[Service]
Restart=always
RestartSec=10
```

If the service is restarting too often, check:
```bash
sudo journalctl -u piichan --since "1 hour ago" | grep -i "error\|fail\|closed"
```

---

## Manual Device Approval

When the CLI has authentication issues, you can manually approve devices by editing the paired.json file.

### Step 1: Get the Pending Request

```bash
docker exec wintermute cat /home/node/.openclaw/devices/pending.json
```

Save the output — you'll need the `deviceId` and `publicKey`.

### Step 2: Create Paired Entry

```bash
# Create a new paired.json with the device
cat << 'EOF' > /tmp/paired_new.json
{
  "DEVICE_ID_HERE": {
    "deviceId": "DEVICE_ID_HERE",
    "publicKey": "PUBLIC_KEY_HERE",
    "displayName": "piichan",
    "platform": "linux",
    "clientId": "node-host",
    "clientMode": "node",
    "role": "node",
    "roles": ["node"],
    "remoteIp": "PI_TAILSCALE_IP",
    "createdAtMs": TIMESTAMP,
    "approvedAtMs": TIMESTAMP,
    "tokens": {}
  }
}
EOF
```

Replace:
- `DEVICE_ID_HERE` — from pending.json
- `PUBLIC_KEY_HERE` — from pending.json
- `PI_TAILSCALE_IP` — Pi's Tailscale IP (e.g., "100.76.12.120")
- `TIMESTAMP` — current Unix timestamp in milliseconds (`date +%s000`)

### Step 3: Copy to Container

```bash
docker cp /tmp/paired_new.json wintermute:/home/node/.openclaw/devices/paired.json

# Clear pending
echo '{}' > /tmp/empty.json
docker cp /tmp/empty.json wintermute:/home/node/.openclaw/devices/pending.json
```

### Step 4: Restart Node

```bash
# On Pi
sudo systemctl restart piichan
```

The gateway will issue a token on the next successful connection.

---

## Gateway CLI Issues

### "gateway token mismatch" Error

**Symptom:**
```
unauthorized: gateway token mismatch (provide gateway auth token)
```

**Cause:** Token mismatch between different sources. The gateway can get its token from:
1. `.env` file (`OPENCLAW_GATEWAY_TOKEN=...`)
2. `openclaw.json` (`gateway.auth.token`)
3. Environment variable passed to container

If these don't match, CLI commands fail.

**Diagnose:**

```bash
# Check what's in .env
cat ~/openclaw/.env | grep GATEWAY_TOKEN

# Check what's in config
docker exec wintermute cat /home/node/.openclaw/openclaw.json | grep -A3 '"auth"'

# Check what the container actually has
docker exec wintermute env | grep GATEWAY_TOKEN
```

**Fix:** Make them all match:

```bash
# Update .env to match your chosen token
sed -i 's/OPENCLAW_GATEWAY_TOKEN=.*/OPENCLAW_GATEWAY_TOKEN=YOUR_TOKEN_HERE/' ~/openclaw/.env

# IMPORTANT: Must recreate container, not just restart
cd ~/openclaw && docker compose down && docker compose up -d

# Verify
docker exec wintermute env | grep GATEWAY_TOKEN
docker exec -w /app wintermute node dist/index.js nodes status
```

**Note:** `docker compose restart` does NOT reload .env changes. You must `down && up`.
```

### "Control UI requires device identity"

**Symptom:** Browser access to gateway shows this error.

**Cause:** Control UI requires HTTPS or localhost for security.

**Fix:** Set up Tailscale Serve (permanent HTTPS):

```bash
# On gateway
sudo tailscale serve --bg --https=443 http://localhost:18789

# Access via HTTPS URL
tailscale status | head -1  # shows your hostname
# URL: https://YOUR-HOSTNAME.tail<id>.ts.net/
```

### "origin not allowed"

**Symptom:** HTTPS access works but WebSocket fails with origin error.

**Cause:** Your access URL isn't in `gateway.controlUi.allowedOrigins`.

**Fix:**
```bash
# Check current origins
docker exec wintermute cat /home/node/.openclaw/openclaw.json | grep -A10 "allowedOrigins"

# Add your Tailscale hostname (with https://)
# Edit ~/.openclaw/openclaw.json on host, add to allowedOrigins array:
# "https://YOUR-HOSTNAME.tail<id>.ts.net"

# Restart
cd ~/openclaw && docker compose down && docker compose up -d
```

### "gateway token missing"

**Symptom:** Control UI loads but won't connect.

**Fix:** Enter the gateway token in the Control UI settings, or append to URL:
```
https://YOUR-HOSTNAME.tail<id>.ts.net/?token=YOUR_GATEWAY_TOKEN
```

Then approve the browser device:
```bash
docker exec wintermute openclaw devices list
docker exec wintermute openclaw devices approve <requestId>
```

---

## Verification Commands

### On Pi

```bash
# Service status
sudo systemctl status piichan

# Recent logs
sudo journalctl -u piichan --no-pager -n 50

# Live log tail
sudo journalctl -u piichan -f

# Process check
ps aux | grep openclaw

# TCP connection
ss -tnp | grep 18789

# Identity info
cat ~/.openclaw/identity/device.json | head -5

# Node config
cat ~/.openclaw/node.json
```

### On Gateway

```bash
# Container running
docker ps | grep wintermute

# Recent logs
docker logs wintermute --tail 50

# Live log tail
docker logs -f wintermute

# Pending devices
docker exec wintermute cat /home/node/.openclaw/devices/pending.json

# Paired devices
docker exec wintermute cat /home/node/.openclaw/devices/paired.json

# Gateway config
docker exec wintermute cat /home/node/.openclaw/openclaw.json | head -30

# Check for Pi connections (replace IP)
docker logs wintermute --tail 100 | grep "100.76.12.120"
```

### Connectivity Test

```bash
# From Pi - test gateway is reachable
curl -v http://GATEWAY_TAILSCALE_IP:18789/health

# Expected response:
# {"ok":true,"status":"live"}
```

---

## Understanding the Token Flow

```
1. Node generates identity (once, on first run)
   └── ~/.openclaw/identity/device.json (deviceId, publicKey, privateKey)

2. Node connects to gateway with identity
   └── Gateway checks if deviceId is in paired.json

3. If not paired:
   └── Gateway creates pending request
   └── Node waits for approval

4. Admin approves (CLI or manual)
   └── Moves device from pending.json to paired.json

5. Node reconnects
   └── Gateway recognizes deviceId
   └── Gateway issues session token
   └── Token stored in paired.json under "tokens"

6. Node is connected!
   └── WebSocket stays open
   └── Node can receive commands from gateway
```

**Key insight:** The gateway doesn't log successful node connections — only failures. Use `ss -tnp | grep 18789` on the Pi to verify connection state.

---

## Emergency Recovery

### Reset Pi Identity (Last Resort)

If everything is broken and you need to start fresh:

```bash
# On Pi
sudo systemctl stop piichan
rm -rf ~/.openclaw/identity/
rm -f ~/.openclaw/node.json
sudo systemctl start piichan

# Then re-approve on gateway
```

### Reset Gateway Device State (Nuclear Option)

```bash
# Clear all paired devices
echo '{}' > /tmp/empty.json
docker cp /tmp/empty.json wintermute:/home/node/.openclaw/devices/paired.json
docker cp /tmp/empty.json wintermute:/home/node/.openclaw/devices/pending.json

# All nodes will need to re-pair
```
