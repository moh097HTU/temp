"""
Offboard session management.

Handles entering/exiting offboard mode and continuous setpoint streaming.
"""

import logging
import time
import threading
from dataclasses import dataclass
from typing import Optional, Callable

from ..common.types import Setpoint
from .setpoints_attitude import send_attitude_target

logger = logging.getLogger(__name__)

# Try to import pymavlink
try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False


# MAVLink command IDs
MAV_CMD_DO_SET_MODE = 176
MAV_MODE_FLAG_CUSTOM_MODE_ENABLED = 1

# PX4 custom modes
PX4_CUSTOM_MAIN_MODE_OFFBOARD = 6


@dataclass
class OffboardConfig:
    """Offboard session configuration."""
    setpoint_rate_hz: float = 30.0
    heartbeat_rate_hz: float = 1.0
    arm_timeout_s: float = 5.0
    mode_timeout_s: float = 5.0
    system_id: int = 255  # Companion computer ID
    component_id: int = 190  # MAV_COMP_ID_ONBOARD_COMPUTER
    target_system: int = 1  # FC system ID
    target_component: int = 1  # FC component ID


class OffboardSession:
    """
    Manages offboard flight mode session.
    
    Requirements for PX4 offboard:
    1. Stream setpoints before requesting offboard mode
    2. Continue streaming at required rate while in offboard
    3. Send heartbeat as companion computer
    """

    def __init__(
        self,
        connection: "mavutil.mavlink_connection",
        config: OffboardConfig
    ):
        """
        Initialize offboard session.
        
        Args:
            connection: MAVLink connection to FC
            config: Offboard configuration
        """
        self.connection = connection
        self.config = config
        
        self._active = False
        self._streaming = False
        self._stream_thread: Optional[threading.Thread] = None
        self._current_setpoint = Setpoint.neutral()
        self._setpoint_lock = threading.Lock()
        
        logger.info("OffboardSession initialized")

    def start(self) -> bool:
        """
        Start offboard session.
        
        1. Start setpoint streaming
        2. Wait for FC to receive setpoints
        3. Request offboard mode
        
        Returns:
            True if offboard mode entered successfully
        """
        if self._active:
            logger.warning("Offboard session already active")
            return True

        if not PYMAVLINK_AVAILABLE:
            logger.warning("pymavlink not available - running in stub mode")
            self._active = True
            self._start_streaming()
            return True

        # Start streaming neutral setpoints
        self._start_streaming()
        
        # Wait for FC to receive setpoints (PX4 needs ~0.5s of setpoints)
        logger.info("Pre-streaming setpoints...")
        time.sleep(0.5)
        
        # Request offboard mode
        if self._request_offboard_mode():
            self._active = True
            logger.info("Offboard mode active")
            return True
        else:
            logger.error("Failed to enter offboard mode")
            self._stop_streaming()
            return False

    def stop(self) -> None:
        """Stop offboard session."""
        if not self._active:
            return

        logger.info("Stopping offboard session...")
        
        # Stream neutral setpoints briefly before stopping
        with self._setpoint_lock:
            self._current_setpoint = Setpoint.neutral()
        time.sleep(0.3)
        
        # Stop streaming
        self._stop_streaming()
        
        # Exit offboard mode (FC will typically fallback to previous mode)
        self._active = False
        logger.info("Offboard session stopped")

    def update_setpoint(self, setpoint: Setpoint) -> None:
        """
        Update the current setpoint.
        
        Args:
            setpoint: New setpoint to stream
        """
        with self._setpoint_lock:
            self._current_setpoint = setpoint

    def _start_streaming(self) -> None:
        """Start background streaming thread."""
        if self._streaming:
            return
        
        self._streaming = True
        self._stream_thread = threading.Thread(target=self._streaming_loop, daemon=True)
        self._stream_thread.start()
        logger.debug("Setpoint streaming started")

    def _stop_streaming(self) -> None:
        """Stop background streaming thread."""
        self._streaming = False
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)
            self._stream_thread = None
        logger.debug("Setpoint streaming stopped")

    def _streaming_loop(self) -> None:
        """Background thread for continuous setpoint streaming."""
        setpoint_period = 1.0 / self.config.setpoint_rate_hz
        heartbeat_period = 1.0 / self.config.heartbeat_rate_hz
        last_heartbeat = 0.0
        
        while self._streaming:
            loop_start = time.time()
            
            # Get current setpoint
            with self._setpoint_lock:
                setpoint = self._current_setpoint
            
            # Send setpoint
            if PYMAVLINK_AVAILABLE:
                try:
                    send_attitude_target(
                        connection=self.connection,
                        setpoint=setpoint,
                        target_system=self.config.target_system,
                        target_component=self.config.target_component
                    )
                except Exception as e:
                    logger.error(f"Failed to send setpoint: {e}")
            
            # Send heartbeat periodically
            if time.time() - last_heartbeat >= heartbeat_period:
                self._send_heartbeat()
                last_heartbeat = time.time()
            
            # Rate limiting
            elapsed = time.time() - loop_start
            if elapsed < setpoint_period:
                time.sleep(setpoint_period - elapsed)

    def _send_heartbeat(self) -> None:
        """Send heartbeat as companion computer."""
        if not PYMAVLINK_AVAILABLE:
            return
        
        try:
            self.connection.mav.heartbeat_send(
                type=mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                base_mode=0,
                custom_mode=0,
                system_status=mavutil.mavlink.MAV_STATE_ACTIVE
            )
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")

    def _request_offboard_mode(self) -> bool:
        """Request transition to offboard mode."""
        if not PYMAVLINK_AVAILABLE:
            return True

        try:
            # PX4 uses custom mode for offboard
            # Main mode = 6 (OFFBOARD), sub mode = 0
            custom_mode = PX4_CUSTOM_MAIN_MODE_OFFBOARD << 16
            
            self.connection.mav.command_long_send(
                self.config.target_system,
                self.config.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,  # confirmation
                MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,  # param1: mode flag
                custom_mode,  # param2: custom mode
                0, 0, 0, 0, 0  # params 3-7 unused
            )
            
            # Wait for ACK
            start_time = time.time()
            while time.time() - start_time < self.config.mode_timeout_s:
                msg = self.connection.recv_match(
                    type='COMMAND_ACK',
                    blocking=True,
                    timeout=0.5
                )
                if msg and msg.command == mavutil.mavlink.MAV_CMD_DO_SET_MODE:
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        return True
                    else:
                        logger.warning(f"Mode change rejected: {msg.result}")
                        return False
            
            logger.warning("Mode change timeout")
            return False
            
        except Exception as e:
            logger.error(f"Failed to request offboard mode: {e}")
            return False

    @property
    def is_active(self) -> bool:
        """Check if offboard session is active."""
        return self._active

    @property
    def is_streaming(self) -> bool:
        """Check if setpoint streaming is active."""
        return self._streaming
