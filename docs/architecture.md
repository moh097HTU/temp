# System Architecture

Drone Vision-Guidance System architecture overview.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JETSON NANO                                     │
│                                                                              │
│  ┌──────────────┐                                                           │
│  │   OAK-D Lite │                                                           │
│  │   Camera     │                                                           │
│  │  ┌────┬────┐ │                                                           │
│  │  │RGB │Depth│ │                                                           │
│  └──┴─┬──┴──┬─┴─┘                                                           │
│       │     │                                                                │
│       ▼     │                                                                │
│  ┌─────────────┐    ┌─────────────┐                                          │
│  │ oak_bridge  │    │   depth     │                                          │
│  │  30 FPS     │◄───┤   query     │                                          │
│  └──────┬──────┘    └─────────────┘                                          │
│         │                   ▲                                                │
│   RGB   │                   │                                                │
│  frames │                   │ depth query                                    │
│         ▼                   │                                                │
│  ┌─────────────┐     ZMQ    │                                                │
│  │ perception  │ ──tracks──►│                                                │
│  │ YOLO +      │            │                                                │
│  │ ByteTrack   │     ┌──────┴──────┐                                         │
│  └─────────────┘     │  targeting  │                                         │
│                      │   lock +    │◄── QGC commands ──┐                     │
│                      │   errors    │                    │                    │
│                      └──────┬──────┘                    │                    │
│                             │                           │                    │
│                        ZMQ  │ errors                    │                    │
│                             ▼                           │                    │
│                      ┌─────────────┐                    │                    │
│                      │   control   │                    │                    │
│                      │   mapper +  │                    │                    │
│                      │   safety    │                    │                    │
│                      └──────┬──────┘                    │                    │
│                             │                           │                    │
│                        ZMQ  │ setpoints                 │                    │
│                             ▼                           │                    │
│  ┌─────────────┐     ┌─────────────┐              ┌─────┴─────┐             │
│  │ esp32_gpio  │────►│  mavlink    │──telemetry──►│   QGC     │             │
│  │  battery    │     │   bridge    │              │  commands │             │
│  └─────────────┘     └──────┬──────┘              └───────────┘             │
│         ▲                   │                           ▲                    │
│         │                   │ SET_ATTITUDE_TARGET       │                    │
│         │                   │ 30 Hz                     │                    │
│  ┌──────┴──────┐           ▼                           │                    │
│  │   ESP32     │     ┌─────────────┐                    │                    │
│  │   GPIO      │     │ MAVProxy   │──UDP 14550─────────┘                    │
│  └─────────────┘     │   router    │                                         │
│                      └──────┬──────┘                                         │
│                             │                                                │
│                      Serial │ 57600                                          │
│                             ▼                                                │
│                      ┌─────────────┐                                         │
│                      │ Orange Cube │                                         │
│                      │ PX4 v1.16   │                                         │
│                      │   TELEM1    │                                         │
│                      └─────────────┘                                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │                         VIDEO PATH                                       ││
│  │  oak_bridge ─► video_streamer ─► UDP 5600 RTP ─► QGC (GCS PC)           ││
│  └──────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Perception Pipeline
1. OAK-D captures RGB @ 30 FPS
2. YOLO detects objects → bounding boxes
3. ByteTrack assigns stable track IDs
4. TrackList published to ZMQ

### Targeting Pipeline
1. Receives tracks from perception
2. Receives commands from QGC via MAVLink
3. Maintains target lock across frames
4. Computes yaw/pitch errors from pixel offset
5. Queries depth for range error
6. Publishes Errors to control

### Control Pipeline
1. Maps errors to setpoints:
   - yaw_error → roll (fixed-wing turns by banking)
   - pitch_error → pitch
   - range_error → thrust (flight mode only)
2. Safety manager applies:
   - EMA filtering
   - Slew rate limiting
   - Clamping to limits
   - Failsafe on timeout
3. Publishes Setpoint to MAVLink

### MAVLink Pipeline
1. Streams SET_ATTITUDE_TARGET @ 30 Hz
2. Receives QGC commands
3. Injects battery telemetry from GPIO
4. Monitors failsafe conditions

## Mode Configurations

| Setting | Bench Mode | Flight Mode |
|---------|------------|-------------|
| Thrust | **ALWAYS 0** | 0.3-0.8 |
| Roll limit | ±20° | ±45° |
| Pitch limit | ±10° | ±20° |
| Track timeout | 500ms | 300ms |
| Failsafe action | Neutral | Loiter |

## Safety Features

1. **Bench mode**: Thrust physically disabled
2. **Timeout failsafe**: Neutral on stale tracking
3. **Slew limiting**: Prevents sudden jumps
4. **EMA filtering**: Smooth response
5. **Hard clamps**: Absolute limits enforced
