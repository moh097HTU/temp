"""
FC telemetry receiver.

Receives and processes telemetry from the flight controller.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Callable

from ..common.types import Telemetry

logger = logging.getLogger(__name__)

# Try to import pymavlink
try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False


@dataclass
class TelemetryConfig:
    """Telemetry receiver configuration."""
    timeout_ms: float = 1000.0  # Telemetry timeout
    heartbeat_timeout_ms: float = 3000.0  # FC heartbeat timeout


class TelemetryReceiver:
    """
    Receives and tracks FC telemetry.
    
    Monitors:
    - Heartbeat (connection alive)
    - System status
    - Battery (from FC, not ESP32)
    - GPS status
    - Current mode
    """

    def __init__(self, config: TelemetryConfig):
        """
        Initialize telemetry receiver.
        
        Args:
            config: Telemetry configuration
        """
        self.config = config
        
        # State
        self._last_heartbeat_time: Optional[float] = None
        self._telemetry = Telemetry()
        self._connected = False
        
        logger.info("TelemetryReceiver initialized")

    def process_message(self, msg) -> None:
        """
        Process incoming MAVLink message.
        
        Args:
            msg: MAVLink message
        """
        if not PYMAVLINK_AVAILABLE:
            return

        msg_type = msg.get_type()
        current_time = time.time()

        if msg_type == 'HEARTBEAT':
            self._process_heartbeat(msg, current_time)
        elif msg_type == 'SYS_STATUS':
            self._process_sys_status(msg)
        elif msg_type == 'BATTERY_STATUS':
            self._process_battery_status(msg)
        elif msg_type == 'GPS_RAW_INT':
            self._process_gps(msg)
        elif msg_type == 'EXTENDED_SYS_STATE':
            self._process_extended_state(msg)

    def _process_heartbeat(self, msg, current_time: float) -> None:
        """Process HEARTBEAT message."""
        # Only process FC heartbeats
        if msg.type not in [
            mavutil.mavlink.MAV_TYPE_FIXED_WING,
            mavutil.mavlink.MAV_TYPE_QUADROTOR,
            mavutil.mavlink.MAV_TYPE_GENERIC
        ]:
            return

        self._last_heartbeat_time = current_time
        self._connected = True
        
        # Extract armed state
        self._telemetry.armed = bool(
            msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
        )
        
        # Extract mode (simplified)
        custom_mode = msg.custom_mode
        main_mode = (custom_mode >> 16) & 0xFF
        
        mode_names = {
            0: "MANUAL",
            1: "ALTITUDE",
            2: "POSITION",
            3: "AUTO.MISSION",
            4: "AUTO.LOITER",
            5: "AUTO.RTL",
            6: "OFFBOARD",
            7: "STABILIZED",
            8: "ACRO",
        }
        self._telemetry.mode = mode_names.get(main_mode, f"MODE_{main_mode}")
        self._telemetry.timestamp = current_time

    def _process_sys_status(self, msg) -> None:
        """Process SYS_STATUS message."""
        # Battery info from FC
        if msg.voltage_battery > 0:
            self._telemetry.battery_voltage = msg.voltage_battery / 1000.0  # mV to V
        if msg.battery_remaining >= 0:
            self._telemetry.battery_remaining = msg.battery_remaining

    def _process_battery_status(self, msg) -> None:
        """Process BATTERY_STATUS message."""
        if len(msg.voltages) > 0 and msg.voltages[0] < 65535:
            total_mv = sum(v for v in msg.voltages if v < 65535)
            self._telemetry.battery_voltage = total_mv / 1000.0
        
        if msg.battery_remaining >= 0:
            self._telemetry.battery_remaining = msg.battery_remaining

    def _process_gps(self, msg) -> None:
        """Process GPS_RAW_INT message."""
        self._telemetry.gps_fix = msg.fix_type

    def _process_extended_state(self, msg) -> None:
        """Process EXTENDED_SYS_STATE message."""
        # Additional state info if needed
        pass

    def check_connection(self) -> bool:
        """
        Check if FC connection is healthy.
        
        Returns:
            True if connected and receiving heartbeats
        """
        if self._last_heartbeat_time is None:
            return False
        
        elapsed_ms = (time.time() - self._last_heartbeat_time) * 1000
        return elapsed_ms < self.config.heartbeat_timeout_ms

    def get_telemetry(self) -> Telemetry:
        """Get current telemetry state."""
        return self._telemetry

    @property
    def is_connected(self) -> bool:
        """Check if connected to FC."""
        return self._connected and self.check_connection()

    @property
    def is_armed(self) -> bool:
        """Check if FC is armed."""
        return self._telemetry.armed

    @property
    def mode(self) -> str:
        """Get current flight mode."""
        return self._telemetry.mode

    @property
    def is_offboard(self) -> bool:
        """Check if in offboard mode."""
        return self._telemetry.mode == "OFFBOARD"

    @property
    def time_since_heartbeat_ms(self) -> Optional[float]:
        """Get time since last heartbeat in ms."""
        if self._last_heartbeat_time is None:
            return None
        return (time.time() - self._last_heartbeat_time) * 1000
