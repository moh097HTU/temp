"""
Custom telemetry injection.

Sends battery state and other custom data to QGC via MAVLink.
"""

import logging
import time
from typing import Optional

from ..common.types import BatteryState, TrackList

logger = logging.getLogger(__name__)

# Try to import pymavlink
try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False


class CustomTelemetrySender:
    """
    Sends custom telemetry data to QGC.
    
    Uses NAMED_VALUE_INT for efficient transport of simple values.
    """

    def __init__(self, connection):
        """
        Initialize telemetry sender.
        
        Args:
            connection: MAVLink connection
        """
        self.connection = connection
        self._last_battery_send = 0.0
        self._battery_send_interval = 0.5  # 2 Hz
        self._last_tracks_send = 0.0
        self._tracks_send_interval = 0.2  # 5 Hz max
        
        logger.info("CustomTelemetrySender initialized")

    def send_battery_state(self, state: BatteryState, force: bool = False) -> None:
        """
        Send battery state via NAMED_VALUE_INT.
        
        Args:
            state: Battery state to send
            force: Force send even if interval not elapsed
        """
        current_time = time.time()
        
        if not force and current_time - self._last_battery_send < self._battery_send_interval:
            return
        
        if not PYMAVLINK_AVAILABLE:
            return

        try:
            time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF
            
            # Send BAT1_ACTIVE
            self.connection.mav.named_value_int_send(
                time_boot_ms=time_boot_ms,
                name=b"BAT1_ACTIVE",
                value=1 if state.bat1_active else 0
            )
            
            # Send BAT2_ACTIVE
            self.connection.mav.named_value_int_send(
                time_boot_ms=time_boot_ms,
                name=b"BAT2_ACTIVE",
                value=1 if state.bat2_active else 0
            )
            
            # Send ACTIVE_BAT (0, 1, or 2)
            self.connection.mav.named_value_int_send(
                time_boot_ms=time_boot_ms,
                name=b"ACTIVE_BAT",
                value=state.active_bat
            )
            
            self._last_battery_send = current_time
            
        except Exception as e:
            logger.error(f"Failed to send battery state: {e}")

    def send_track_count(self, track_list: TrackList) -> None:
        """
        Send track count as a simple summary.
        
        For bandwidth efficiency, we only send count, not full list.
        
        Args:
            track_list: Current track list
        """
        if not PYMAVLINK_AVAILABLE:
            return

        try:
            time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF
            
            self.connection.mav.named_value_int_send(
                time_boot_ms=time_boot_ms,
                name=b"TRK_COUNT",
                value=len(track_list.tracks)
            )
            
        except Exception as e:
            logger.error(f"Failed to send track count: {e}")

    def send_lock_status(self, locked_track_id: Optional[int], lock_valid: bool) -> None:
        """
        Send lock status to QGC.
        
        Args:
            locked_track_id: Currently locked track ID (or None)
            lock_valid: Whether lock is valid
        """
        if not PYMAVLINK_AVAILABLE:
            return

        try:
            time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF
            
            # Send lock status
            self.connection.mav.named_value_int_send(
                time_boot_ms=time_boot_ms,
                name=b"TRK_LOCKED",
                value=1 if lock_valid else 0
            )
            
            # Send locked track ID
            self.connection.mav.named_value_int_send(
                time_boot_ms=time_boot_ms,
                name=b"TRK_LOCK_ID",
                value=locked_track_id if locked_track_id is not None else -1
            )
            
        except Exception as e:
            logger.error(f"Failed to send lock status: {e}")

    def send_tracking_errors(
        self,
        yaw_error_deg: float,
        pitch_error_deg: float
    ) -> None:
        """
        Send tracking errors to QGC for display.
        
        Args:
            yaw_error_deg: Yaw error in degrees
            pitch_error_deg: Pitch error in degrees
        """
        if not PYMAVLINK_AVAILABLE:
            return

        try:
            time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF
            
            # Named value float for precision
            self.connection.mav.named_value_float_send(
                time_boot_ms=time_boot_ms,
                name=b"TRK_YAW_ERR",
                value=yaw_error_deg
            )
            
            self.connection.mav.named_value_float_send(
                time_boot_ms=time_boot_ms,
                name=b"TRK_PIT_ERR",
                value=pitch_error_deg
            )
            
        except Exception as e:
            logger.error(f"Failed to send tracking errors: {e}")

    def send_debug_values(self, values: dict) -> None:
        """
        Send arbitrary debug values.
        
        Args:
            values: Dict of name -> value (int or float)
        """
        if not PYMAVLINK_AVAILABLE:
            return

        try:
            time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF
            
            for name, value in values.items():
                # Truncate name to max 10 chars
                name_bytes = name[:10].encode('ascii')
                
                if isinstance(value, int):
                    self.connection.mav.named_value_int_send(
                        time_boot_ms=time_boot_ms,
                        name=name_bytes,
                        value=value
                    )
                else:
                    self.connection.mav.named_value_float_send(
                        time_boot_ms=time_boot_ms,
                        name=name_bytes,
                        value=float(value)
                    )
                    
        except Exception as e:
            logger.error(f"Failed to send debug values: {e}")
