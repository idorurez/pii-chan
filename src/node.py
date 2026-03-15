#!/usr/bin/env python3
"""
OpenClaw Node — WebSocket client for the gateway.

Connects to the OpenClaw gateway as a paired node, sends voice
transcripts, and streams Claude's responses back for TTS.
"""

import asyncio
import base64
import json
import time
import uuid
from pathlib import Path
from typing import Optional, Callable

import websockets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    Encoding,
    PublicFormat,
)


class OpenClawNode:
    """WebSocket client that connects to the OpenClaw gateway as a node."""

    def __init__(
        self,
        config_dir: str = "~/.openclaw",
        on_response: Optional[Callable[[str], None]] = None,
    ):
        self.config_dir = Path(config_dir).expanduser()
        self.on_response = on_response

        # Loaded from config files
        self._node_id: Optional[str] = None
        self._display_name: Optional[str] = None
        self._gateway_host: Optional[str] = None
        self._gateway_port: int = 18789
        self._gateway_tls: bool = False
        self._device_id: Optional[str] = None
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key_pem: Optional[str] = None
        self._device_token: Optional[str] = None
        self._gateway_token: Optional[str] = None

        self._ws = None
        self._connected = False
        self._req_counter = 0
        self._pending: dict[str, asyncio.Future] = {}

    # ---- Config loading ----

    def load_config(self):
        """Load node config, device identity, and auth from ~/.openclaw."""
        node_json = self.config_dir / "node.json"
        device_json = self.config_dir / "identity" / "device.json"
        auth_json = self.config_dir / "identity" / "device-auth.json"

        if not node_json.exists():
            raise FileNotFoundError(f"Node config not found: {node_json}")
        if not device_json.exists():
            raise FileNotFoundError(f"Device identity not found: {device_json}")
        if not auth_json.exists():
            raise FileNotFoundError(f"Device auth not found: {auth_json}")

        # Node config
        node = json.loads(node_json.read_text())
        self._node_id = node["nodeId"]
        self._display_name = node.get("displayName", "mira")
        gw = node.get("gateway", {})
        self._gateway_host = gw.get("host", "100.112.61.98")
        self._gateway_port = gw.get("port", 18789)
        self._gateway_tls = gw.get("tls", False)

        # Device identity (Ed25519 keypair)
        device = json.loads(device_json.read_text())
        self._device_id = device["deviceId"]
        self._public_key_pem = device["publicKeyPem"]
        pem_bytes = device["privateKeyPem"].encode()
        self._private_key = load_pem_private_key(pem_bytes, password=None)

        # Auth token
        auth = json.loads(auth_json.read_text())
        tokens = auth.get("tokens", {})
        node_token = tokens.get("node", {})
        self._device_token = node_token.get("token")

        # Gateway shared token (optional, from env or openclaw.json)
        oc_json = self.config_dir / "openclaw.json"
        if oc_json.exists():
            oc = json.loads(oc_json.read_text())
            self._gateway_token = oc.get("gateway", {}).get("auth", {}).get("token")

        print(f"[node] Config loaded: {self._display_name} → "
              f"{self._gateway_host}:{self._gateway_port}")

    # ---- Ed25519 challenge signing ----

    def _sign_challenge(self, nonce: str) -> tuple[str, int]:
        """Sign the gateway challenge nonce. Returns (signature_b64, signed_at_ms)."""
        signed_at_ms = int(time.time() * 1000)
        # v2 pipe-delimited payload
        token_for_sig = self._gateway_token or self._device_token or ""
        payload = "|".join([
            "v2",
            self._device_id,
            "node-host",       # clientId
            "node",            # clientMode
            "node",            # role
            "",                # scopes (empty)
            str(signed_at_ms),
            token_for_sig,
            nonce,
        ])
        sig = self._private_key.sign(payload.encode())
        return base64.b64encode(sig).decode(), signed_at_ms

    # ---- WebSocket connection ----

    def _next_id(self) -> str:
        self._req_counter += 1
        return f"r{self._req_counter}"

    async def _send_req(self, method: str, params: dict) -> dict:
        """Send a request and wait for the response."""
        req_id = self._next_id()
        msg = {"type": "req", "id": req_id, "method": method, "params": params}

        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        await self._ws.send(json.dumps(msg))

        # Read messages until we get our response
        deadline = time.time() + 30
        while not fut.done():
            if time.time() > deadline:
                self._pending.pop(req_id, None)
                raise TimeoutError(f"No response for {method}")
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=5)
                msg_in = json.loads(raw)
                if msg_in.get("type") == "res":
                    rid = msg_in.get("id")
                    f = self._pending.pop(rid, None)
                    if f and not f.done():
                        f.set_result(msg_in)
                elif msg_in.get("type") == "event":
                    await self._handle_event(msg_in)
            except asyncio.TimeoutError:
                continue

        return fut.result()

    async def connect(self):
        """Connect to the gateway, authenticate, and start listening."""
        scheme = "wss" if self._gateway_tls else "ws"
        url = f"{scheme}://{self._gateway_host}:{self._gateway_port}"
        print(f"[node] Connecting to {url}...")

        self._ws = await websockets.connect(url, max_size=25 * 1024 * 1024)

        # Wait for challenge
        raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
        challenge = json.loads(raw)
        if challenge.get("event") != "connect.challenge":
            raise RuntimeError(f"Expected connect.challenge, got: {challenge}")

        nonce = challenge["payload"]["nonce"]
        print(f"[node] Challenge received, signing...")

        # Sign and send connect request
        sig_b64, signed_at = self._sign_challenge(nonce)

        auth = {}
        if self._gateway_token:
            auth["token"] = self._gateway_token
        if self._device_token:
            auth["deviceToken"] = self._device_token

        result = await self._send_req("connect", {
            "minProtocol": 3,
            "maxProtocol": 3,
            "client": {
                "id": "node-host",
                "version": "0.1.0",
                "platform": "linux",
                "mode": "node",
            },
            "role": "node",
            "scopes": [],
            "auth": auth,
            "device": {
                "id": self._device_id,
                "publicKey": self._public_key_pem,
                "signature": sig_b64,
                "signedAt": signed_at,
                "nonce": nonce,
            },
        })

        if not result.get("ok"):
            raise RuntimeError(f"Connect failed: {result.get('error')}")

        self._connected = True
        print(f"[node] Connected to gateway!")

    async def _recv_loop(self):
        """Process incoming messages from the gateway."""
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "res":
                # Response to a request we sent
                req_id = msg.get("id")
                fut = self._pending.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(msg)

            elif msg_type == "event":
                await self._handle_event(msg)

    async def _handle_event(self, msg: dict):
        """Handle an event from the gateway."""
        event = msg.get("event", "")
        payload = msg.get("payload", {})

        if event == "agent":
            stream = payload.get("stream")
            data = payload.get("data", {})

            if stream == "assistant":
                # Streaming text delta from Claude
                delta = data.get("delta", "")
                if delta:
                    pass  # Could show streaming progress here

            elif stream == "lifecycle":
                phase = data.get("phase")
                if phase == "end":
                    # Agent run complete — we'll get the final text from chat event
                    pass

        elif event == "chat":
            state = payload.get("state")
            if state == "final":
                # Final complete response
                message = payload.get("message", {})
                text = ""
                for block in message.get("content", []):
                    if block.get("type") == "text":
                        text += block.get("text", "")
                if text and self.on_response:
                    self.on_response(text)

    # ---- Public API ----

    async def send_voice_transcript(self, text: str, agent: str = "agent:mira:main"):
        """Send a voice transcript to the gateway for Claude to respond to.

        The sessionKey determines which agent handles the message.
        Format: agent:<agent-id>:<session-scope>
        """
        if not self._connected:
            print("[node] Not connected to gateway")
            return

        req_id = self._next_id()
        msg = {
            "type": "req",
            "id": req_id,
            "method": "node.event",
            "params": {
                "event": "voice.transcript",
                "payload": {
                    "text": text,
                    "sessionKey": agent,
                },
            },
        }
        await self._ws.send(json.dumps(msg))
        # Response will be picked up by _recv_loop

    async def run(self):
        """Connect and run the receive loop. Reconnects on failure."""
        while True:
            try:
                await self.connect()
                await self._recv_loop()
            except (websockets.ConnectionClosed, ConnectionError) as e:
                print(f"[node] Disconnected: {e}")
                self._connected = False
                print("[node] Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[node] Error: {e}")
                self._connected = False
                await asyncio.sleep(5)

    @property
    def connected(self) -> bool:
        return self._connected

    async def disconnect(self):
        """Close the WebSocket connection."""
        self._connected = False
        if self._ws:
            await self._ws.close()


async def main():
    """Quick test: connect, send a message, print response."""
    response_text = None
    response_event = asyncio.Event()

    def on_response(text):
        nonlocal response_text
        response_text = text
        print(f"\n[Claude] {text}")
        response_event.set()

    node = OpenClawNode(on_response=on_response)
    node.load_config()
    await node.connect()

    # Start receive loop in background
    recv_task = asyncio.create_task(node.run())

    # Send a test message
    print("\nSending test message...")
    await node.send_voice_transcript("Hello, what is your name?")

    # Wait for response
    try:
        await asyncio.wait_for(response_event.wait(), timeout=30)
    except asyncio.TimeoutError:
        print("[node] Timed out waiting for response")

    await node.disconnect()
    recv_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
