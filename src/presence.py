#!/usr/bin/env python3
"""
presence.py - Owner presence detection via Bluetooth scan

Detects owner's phone without connecting - just passive scanning.
Used to switch between Owner Mode (full access) and Guest Mode (restricted).
"""

import subprocess
import time
import logging
from enum import Enum
from typing import Callable, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AccessMode(Enum):
    OWNER = "owner"
    GUEST = "guest"


# Configuration - set your device MAC addresses or names
OWNER_DEVICES_MAC = [
    # "AA:BB:CC:DD:EE:FF",  # iPhone
    # "11:22:33:44:55:66",  # Android
]

OWNER_DEVICES_NAME = [
    # "Alfred's iPhone",
    # "Pixel 7",
]

# Scan settings
SCAN_DURATION = 10  # seconds to scan
SCAN_INTERVAL = 30  # seconds between scans
GRACE_PERIOD = 60   # seconds before downgrading to guest (in case of brief signal loss)


# Queries blocked in guest mode
GUEST_BLOCKED_KEYWORDS = [
    "calendar",
    "schedule",
    "meeting",
    "appointment",
    "message",
    "email",
    "text",
    "reminder",
    "todo",
    "contact",
    "call",
    "personal",
    "private",
    "secret",
    "password",
    "account",
    "bank",
    "money",
    "pay",
]


def scan_bluetooth_devices() -> dict[str, str]:
    """
    Scan for nearby Bluetooth devices.
    Returns dict of {MAC: Name}
    """
    devices = {}
    
    try:
        # Start scan
        subprocess.run(
            ["bluetoothctl", "scan", "on"],
            timeout=2,
            capture_output=True,
            check=False
        )
        
        # Wait for devices to be discovered
        time.sleep(SCAN_DURATION)
        
        # Stop scan
        subprocess.run(
            ["bluetoothctl", "scan", "off"],
            timeout=2,
            capture_output=True,
            check=False
        )
        
        # Get discovered devices
        result = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Parse output: "Device AA:BB:CC:DD:EE:FF DeviceName"
        for line in result.stdout.strip().split('\n'):
            if line.startswith('Device '):
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    mac = parts[1].upper()
                    name = parts[2] if len(parts) > 2 else ""
                    devices[mac] = name
                elif len(parts) == 2:
                    devices[parts[1].upper()] = ""
        
        logger.debug(f"Found {len(devices)} devices: {list(devices.keys())}")
        
    except subprocess.TimeoutExpired:
        logger.warning("Bluetooth scan timed out")
    except Exception as e:
        logger.error(f"Bluetooth scan error: {e}")
    
    return devices


def is_owner_present() -> Tuple[bool, Optional[str]]:
    """
    Check if any owner device is nearby.
    Returns (is_present, device_identifier)
    """
    devices = scan_bluetooth_devices()
    
    # Check by MAC address
    for mac in OWNER_DEVICES_MAC:
        if mac.upper() in devices:
            logger.info(f"Owner detected by MAC: {mac}")
            return True, mac
    
    # Check by device name
    for owner_name in OWNER_DEVICES_NAME:
        for mac, device_name in devices.items():
            if owner_name.lower() in device_name.lower():
                logger.info(f"Owner detected by name: {device_name}")
                return True, device_name
    
    return False, None


def is_query_allowed_guest(query: str) -> bool:
    """Check if a query is allowed in guest mode."""
    query_lower = query.lower()
    
    for keyword in GUEST_BLOCKED_KEYWORDS:
        if keyword in query_lower:
            return False
    
    return True


def get_guest_rejection_message() -> str:
    """Message shown when guest tries to access restricted features."""
    return (
        "Personal features are currently locked. "
        "I can help with car controls and general questions. "
        "Owner verification required for personal data."
    )


class PresenceMonitor:
    """Monitors owner presence and manages access mode."""
    
    def __init__(
        self,
        on_mode_change: Optional[Callable[[AccessMode, Optional[str]], None]] = None
    ):
        self.current_mode = AccessMode.GUEST
        self.on_mode_change = on_mode_change
        self.last_owner_seen = 0
        self._running = False
    
    def get_mode(self) -> AccessMode:
        return self.current_mode
    
    def is_owner_mode(self) -> bool:
        return self.current_mode == AccessMode.OWNER
    
    def check_once(self) -> AccessMode:
        """Do a single presence check and update mode."""
        present, device = is_owner_present()
        
        if present:
            self.last_owner_seen = time.time()
            if self.current_mode != AccessMode.OWNER:
                self._set_mode(AccessMode.OWNER, device)
        else:
            # Grace period before downgrading
            time_since_seen = time.time() - self.last_owner_seen
            if self.current_mode == AccessMode.OWNER and time_since_seen > GRACE_PERIOD:
                self._set_mode(AccessMode.GUEST, None)
        
        return self.current_mode
    
    def _set_mode(self, mode: AccessMode, device: Optional[str]):
        """Update mode and notify callback."""
        old_mode = self.current_mode
        self.current_mode = mode
        
        if old_mode != mode:
            logger.info(f"Access mode changed: {old_mode.value} → {mode.value}")
            if self.on_mode_change:
                self.on_mode_change(mode, device)
    
    def start_monitoring(self):
        """Start continuous presence monitoring loop."""
        self._running = True
        logger.info("Starting presence monitoring...")
        
        # Initial check
        self.check_once()
        
        while self._running:
            time.sleep(SCAN_INTERVAL)
            self.check_once()
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False


# Example usage
if __name__ == "__main__":
    def on_mode_change(mode: AccessMode, device: Optional[str]):
        if mode == AccessMode.OWNER:
            print(f"✅ OWNER MODE - Welcome back! (Device: {device})")
            print("   Full access enabled.")
        else:
            print("🔒 GUEST MODE - Owner not detected")
            print("   Personal features locked.")
    
    monitor = PresenceMonitor(on_mode_change=on_mode_change)
    
    print("=" * 50)
    print("Mira Presence Detection")
    print("=" * 50)
    print()
    print("Configure your device in OWNER_DEVICES_MAC or OWNER_DEVICES_NAME")
    print("Scanning for Bluetooth devices...")
    print()
    
    try:
        monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\nStopping...")
        monitor.stop_monitoring()
