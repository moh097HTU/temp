# QGC Integration Guide: Vision Tracking MAVLink Commands

This document explains how to integrate QGroundControl (QGC) with the Jetson-based vision tracking system. The system uses MAVLink `COMMAND_LONG` messages for all commands.

---

## System Overview

```
┌─────────────┐      MAVLink UDP       ┌─────────────────┐
│     QGC     │ ──────────────────────>│  Jetson Nano    │
│  (Windows)  │     Port 14550         │  Vision Stack   │
│             │<───────────────────────│                 │
│  Video UDP  │     Video Stream       │  OAK-D Camera   │
│  Port 5600  │     H.264 RTP          │                 │
└─────────────┘                        └─────────────────┘
```

**Video Display:**
- Displays H.264 video stream on UDP port 5600
- Bounding boxes are **already drawn on the video** by the Jetson
- Each bounding box shows: `#<track_id> <class_name> <confidence>`
- Example: `#3 person 0.92` means track ID = 3, detected as person, 92% confidence

---

## MAVLink Commands (COMMAND_LONG)

All commands use the standard MAVLink `COMMAND_LONG` message format:

```cpp
void sendTrackingCommand(uint16_t command, float param1 = 0, float param2 = 0) {
    mavlink_message_t msg;
    mavlink_msg_command_long_pack(
        255,                     // source system (GCS)
        0,                       // source component
        &msg,
        1,                       // target_system (vehicle/Jetson)
        0,                       // target_component
        command,                 // command ID (see table below)
        0,                       // confirmation
        param1,                  // parameter 1
        param2,                  // parameter 2
        0, 0, 0, 0, 0            // parameters 3-7 (unused)
    );
    // Send msg via MAVLink connection
}
```

---

## Command Reference

| Command | ID | param1 | param2 | Description |
|---------|-----|--------|--------|-------------|
| START_TRACKING | `31100` | - | - | Enable tracking mode. Must be sent before selecting a target. |
| STOP_TRACKING | `31101` | - | - | Disable tracking mode. Clears lock and stops control output. |
| SELECT_TARGET_ID | `31102` | track_id | - | Lock onto the track with specified ID (shown on bounding box). |
| SELECT_TARGET_PIXEL | `31103` | pixel_x | pixel_y | Lock onto track at pixel position (deprecated, use ID instead). |
| SET_DEPTH_RANGE | `31104` | min_m | max_m | Set depth filtering range in meters. |
| CLEAR_LOCK | `31105` | - | - | Clear current target lock without stopping tracking mode. |

---

## Recommended Usage Flow

### Step 1: Start Tracking Mode
```cpp
// Enable tracking mode - must be called first
sendTrackingCommand(31100);  // START_TRACKING
```

### Step 2: User Selects Target
When user sees bounding boxes on video and wants to track a specific target:

```cpp
// User clicked on a box showing "#3 person 0.92"
// Extract track ID = 3 from the label
int selectedTrackId = 3;

// Send selection command
sendTrackingCommand(31102, (float)selectedTrackId);  // SELECT_TARGET_ID
```

### Step 3: Stop Tracking (when done)
```cpp
sendTrackingCommand(31101);  // STOP_TRACKING
```

---

## Complete C++ Implementation Example

```cpp
#include <mavlink.h>

class VisionTrackingController {
private:
    MAVLinkConnection* connection;
    
    void sendCommand(uint16_t cmdId, float p1 = 0, float p2 = 0) {
        mavlink_message_t msg;
        mavlink_msg_command_long_pack(
            255, 0, &msg,    // source: GCS
            1, 0,            // target: vehicle
            cmdId, 0,        // command, confirmation
            p1, p2,          // params 1-2
            0, 0, 0, 0, 0    // params 3-7
        );
        connection->send(msg);
    }

public:
    // Enable tracking mode
    void startTracking() {
        sendCommand(31100);
    }
    
    // Disable tracking mode
    void stopTracking() {
        sendCommand(31101);
    }
    
    // Select target by track ID (shown on bounding box as #ID)
    void selectTargetById(int trackId) {
        sendCommand(31102, (float)trackId);
    }
    
    // Select target by clicking on video (alternative method)
    void selectTargetByPixel(int x, int y) {
        sendCommand(31103, (float)x, (float)y);
    }
    
    // Clear current lock
    void clearLock() {
        sendCommand(31105);
    }
};
```

---

## QGC UI Integration Suggestions

### Option A: Click on Video to Select
1. When user clicks on video widget, calculate pixel coordinates
2. **Scale to video resolution** (1280x720): 
   ```cpp
   int videoX = clickX * (1280.0 / widgetWidth);
   int videoY = clickY * (720.0 / widgetHeight);
   ```
3. Send `SELECT_TARGET_PIXEL` (31103) with scaled coordinates

### Option B: Track ID Dropdown (Recommended)
1. Display a list/dropdown of available track IDs
2. When user selects a track ID, send `SELECT_TARGET_ID` (31102)
3. Track IDs are visible on bounding boxes (e.g., "#3 person")

### Option C: Parse ID from Video Click
1. User clicks near a bounding box
2. QGC determines which track ID's box was clicked (based on stored positions)
3. Send `SELECT_TARGET_ID` (31102) with that ID

---

## Expected Jetson Response (Debug Logs)

When commands are received correctly, the Jetson logs will show:

```
[MAVLINK] Received COMMAND_LONG: cmd=31100, params=(0.0, 0.0, 0.0, 0.0)
[MAVLINK] Received command: START_TRACKING
[TARGETING] Received command: START_TRACKING
[TARGETING] Tracking ENABLED

[MAVLINK] Received COMMAND_LONG: cmd=31102, params=(3.0, 0.0, 0.0, 0.0)
[MAVLINK] Received command: SELECT_TARGET_ID
[TARGETING] Received command: SELECT_TARGET_ID
[TARGETING] Select target by ID: 3
[TARGETING] Lock state: LockState(status=LOCKED, locked_track_id=3, ...)
```

---

## Network Configuration

| Service | Protocol | Port | Direction |
|---------|----------|------|-----------|
| MAVLink Telemetry | UDP | 14550 | Jetson → QGC |
| MAVLink Commands | UDP | 14550 | QGC → Jetson |
| Video Stream | UDP/RTP | 5600 | Jetson → QGC |

**IP Addresses:**
- Jetson: Connected via USB hotspot (e.g., 172.20.10.X)
- QGC: Windows machine (e.g., 172.20.10.4)

---

## Summary

1. **Send `31100` (START_TRACKING)** first to enable tracking mode
2. **Send `31102` (SELECT_TARGET_ID) with `param1=track_id`** to lock onto a target
3. Track IDs are visible on the video bounding boxes as `#<id>`
4. **Send `31101` (STOP_TRACKING)** to disable tracking

The Jetson handles all detection, tracking, and control output automatically once a target is selected.
