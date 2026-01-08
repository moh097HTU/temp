# ZMQ Message Definitions

Internal message schemas for inter-process communication.

## Topics and Publishers

| Topic | Publisher | Subscriber(s) | Rate |
|-------|-----------|---------------|------|
| `tracks` | perception | targeting | 30 Hz |
| `lock_state` | targeting | control, mavlink | 30 Hz |
| `errors` | targeting | control | 30 Hz |
| `setpoints` | control | mavlink | 30 Hz |
| `battery_state` | gpio_bridge | mavlink | 2 Hz |
| `qgc_cmds` | mavlink | targeting | on-demand |
| `telemetry` | mavlink | control | 1 Hz |

## Message Schemas

### Track

```python
@dataclass
class Track:
    track_id: int           # Stable ID across frames
    bbox: BoundingBox       # {x1, y1, x2, y2}
    class_id: int           # COCO class ID
    label: str              # Class name
    confidence: float       # 0.0-1.0
    timestamp: float        # Unix timestamp
```

### TrackList

```python
@dataclass
class TrackList:
    tracks: List[Track]
    frame_id: int
    timestamp: float
```

### LockState

```python
@dataclass  
class LockState:
    status: LockStatus      # UNLOCKED, LOCKING, LOCKED, LOST
    locked_track_id: int?   # None if unlocked
    lock_timestamp: float?
    frames_since_lock: int
```

### Errors

```python
@dataclass
class Errors:
    yaw_error: float        # radians, + = target right
    pitch_error: float      # radians, + = target above
    range_error: float      # meters, + = target far
    track_valid: bool
    depth_valid: bool
    lock_valid: bool
    timestamp: float
```

### Setpoint

```python
@dataclass
class Setpoint:
    roll_deg: float         # degrees, + = bank right
    pitch_deg: float        # degrees, + = nose up
    thrust: float           # 0-1, ALWAYS 0 in bench
    yaw_deg: float          # degrees (usually 0)
    timestamp: float
```

### BatteryState

```python
@dataclass
class BatteryState:
    bat1_active: bool
    bat2_active: bool
    timestamp: float
    
    @property
    def active_bat(self) -> int:  # 0, 1, or 2
```

### UserCommand

```python
@dataclass
class UserCommand:
    cmd_type: CommandType
    track_id: int?
    pixel_u: int?
    pixel_v: int?
    min_depth: float?
    max_depth: float?
    timestamp: float
```

## CommandType Enum

```python
class CommandType(Enum):
    START_TRACKING
    STOP_TRACKING
    SELECT_TARGET_ID
    SELECT_TARGET_PIXEL
    SET_DEPTH_RANGE
    CLEAR_LOCK
    REQUEST_TRACK_LIST
```

## Serialization

Messages are serialized to JSON:

```json
{
    "__type__": "Track",
    "track_id": 42,
    "bbox": {"x1": 100, "y1": 200, "x2": 300, "y2": 400},
    "class_id": 0,
    "label": "person",
    "confidence": 0.95,
    "timestamp": 1704700000.0
}
```
