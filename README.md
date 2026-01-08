# Drone Vision-Guidance System

Production-grade fixed-wing drone vision-guidance system for target tracking with Jetson Nano, OAK-D Lite camera, and PX4 flight controller.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        JETSON NANO                               │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ OAK-D    │→ │ Perception│→ │Targeting │→ │   Control     │   │
│  │ Bridge   │  │ (YOLO+    │  │ (Lock +  │  │  (Safety +    │   │
│  │ (RGB+    │  │ ByteTrack)│  │ Errors)  │  │   Mapper)     │   │
│  │ Depth)   │  └───────────┘  └──────────┘  └───────┬───────┘   │
│  └─────┬────┘                                       │           │
│        │                                            ▼           │
│        │                               ┌────────────────────┐   │
│        └──────────────────────────────→│   MAVLink Bridge   │   │
│                                        │   (Offboard +      │   │
│                                        │    Telemetry)      │   │
│                                        └─────────┬──────────┘   │
│                                                  │              │
│  ┌──────────────┐    ┌───────────────────────────┼──────────┐   │
│  │ ESP32 GPIO   │───→│          MAVProxy         │          │   │
│  │ (Battery)    │    │   (Serial ↔ UDP Router)   │          │   │
│  └──────────────┘    └───────────┬───────────────┼──────────┘   │
│                                  │               │              │
│  ┌──────────────┐                │               │              │
│  │Video Streamer│────────────────┼───────────────┼──────────┐   │
│  │ (GStreamer)  │                │               │          │   │
│  └──────────────┘                │               │          │   │
└──────────────────────────────────┼───────────────┼──────────┼───┘
                                   │               │          │
                          Serial   │      UDP      │   UDP    │
                          57600    │     14551     │   5600   │
                                   │               │          │
                                   ▼               │          │
                          ┌────────────────┐       │          │
                          │  Orange Cube   │       │          │
                          │ (PX4 v1.16.0)  │       │          │
                          └────────────────┘       │          │
                                                   │          │
                          ┌────────────────────────┼──────────┘
                          │                        │
                          ▼                        ▼
                    ┌─────────────────────────────────────┐
                    │         GCS Computer                │
                    │     ┌─────────────────────┐         │
                    │     │   Custom QGC (EXE)  │         │
                    │     │  - Video Display    │         │
                    │     │  - Target Selection │         │
                    │     │  - MAVLink Control  │         │
                    │     └─────────────────────┘         │
                    └─────────────────────────────────────┘
```

## Features

- **Perception**: YOLO object detection with ByteTrack multi-object tracking
- **Target Lock**: Stable target selection and tracking across frames
- **Control**: Intent-level fixed-wing control (yaw→roll, pitch, range→thrust)
- **Safety**: Configurable limits, slew-rate, timeout failsafes
- **Bench Mode**: Thrust forced to 0 for safe hardware testing
- **MAVLink**: Full PX4 v1.16 offboard integration
- **Video**: Low-latency GStreamer UDP streaming to QGC

## Quick Start

### Prerequisites

```bash
# On Jetson Nano
sudo apt update
sudo apt install -y python3.8 python3-pip gstreamer1.0-tools
pip3 install depthai pymavlink pyzmq numpy ultralytics

# MAVProxy
pip3 install mavproxy
```

### Bench Test (Propellers Removed!)

```bash
cd vision_stack

# Set your GCS IP
export GCS_IP=192.168.1.100

# Start all components
./scripts/run_all_bench.sh
```

### Configuration

All settings are in `vision_stack/configs/`:

```yaml
# configs/modes/bench_px4_v1_16.yaml
control:
  thrust_enabled: false  # ALWAYS 0 in bench mode
  roll_limit_deg: 20.0
  pitch_limit_deg: 10.0
```

## Repository Structure

```
drone_system/
├── docs/                    # Documentation
├── deploy/                  # Systemd services, udev rules
├── vision_stack/            # Main Python package
│   ├── configs/             # YAML configuration
│   ├── scripts/             # Startup scripts
│   ├── src/                 # Source code
│   └── tests/               # Unit tests
└── esp32_firmware/          # Optional ESP32 code
```

## Safety

> ⚠️ **ALWAYS REMOVE PROPELLERS** before bench testing

- Bench mode forces `thrust = 0`
- 500ms track timeout → neutral setpoints
- Configurable roll/pitch limits
- Failsafe on telemetry loss

## License

MIT License - See [LICENSE](LICENSE)
