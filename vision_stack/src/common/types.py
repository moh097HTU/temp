"""
Core data types for the drone vision-guidance system.

All inter-component messages use these strongly-typed dataclasses.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple
import time


@dataclass
class BoundingBox:
    """Bounding box in pixel coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self) -> Tuple[float, float]:
        """Return center point (cx, cy)."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass
class Detection:
    """Single detection from YOLO."""
    bbox: BoundingBox
    class_id: int
    label: str
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class Track:
    """Tracked object with stable ID across frames."""
    track_id: int
    bbox: BoundingBox
    class_id: int
    label: str
    confidence: float
    timestamp: float = field(default_factory=time.time)
    velocity: Optional[Tuple[float, float]] = None  # pixels/sec


@dataclass
class TrackList:
    """List of tracks from a single frame."""
    tracks: List[Track]
    frame_id: int
    timestamp: float = field(default_factory=time.time)


class LockStatus(Enum):
    """Target lock status."""
    UNLOCKED = auto()
    LOCKING = auto()
    LOCKED = auto()
    LOST = auto()


@dataclass
class LockState:
    """Current target lock state."""
    status: LockStatus
    locked_track_id: Optional[int] = None
    lock_timestamp: Optional[float] = None
    frames_since_lock: int = 0
    
    @property
    def is_valid(self) -> bool:
        return self.status == LockStatus.LOCKED and self.locked_track_id is not None


@dataclass
class Errors:
    """Computed tracking errors for control."""
    yaw_error: float  # radians, positive = target right of center
    pitch_error: float  # radians, positive = target above center
    range_error: float  # meters, positive = target too far
    
    # Validity flags
    track_valid: bool = False
    depth_valid: bool = False
    lock_valid: bool = False
    
    timestamp: float = field(default_factory=time.time)

    @property
    def all_valid(self) -> bool:
        return self.track_valid and self.depth_valid and self.lock_valid


@dataclass
class Setpoint:
    """Control setpoint for the flight controller."""
    roll_deg: float  # degrees, positive = bank right
    pitch_deg: float  # degrees, positive = nose up
    thrust: float  # 0.0 - 1.0, always 0 in bench mode
    yaw_deg: float = 0.0  # degrees, typically unused for tracking
    
    timestamp: float = field(default_factory=time.time)

    @staticmethod
    def neutral() -> "Setpoint":
        """Return a neutral (zero) setpoint."""
        return Setpoint(roll_deg=0.0, pitch_deg=0.0, thrust=0.0, yaw_deg=0.0)


class BatteryStatus(Enum):
    """Battery switching status."""
    UNKNOWN = auto()
    BAT1_ACTIVE = auto()
    BAT2_ACTIVE = auto()
    BOTH_ON = auto()  # Invalid state
    BOTH_OFF = auto()  # Invalid state


@dataclass
class BatteryState:
    """Battery switch state from ESP32 GPIO."""
    bat1_active: bool
    bat2_active: bool
    timestamp: float = field(default_factory=time.time)

    @property
    def status(self) -> BatteryStatus:
        if self.bat1_active and not self.bat2_active:
            return BatteryStatus.BAT1_ACTIVE
        elif self.bat2_active and not self.bat1_active:
            return BatteryStatus.BAT2_ACTIVE
        elif self.bat1_active and self.bat2_active:
            return BatteryStatus.BOTH_ON
        else:
            return BatteryStatus.BOTH_OFF

    @property
    def active_bat(self) -> int:
        """Return 1, 2, or 0 (invalid)."""
        if self.status == BatteryStatus.BAT1_ACTIVE:
            return 1
        elif self.status == BatteryStatus.BAT2_ACTIVE:
            return 2
        return 0


class CommandType(Enum):
    """Command types from QGC."""
    START_TRACKING = auto()
    STOP_TRACKING = auto()
    SELECT_TARGET_ID = auto()
    SELECT_TARGET_PIXEL = auto()
    SET_DEPTH_RANGE = auto()
    CLEAR_LOCK = auto()
    REQUEST_TRACK_LIST = auto()


@dataclass
class UserCommand:
    """Command received from QGC via MAVLink."""
    cmd_type: CommandType
    track_id: Optional[int] = None
    pixel_u: Optional[int] = None
    pixel_v: Optional[int] = None
    min_depth: Optional[float] = None
    max_depth: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters."""
    fx: float  # focal length x
    fy: float  # focal length y
    cx: float  # principal point x
    cy: float  # principal point y
    width: int
    height: int


@dataclass 
class Telemetry:
    """Flight controller telemetry data."""
    armed: bool = False
    mode: str = "UNKNOWN"
    battery_voltage: float = 0.0
    battery_remaining: int = 0
    gps_fix: int = 0
    timestamp: float = field(default_factory=time.time)
