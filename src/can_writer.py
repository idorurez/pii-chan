"""
CAN Bus Writer - For sending commands to the car (HVAC, etc.)

⚠️ SAFETY WARNING: This module is for non-safety systems ONLY.
Never send steering, braking, or throttle commands.

Currently a stub - will be populated once HVAC messages are decoded.
"""

from dataclasses import dataclass
from typing import Optional
import logging

try:
    import can
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ClimateState:
    """Desired climate control state."""
    driver_temp_f: Optional[float] = None  # 60-90°F
    passenger_temp_f: Optional[float] = None
    fan_speed: Optional[int] = None  # 0-7, or 8 for auto
    ac_on: Optional[bool] = None
    recirc: Optional[bool] = None
    vent_mode: Optional[str] = None  # "face", "feet", "defrost", etc.


class CANWriter:
    """
    CAN bus writer for sending commands.
    
    IMPORTANT: Message IDs and formats must be discovered through
    CAN bus sniffing. See docs/CAN_SNIFFING_GUIDE.md
    
    This is a STUB until the Sienna HVAC messages are decoded.
    """
    
    # Message IDs - TO BE DISCOVERED
    # These are placeholders based on typical Toyota patterns
    CLIMATE_CONTROL_ID = 0x540  # PLACEHOLDER - needs verification
    
    def __init__(self, interface: str = "socketcan", channel: str = "can0"):
        self.interface = interface
        self.channel = channel
        self.bus = None
        self._enabled = False
        
    def connect(self) -> bool:
        """Connect to CAN bus for writing."""
        if not CAN_AVAILABLE:
            logger.warning("python-can not available, CAN write disabled")
            return False
            
        if self.interface == "mock":
            logger.info("CAN writer in mock mode")
            self._enabled = True
            return True
            
        try:
            self.bus = can.interface.Bus(
                channel=self.channel,
                bustype=self.interface
            )
            self._enabled = True
            logger.info(f"CAN writer connected: {self.channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect CAN bus: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from CAN bus."""
        if self.bus:
            self.bus.shutdown()
            self.bus = None
        self._enabled = False
        
    @property
    def is_enabled(self) -> bool:
        return self._enabled
        
    def set_climate(self, state: ClimateState) -> bool:
        """
        Send climate control command.
        
        ⚠️ NOT YET IMPLEMENTED - Needs CAN message discovery
        
        Args:
            state: Desired climate state
            
        Returns:
            True if command sent successfully
        """
        if not self._enabled:
            logger.warning("CAN writer not enabled")
            return False
            
        # TODO: Implement once message format is discovered
        # See docs/CAN_SNIFFING_GUIDE.md
        
        logger.warning("Climate control not yet implemented - need to decode CAN messages")
        logger.info(f"Would set: {state}")
        
        # PLACEHOLDER - this is what the implementation might look like:
        #
        # data = bytearray(8)
        # 
        # if state.driver_temp_f is not None:
        #     # Convert temp to CAN value (needs calibration)
        #     data[0] = int((state.driver_temp_f - 60) / 0.5)
        #     
        # if state.fan_speed is not None:
        #     data[2] = state.fan_speed
        #     
        # if state.ac_on is not None:
        #     if state.ac_on:
        #         data[4] |= 0x01
        #     else:
        #         data[4] &= ~0x01
        #
        # msg = can.Message(
        #     arbitration_id=self.CLIMATE_CONTROL_ID,
        #     data=data,
        #     is_extended_id=False
        # )
        # self.bus.send(msg)
        
        return False
        
    def set_driver_temp(self, temp_f: float) -> bool:
        """Set driver side temperature."""
        return self.set_climate(ClimateState(driver_temp_f=temp_f))
        
    def set_fan_speed(self, speed: int) -> bool:
        """Set fan speed (0=off, 1-7=manual, 8=auto)."""
        return self.set_climate(ClimateState(fan_speed=speed))
        
    def set_ac(self, on: bool) -> bool:
        """Turn AC on/off."""
        return self.set_climate(ClimateState(ac_on=on))
        
    def send_raw(self, msg_id: int, data: bytes) -> bool:
        """
        Send a raw CAN message. For testing/development only.
        
        ⚠️ BE CAREFUL - only use for non-safety messages!
        
        Args:
            msg_id: CAN message ID
            data: Message data (up to 8 bytes)
            
        Returns:
            True if sent successfully
        """
        if not self._enabled:
            return False
            
        if self.interface == "mock":
            logger.info(f"Mock send: ID=0x{msg_id:03X} data={data.hex()}")
            return True
            
        try:
            msg = can.Message(
                arbitration_id=msg_id,
                data=data,
                is_extended_id=False
            )
            self.bus.send(msg)
            logger.debug(f"Sent: ID=0x{msg_id:03X} data={data.hex()}")
            return True
        except Exception as e:
            logger.error(f"Failed to send CAN message: {e}")
            return False


# Convenience functions for Mira
def create_writer(interface: str = "mock", channel: str = "can0") -> CANWriter:
    """Create and connect a CAN writer."""
    writer = CANWriter(interface, channel)
    writer.connect()
    return writer
