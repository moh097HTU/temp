# Ports and Endpoints

Reference for all network ports and serial connections.

## Serial Ports

| Port | Device | Baudrate | Purpose |
|------|--------|----------|---------|
| `/dev/ttyTHS1` | FC TELEM1 | 57600 | MAVLink to/from FC |

### TELEM1 Wiring

```
Orange Cube TELEM1          Jetson Nano
─────────────────          ──────────────
Pin 2 (TX)  ──────────────► Pin 10 (UART RX)
Pin 3 (RX)  ◄────────────── Pin 8  (UART TX)
Pin 6 (GND) ──────────────► Pin 6  (GND)
```

⚠️ **Voltage**: TELEM1 is 3.3V, compatible with Jetson GPIO.

## UDP Ports

| Port | Direction | Source | Destination | Purpose |
|------|-----------|--------|-------------|---------|
| 14550 | Out | MAVProxy | GCS | MAVLink to QGC |
| 14551 | In | MAVProxy | Jetson apps | MAVLink local |
| 5600 | Out | Jetson | GCS | Video stream (RTP) |

## ZMQ Ports (Internal to Jetson)

| Port | Publisher | Topic(s) |
|------|-----------|----------|
| 5550 | oak_bridge | frames |
| 5551 | perception | tracks |
| 5552 | targeting | lock_state, errors |
| 5553 | control | setpoints |
| 5554 | mavlink_bridge | qgc_cmds, telemetry |
| 5555 | esp32_gpio | battery_state |

All ZMQ uses `tcp://localhost:PORT`.

## GPIO Pins (ESP32 → Jetson)

| Signal | Jetson Pin | BCM GPIO |
|--------|------------|----------|
| BAT1_ACTIVE | 11 | 17 |
| BAT2_ACTIVE | 12 | 18 |
| GND | 6 | - |

## Quick Reference

### Environment Variables

```bash
export GCS_IP=192.168.1.100
export MODE=bench_px4_v1_16
export SERIAL_PORT=/dev/ttyTHS1
export BAUDRATE=57600
```

### Test Commands

```bash
# Serial test
screen /dev/ttyTHS1 57600

# MAVLink test
mavproxy.py --master=/dev/ttyTHS1 --baudrate=57600

# Video receive (on GCS)
gst-launch-1.0 udpsrc port=5600 ! \
  application/x-rtp,payload=96 ! \
  rtph264depay ! avdec_h264 ! autovideosink
```
