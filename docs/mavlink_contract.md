# MAVLink Contract

Defines the MAVLink message protocol between Jetson companion computer and QGC/FC.

## Topology

```
┌───────────────┐         ┌─────────────┐         ┌─────────────┐
│ Orange Cube   │ Serial  │  MAVProxy   │  UDP    │   Custom    │
│ (PX4 v1.16)   │◄───────►│  (Jetson)   │◄───────►│    QGC      │
│               │ 57600   │             │ 14550   │   (GCS PC)  │
└───────────────┘         └──────┬──────┘         └─────────────┘
                                 │ UDP
                                 │ 14551
                          ┌──────▼──────┐
                          │   Jetson    │
                          │ MAVLink     │
                          │   Bridge    │
                          └─────────────┘
```

## Component IDs

| Component | System ID | Component ID |
|-----------|-----------|--------------|
| Flight Controller | 1 | 1 |
| Jetson Companion | 255 | 190 (ONBOARD_COMPUTER) |
| QGC | 255 | (varies) |

## Messages: Jetson → FC

### SET_ATTITUDE_TARGET (Continuous at 30 Hz)

Controls aircraft attitude in offboard mode.

```
time_boot_ms: uint32      # Monotonic timestamp
target_system: 1          # FC system ID
target_component: 1       # FC component ID
type_mask: 7              # Ignore body rates, use attitude + thrust
q[4]: float[4]            # Quaternion [w,x,y,z] from roll/pitch
body_roll_rate: 0         # Ignored
body_pitch_rate: 0        # Ignored
body_yaw_rate: 0          # Ignored
thrust: float             # 0.0-1.0 (ALWAYS 0 in bench mode)
```

### HEARTBEAT (1 Hz)

```
type: MAV_TYPE_ONBOARD_CONTROLLER
autopilot: MAV_AUTOPILOT_INVALID
base_mode: 0
custom_mode: 0
system_status: MAV_STATE_ACTIVE
```

### COMMAND_LONG (Mode changes)

```
command: MAV_CMD_DO_SET_MODE
param1: MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
param2: custom_mode (PX4 offboard = 6 << 16)
```

## Messages: Jetson → QGC (Custom Telemetry)

### NAMED_VALUE_INT (1-2 Hz)

Battery status from ESP32:

```
name: "BAT1_ACTIVE"   value: 0/1
name: "BAT2_ACTIVE"   value: 0/1
name: "ACTIVE_BAT"    value: 0/1/2
```

Lock status:

```
name: "TRK_LOCKED"    value: 0/1
name: "TRK_LOCK_ID"   value: track_id (-1 if none)
name: "TRK_COUNT"     value: number of tracks
```

### NAMED_VALUE_FLOAT (Optional, 5 Hz)

Tracking errors for display:

```
name: "TRK_YAW_ERR"   value: degrees
name: "TRK_PIT_ERR"   value: degrees
```

## Messages: QGC → Jetson (Commands)

### COMMAND_LONG (Custom Commands)

| Command ID | Description | Parameters |
|------------|-------------|------------|
| 31100 | START_TRACKING | - |
| 31101 | STOP_TRACKING | - |
| 31102 | SELECT_TARGET_ID | param1: track_id |
| 31103 | SELECT_TARGET_PIXEL | param1: u, param2: v |
| 31104 | SET_DEPTH_RANGE | param1: min, param2: max |
| 31105 | CLEAR_LOCK | - |
| 31106 | REQUEST_TRACK_LIST | - |

### NAMED_VALUE_INT (Alternative simple commands)

```
name: "TRK_START"     value: 1
name: "TRK_STOP"      value: 1
name: "TRK_SEL_ID"    value: track_id
name: "TRK_CLEAR"     value: 1
```

## Bandwidth Considerations

TELEM1 at 57600 baud ≈ 5760 bytes/sec

| Message | Rate | Approx Size | Bandwidth |
|---------|------|-------------|-----------|
| SET_ATTITUDE_TARGET | 30 Hz | 39 bytes | 1170 B/s |
| HEARTBEAT | 1 Hz | 9 bytes | 9 B/s |
| NAMED_VALUE_INT (x3) | 2 Hz | 18 bytes | 108 B/s |
| **Total Jetson→FC** | | | ~1300 B/s |

Video stream uses separate UDP (not TELEM1).

## Offboard Mode Requirements (PX4 v1.16)

1. Stream setpoints for >0.5s before requesting mode change
2. Maintain >2 Hz setpoint rate (we do 30 Hz)
3. Send HEARTBEAT as companion
4. If setpoint stream stops >0.5s, PX4 exits offboard

## Error Handling

| Condition | Jetson Action |
|-----------|---------------|
| No FC heartbeat >3s | Log error, attempt reconnect |
| Offboard mode rejected | Log, continue streaming neutral |
| Track lost | Send neutral setpoints |
| QGC disconnect | Continue tracking if active |
