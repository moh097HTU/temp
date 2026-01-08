"""
SET_ATTITUDE_TARGET message builder.

Builds MAVLink attitude setpoint messages with quaternion from roll/pitch.
"""

import time
from typing import Tuple

from ..common.types import Setpoint
from ..common.math3d import euler_to_quaternion, deg_to_rad, Quaternion

# Try to import pymavlink
try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False


# Type mask bits for SET_ATTITUDE_TARGET
# Setting a bit IGNORES that field
ATTITUDE_TARGET_TYPEMASK_BODY_ROLL_RATE_IGNORE = 1
ATTITUDE_TARGET_TYPEMASK_BODY_PITCH_RATE_IGNORE = 2
ATTITUDE_TARGET_TYPEMASK_BODY_YAW_RATE_IGNORE = 4
ATTITUDE_TARGET_TYPEMASK_THROTTLE_IGNORE = 64
ATTITUDE_TARGET_TYPEMASK_ATTITUDE_IGNORE = 128

# We want to control attitude and thrust, ignore rates
DEFAULT_TYPE_MASK = (
    ATTITUDE_TARGET_TYPEMASK_BODY_ROLL_RATE_IGNORE |
    ATTITUDE_TARGET_TYPEMASK_BODY_PITCH_RATE_IGNORE |
    ATTITUDE_TARGET_TYPEMASK_BODY_YAW_RATE_IGNORE
)


def build_attitude_target_quaternion(
    roll_deg: float,
    pitch_deg: float,
    yaw_deg: float = 0.0
) -> Tuple[float, float, float, float]:
    """
    Build quaternion from Euler angles for SET_ATTITUDE_TARGET.
    
    Args:
        roll_deg: Roll angle in degrees
        pitch_deg: Pitch angle in degrees
        yaw_deg: Yaw angle in degrees (usually 0 for tracking)
        
    Returns:
        Tuple (w, x, y, z) quaternion
    """
    q = euler_to_quaternion(
        roll_rad=deg_to_rad(roll_deg),
        pitch_rad=deg_to_rad(pitch_deg),
        yaw_rad=deg_to_rad(yaw_deg)
    )
    return (q.w, q.x, q.y, q.z)


def build_attitude_target_message(
    mav: "mavutil.mavlink.MAVLink",
    setpoint: Setpoint,
    target_system: int = 1,
    target_component: int = 1
) -> bytes:
    """
    Build SET_ATTITUDE_TARGET MAVLink message.
    
    Args:
        mav: MAVLink connection/dialect
        setpoint: Control setpoint
        target_system: Target system ID (usually 1 for FC)
        target_component: Target component ID (usually 1)
        
    Returns:
        Encoded MAVLink message bytes
    """
    if not PYMAVLINK_AVAILABLE:
        raise RuntimeError("pymavlink not available")

    # Build quaternion from roll/pitch
    q = build_attitude_target_quaternion(
        roll_deg=setpoint.roll_deg,
        pitch_deg=setpoint.pitch_deg,
        yaw_deg=setpoint.yaw_deg
    )

    # Time in milliseconds since boot (we use monotonic time)
    time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF

    msg = mav.set_attitude_target_encode(
        time_boot_ms=time_boot_ms,
        target_system=target_system,
        target_component=target_component,
        type_mask=DEFAULT_TYPE_MASK,
        q=list(q),  # Quaternion [w, x, y, z]
        body_roll_rate=0.0,
        body_pitch_rate=0.0,
        body_yaw_rate=0.0,
        thrust=setpoint.thrust
    )

    return msg


def send_attitude_target(
    connection: "mavutil.mavlink_connection",
    setpoint: Setpoint,
    target_system: int = 1,
    target_component: int = 1
) -> None:
    """
    Send SET_ATTITUDE_TARGET to flight controller.
    
    Args:
        connection: MAVLink connection
        setpoint: Control setpoint
        target_system: Target system ID
        target_component: Target component ID
    """
    if not PYMAVLINK_AVAILABLE:
        return

    q = build_attitude_target_quaternion(
        roll_deg=setpoint.roll_deg,
        pitch_deg=setpoint.pitch_deg,
        yaw_deg=setpoint.yaw_deg
    )

    time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF

    connection.mav.set_attitude_target_send(
        time_boot_ms=time_boot_ms,
        target_system=target_system,
        target_component=target_component,
        type_mask=DEFAULT_TYPE_MASK,
        q=list(q),
        body_roll_rate=0.0,
        body_pitch_rate=0.0,
        body_yaw_rate=0.0,
        thrust=setpoint.thrust
    )
