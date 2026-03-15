# Reconnection & Resilience

How to ensure Mira stays connected through network issues, reboots, and gateway restarts.

---

## Built-in Resilience

### Systemd Auto-Restart

The service file includes:
```ini
Restart=always
RestartSec=10
```

This means:
- If the process exits for ANY reason, systemd waits 10 seconds then restarts it
- Includes crashes, network errors, gateway disconnects
- No manual intervention needed

### OpenClaw Node Reconnection

The `openclaw node run` command has built-in reconnection:
- WebSocket disconnects trigger automatic reconnect attempts
- Exponential backoff prevents hammering the gateway
- Token-based auth means no re-pairing needed after initial approval

---

## Scenario Testing

### Gateway Restarts

**What happens:**
1. Gateway container stops
2. Node WebSocket closes (1012: service restart)
3. Node starts reconnect loop
4. Gateway comes back up
5. Node reconnects, authenticates with existing token
6. Connection restored

**Verify:**
```bash
# On gateway
docker compose restart wintermute

# On Pi - watch the logs
sudo journalctl -u mira -f
# Should see: disconnect, then reconnect after gateway is up
```

### Pi Reboots

**What happens:**
1. Pi reboots
2. systemd starts mira.service
3. Node reads identity from `~/.openclaw/identity/device.json`
4. Connects to gateway with same deviceId
5. Gateway recognizes device, issues new session token
6. Connection established

**Verify:**
```bash
# On Pi
sudo reboot

# Wait 2-3 minutes, then SSH back in
sudo systemctl status mira
ss -tnp | grep 18789
```

### Network Outage

**What happens:**
1. WiFi/network drops
2. WebSocket connection times out
3. Node enters reconnect loop (with backoff)
4. Network recovers
5. Next reconnect attempt succeeds
6. Connection restored

**The service handles this automatically.**

### Tailscale Reconnects

**What happens:**
1. Tailscale connection drops (e.g., laptop sleep, network change)
2. WebSocket fails (can't reach gateway IP)
3. Node reconnects when Tailscale recovers
4. May take a few minutes depending on Tailscale's reconnection

---

## Monitoring

### Check Connection Status

```bash
# Quick check - is TCP connection up?
ss -tnp | grep 18789

# Process running?
systemctl is-active mira

# Recent activity
sudo journalctl -u mira --since "10 minutes ago"
```

### Alerting (Optional)

Create a simple health check script:

```bash
#!/bin/bash
# /home/mira/check_connection.sh

if ! ss -tnp | grep -q 18789; then
    echo "Mira disconnected at $(date)" >> /var/log/mira-health.log
    # Optional: send notification
    # curl -X POST "https://your-webhook" -d "Mira disconnected"
fi
```

Add to crontab:
```bash
crontab -e
# Add: */5 * * * * /home/mira/check_connection.sh
```

---

## Recovery Procedures

### Service Won't Start

```bash
# Check status
sudo systemctl status mira

# View recent logs
sudo journalctl -u mira --no-pager -n 100

# Restart
sudo systemctl restart mira
```

### Identity Issues After Update

If OpenClaw was updated and identity format changed:

```bash
# Backup current identity
cp -r ~/.openclaw/identity ~/.openclaw/identity.bak

# Let it regenerate (will need re-approval on gateway)
rm -rf ~/.openclaw/identity
sudo systemctl restart mira

# Approve new identity on gateway
```

### Gateway Token Changed

If someone changed the gateway token:

```bash
# Update the service file with new token
sudo nano /etc/systemd/system/mira.service
# Edit: Environment=OPENCLAW_GATEWAY_TOKEN=NEW_TOKEN_HERE

sudo systemctl daemon-reload
sudo systemctl restart mira
```

---

## Configuration Reference

### Service File (Complete)

```ini
[Unit]
Description=Mira OpenClaw Node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mira

# Tailscale transport is encrypted; allow non-TLS WebSocket
Environment=OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1

# Gateway authentication
Environment=OPENCLAW_GATEWAY_TOKEN=69d05e0c49fa731be1ebcb8ed9812305

# The command
ExecStart=/home/mira/.npm-global/bin/openclaw node run \
  --host 100.112.61.98 \
  --port 18789 \
  --display-name mira

# Auto-restart on any exit
Restart=always
RestartSec=10

# Limit restart attempts (optional - prevents infinite loop if misconfigured)
# StartLimitIntervalSec=300
# StartLimitBurst=5

[Install]
WantedBy=multi-user.target
```

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `OPENCLAW_ALLOW_INSECURE_PRIVATE_WS` | Allow non-TLS WebSocket over private IPs | Yes (with Tailscale) |
| `OPENCLAW_GATEWAY_TOKEN` | Shared secret for authentication | Yes |

---

## Best Practices

1. **Never delete `~/.openclaw/identity/`** — it's your permanent device ID
2. **Set `Restart=always`** — let systemd handle recovery
3. **Use `RestartSec=10`** — gives network time to recover
4. **Monitor with `ss -tnp`** — most reliable connection check
5. **Keep Tailscale updated** — `sudo tailscale update`
6. **Test failover regularly** — reboot both sides, verify recovery
