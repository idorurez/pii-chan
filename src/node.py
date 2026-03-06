#!/usr/bin/env python3
"""
OpenClaw Node Integration for Pii-chan

This module handles the connection between the Pi and OpenClaw gateway,
exposing CAN bus operations as tools that Claude can invoke.
"""

import json
import asyncio
from dataclasses import dataclass, asdict
from typing import Optional, Callable, Any
from enum import Enum

# TODO: Import actual OpenClaw node SDK when available
# from openclaw import Node, Tool


@dataclass
class CarState:
    """Current vehicle state - exposed to Claude as context."""
    engine_running: bool = False
    speed_kmh: float = 0.0
    gear: str = "P"
    battery_soc: float = 100.0
    fuel_level: float = 100.0
    
    # Climate
    climate_temp_driver: float = 72.0
    climate_temp_passenger: float = 72.0
    climate_temp_rear: float = 72.0
    climate_fan_speed: int = 0
    climate_mode: str = "auto"  # auto, face, feet, both, defrost
    climate_sync: bool = True
    
    # Doors/lights
    any_door_open: bool = False
    headlights_on: bool = False
    
    def to_context(self) -> str:
        """Format state as context for Claude."""
        lines = [
            "## Current Vehicle State",
            f"- Engine: {'Running' if self.engine_running else 'Off'}",
            f"- Speed: {self.speed_kmh:.0f} km/h",
            f"- Gear: {self.gear}",
            f"- Battery: {self.battery_soc:.0f}%",
            f"- Fuel: {self.fuel_level:.0f}%",
            "",
            "### Climate",
            f"- Driver zone: {self.climate_temp_driver}°F, {self.climate_mode}",
            f"- Passenger zone: {self.climate_temp_passenger}°F",
            f"- Rear zone: {self.climate_temp_rear}°F", 
            f"- Fan: {self.climate_fan_speed}",
            f"- Sync: {'On' if self.climate_sync else 'Off'}",
        ]
        return "\n".join(lines)


class PiiChanNode:
    """
    OpenClaw node that runs in the car.
    
    Exposes CAN bus operations as tools and provides vehicle context
    to Claude for natural conversation.
    """
    
    def __init__(self, can_interface=None):
        self.can = can_interface
        self.state = CarState()
        self._connected = False
        
    async def connect(self, gateway_url: str, node_token: str):
        """Connect to OpenClaw gateway as a node."""
        # TODO: Implement actual OpenClaw node registration
        # This will use the openclaw SDK when available
        print(f"[Node] Connecting to {gateway_url}...")
        self._connected = True
        print("[Node] Connected!")
        
    def get_tools(self) -> list[dict]:
        """Return tool definitions for OpenClaw."""
        return [
            {
                "name": "car_state",
                "description": "Get current vehicle state (speed, gear, climate, etc.)",
                "parameters": {}
            },
            {
                "name": "climate_set",
                "description": "Set climate control. Can control temperature, fan, mode, and sync.",
                "parameters": {
                    "zone": {
                        "type": "string",
                        "enum": ["driver", "passenger", "rear", "all"],
                        "description": "Which zone to control"
                    },
                    "temp": {
                        "type": "number",
                        "description": "Temperature in Fahrenheit (60-85)"
                    },
                    "fan": {
                        "type": "integer",
                        "description": "Fan speed (0-7, 0=auto)"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "face", "feet", "both", "defrost"],
                        "description": "Airflow mode"
                    },
                    "sync": {
                        "type": "boolean",
                        "description": "Sync all zones to driver settings"
                    }
                }
            },
            {
                "name": "climate_off",
                "description": "Turn off climate control completely"
            }
        ]
    
    async def handle_tool_call(self, tool_name: str, params: dict) -> dict:
        """Handle tool invocation from Claude."""
        
        if tool_name == "car_state":
            return {
                "success": True,
                "state": asdict(self.state)
            }
            
        elif tool_name == "climate_set":
            return await self._set_climate(params)
            
        elif tool_name == "climate_off":
            return await self._climate_off()
            
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    async def _set_climate(self, params: dict) -> dict:
        """Set climate control via CAN bus."""
        zone = params.get("zone", "driver")
        
        # Update local state
        if "temp" in params:
            temp = params["temp"]
            if zone in ["driver", "all"]:
                self.state.climate_temp_driver = temp
            if zone in ["passenger", "all"]:
                self.state.climate_temp_passenger = temp
            if zone in ["rear", "all"]:
                self.state.climate_temp_rear = temp
                
        if "fan" in params:
            self.state.climate_fan_speed = params["fan"]
            
        if "mode" in params:
            self.state.climate_mode = params["mode"]
            
        if "sync" in params:
            self.state.climate_sync = params["sync"]
            if params["sync"]:
                # When syncing, copy driver to all zones
                self.state.climate_temp_passenger = self.state.climate_temp_driver
                self.state.climate_temp_rear = self.state.climate_temp_driver
        
        # TODO: Actually write to CAN bus
        # await self.can.write_climate(...)
        
        return {
            "success": True,
            "message": f"Climate updated for {zone} zone",
            "new_state": {
                "driver": self.state.climate_temp_driver,
                "passenger": self.state.climate_temp_passenger,
                "rear": self.state.climate_temp_rear,
                "fan": self.state.climate_fan_speed,
                "mode": self.state.climate_mode,
                "sync": self.state.climate_sync
            }
        }
    
    async def _climate_off(self) -> dict:
        """Turn off climate completely."""
        self.state.climate_fan_speed = 0
        # TODO: Write to CAN bus
        return {"success": True, "message": "Climate control off"}
    
    def get_context(self) -> str:
        """Get current context for Claude (injected into prompts)."""
        return self.state.to_context()


# Example usage
async def main():
    """Demo the node interface."""
    node = PiiChanNode()
    
    # Show tools
    print("Available tools:")
    for tool in node.get_tools():
        print(f"  - {tool['name']}: {tool['description']}")
    
    print()
    
    # Get state
    result = await node.handle_tool_call("car_state", {})
    print("Current state:", json.dumps(result, indent=2))
    
    print()
    
    # Set climate
    result = await node.handle_tool_call("climate_set", {
        "zone": "rear",
        "mode": "feet",
        "sync": False
    })
    print("Climate set result:", json.dumps(result, indent=2))
    
    print()
    
    # Context for Claude
    print("Context for Claude:")
    print(node.get_context())


if __name__ == "__main__":
    asyncio.run(main())
