"""Common utilities for drone vision stack."""

from .types import (
    BoundingBox,
    Detection,
    Track,
    TrackList,
    LockStatus,
    LockState,
    Errors,
    Setpoint,
    BatteryStatus,
    BatteryState,
    CommandType,
    UserCommand,
    CameraIntrinsics,
    Telemetry,
)
from .filters import (
    EMAFilter,
    SlewRateLimiter,
    Debouncer,
    LowPassFilter,
    clamp,
    deadband,
)
from .math3d import (
    Quaternion,
    euler_to_quaternion,
    quaternion_to_euler,
    quaternion_multiply,
    pixel_to_angles,
    deg_to_rad,
    rad_to_deg,
    normalize_angle,
)

__all__ = [
    # Types
    "BoundingBox",
    "Detection",
    "Track",
    "TrackList",
    "LockStatus",
    "LockState",
    "Errors",
    "Setpoint",
    "BatteryStatus",
    "BatteryState",
    "CommandType",
    "UserCommand",
    "CameraIntrinsics",
    "Telemetry",
    # Filters
    "EMAFilter",
    "SlewRateLimiter",
    "Debouncer",
    "LowPassFilter",
    "clamp",
    "deadband",
    # Math
    "Quaternion",
    "euler_to_quaternion",
    "quaternion_to_euler",
    "quaternion_multiply",
    "pixel_to_angles",
    "deg_to_rad",
    "rad_to_deg",
    "normalize_angle",
]
