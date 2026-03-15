# Gateway Setup for Mira

Mira runs as a **separate agent** on your existing OpenClaw gateway, with the Pi as a **node** providing local capabilities (voice, CAN bus).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Gateway (Docker)                      │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   Wintermute Agent  │  │     Mira Agent          │   │
│  │   (main workspace)  │  │   (mira-workspace)      │   │
│  │                     │  │                             │   │
│  │   SOUL.md           │  │   SOUL.md (car personality) │   │
│  │   MEMORY.md         │  │   MEMORY.md (drive history) │   │
│  │   Discord/etc       │  │   Voice from car node       │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
│                                    ▲                         │
│                                    │ WebSocket (Tailscale)   │
└────────────────────────────────────┼─────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │    Pi 5 Node        │
                          │    (in car)         │
                          │                     │
                          │  - Microphone/TTS   │
                          │  - CAN bus tools    │
                          │  - Local fallback   │
                          └─────────────────────┘
```

---

## Prerequisites

- AWS instance (or any Linux server) running Docker
- Tailscale installed on both gateway and Pi nodes
- Domain or stable IP for Discord/webhook callbacks

---

## Step 1: Tailscale on Gateway

Install Tailscale for secure node connectivity:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Get your Tailscale IP (nodes will connect to this)
tailscale ip -4
# Example: 100.112.61.98
```

---

## Step 2: Configure Gateway for Node Connections

Your `docker-compose.yml` should use `network_mode: host` to expose the gateway port on Tailscale:

```yaml
version: '3.8'
services:
  wintermute:
    image: ghcr.io/openclaw/openclaw:latest
    container_name: wintermute
    network_mode: host  # Required for Tailscale connectivity
    restart: unless-stopped
    volumes:
      - ${OPENCLAW_CONFIG_DIR:-~/.openclaw}:/home/node/.openclaw
      - ~/.ssh:/home/node/.ssh:ro
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      # Add other API keys as needed
```

---

## Step 3: Generate Gateway Auth Token

Create a shared token for node authentication:

```bash
# Generate a secure random token
openssl rand -hex 16
# Example output: 69d05e0c49fa731be1ebcb8ed9812305
```

Add to your gateway config (`~/.openclaw/openclaw.json`):

```json
{
  "gateway": {
    "bind": "tailnet",
    "port": 18789,
    "auth": {
      "token": "69d05e0c49fa731be1ebcb8ed9812305"
    },
    "remote": {
      "token": "69d05e0c49fa731be1ebcb8ed9812305"
    }
  }
}
```

**Important:** Both `auth.token` and `remote.token` must match. The `remote.token` is used by CLI commands; if it's missing, CLI commands will fail with "gateway token mismatch".

Restart the gateway:
```bash
docker compose down && docker compose up -d
```

---

## Step 4: Create Mira Workspace

```bash
# On the gateway HOST (not inside container)
mkdir -p ~/.openclaw/mira-workspace

# Clone repo and copy template files
git clone https://github.com/idorurez/mira.git /tmp/mira
cp /tmp/mira/workspace-template/* ~/.openclaw/mira-workspace/

# Fix permissions (container runs as uid 1000)
sudo chown -R 1000:1000 ~/.openclaw/mira-workspace/

# Verify
ls ~/.openclaw/mira-workspace/
# Should show: AGENTS.md  HEARTBEAT.md  IDENTITY.md  MEMORY.md  SOUL.md  USER.md
```

---

## Step 5: Register Mira Agent

```bash
# Inside container
docker exec -w /app wintermute node dist/index.js agents add mira \
  --workspace /home/node/.openclaw/mira-workspace
```

Verify:
```bash
docker exec -w /app wintermute node dist/index.js agents list
# Should show: main (default), mira
```

---

## Step 6: Install Mira Skill (Optional)

```bash
cp -r /tmp/mira/skills/car-control ~/.openclaw/skills/
rm -rf /tmp/mira
```

---

## Device Files

OpenClaw stores device pairing state in:

```
~/.openclaw/devices/
├── pending.json   # Unapproved pairing requests
└── paired.json    # Approved devices with tokens
```

These are JSON objects keyed by `deviceId`:

**pending.json:**
```json
{
  "request-uuid": {
    "requestId": "request-uuid",
    "deviceId": "sha256-hash-of-public-key",
    "publicKey": "base64-ed25519-public-key",
    "displayName": "mira",
    "role": "node",
    ...
  }
}
```

**paired.json:**
```json
{
  "sha256-hash-of-public-key": {
    "deviceId": "sha256-hash-of-public-key",
    "publicKey": "base64-ed25519-public-key",
    "displayName": "mira",
    ...
    "tokens": {
      "node": {
        "token": "session-token-issued-by-gateway",
        "createdAtMs": 1773028911447
      }
    }
  }
}
```

---

## Approving Node Pairing

### Option A: CLI (If Working)

```bash
# List pending requests
docker exec -w /app wintermute node dist/index.js devices pending

# Approve by request ID
docker exec -w /app wintermute node dist/index.js devices approve REQUEST_ID
```

### Option B: Manual (If CLI Has Auth Issues)

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#manual-device-approval) for manual approval steps.

---

## Verifying Node Connection

```bash
# Check paired devices have tokens
docker exec wintermute cat /home/node/.openclaw/devices/paired.json

# Look for recent connections from Pi IP
docker logs wintermute --tail 100 | grep "100.76.12.120"
```

**Note:** The gateway doesn't log successful node connections — only failures. The absence of errors is good news.

---

## What's Persistent (Docker)

| Item | Location on Host | Survives Compose |
|------|------------------|------------------|
| Agent config | `~/.openclaw/openclaw.json` | ✅ Yes |
| Mira workspace | `~/.openclaw/mira-workspace/` | ✅ Yes |
| Mira memories | `~/.openclaw/mira-workspace/MEMORY.md` | ✅ Yes |
| Skills | `~/.openclaw/skills/` | ✅ Yes |
| Device pairing | `~/.openclaw/devices/` | ✅ Yes |
| Gateway identity | `~/.openclaw/identity/` | ✅ Yes |

**No changes to `docker-compose.yml` needed** — everything is under the already-mounted `${OPENCLAW_CONFIG_DIR}`.

---

## Separate Contexts

| Aspect | Wintermute | Mira |
|--------|------------|----------|
| Workspace | `~/.openclaw/workspace/` | `~/.openclaw/mira-workspace/` |
| Personality | Your main assistant | Car spirit |
| Memory | Discord, projects, life | Drives, car stuff |
| Channels | Discord, Signal, etc. | Voice from car node |
| Tools | All | Car-specific + basics |

They share the same gateway infrastructure but are completely isolated in personality, memory, and context.

---

## Troubleshooting

### CLI "gateway token mismatch" Error

The CLI can't authenticate. Ensure both `gateway.auth.token` and `gateway.remote.token` are set and match in `openclaw.json`.

### Control UI "requires device identity"

Browser access requires HTTPS or localhost. Options:
- SSH tunnel: `ssh -L 18789:localhost:18789 user@gateway`
- Tailscale Serve (for HTTPS)
- Access from gateway machine directly

### Node Won't Pair

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for detailed pairing issues.

---

*Next: Set up the Pi node — see [PI_SETUP.md](./PI_SETUP.md)*
