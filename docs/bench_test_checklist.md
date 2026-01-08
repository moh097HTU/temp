# Bench Test Checklist

Pre-flight bench test procedures for validating the vision-guidance system.

## ⚠️ Safety First

- [ ] **REMOVE ALL PROPELLERS** before any testing
- [ ] Secure aircraft to prevent movement
- [ ] Have RC transmitter ready for manual override
- [ ] Clear area around control surfaces

## Hardware Setup

### 1. Power and Connections

- [ ] Battery connected to FC
- [ ] Jetson Nano powered (separate supply recommended)
- [ ] OAK-D Lite connected via USB3
- [ ] ESP32 GPIO signals connected to Jetson pins 17/18
- [ ] TELEM1 connected: FC → Jetson `/dev/ttyTHS1`
- [ ] Network cable/WiFi between Jetson and GCS PC

### 2. Verify Connections

```bash
# On Jetson
ls -la /dev/ttyTHS1  # Should exist
lsusb | grep -i luxonis  # OAK-D should appear
```

## Software Startup

### 3. Start MAVProxy

```bash
cd ~/drone_system/vision_stack
./scripts/run_mavproxy.sh 192.168.1.100  # Replace with GCS IP
```

Expected output:
- "link 1 OK" - serial connected
- Heartbeats received

### 4. Start Vision Stack

```bash
export GCS_IP=192.168.1.100
./scripts/run_all_bench.sh
```

### 5. Open QGC

- Launch custom QGC on GCS PC
- Verify video stream displays
- Verify MAVLink telemetry received

## Functional Tests

### Test 1: Perception → Track List

- [ ] Point camera at target objects
- [ ] Verify tracks appear in QGC overlay
- [ ] Move objects, verify stable track IDs

### Test 2: Target Selection

| Action | Expected Result |
|--------|-----------------|
| Click on target in QGC | Lock indicator shows locked |
| Target moves left | Right aileron rises (bank right) |
| Target moves right | Left aileron rises (bank left) |
| Target moves up | Elevator moves up |
| Target moves down | Elevator moves down |

### Test 3: Failsafe

| Action | Expected Result |
|--------|-----------------|
| Cover camera lens | Surfaces return to neutral within 500ms |
| Disconnect TELEM1 | Surfaces return to neutral within 1s |
| Clear lock in QGC | Surfaces return to neutral |

### Test 4: Battery Signal

- [ ] Switch to BAT1 → QGC shows BAT1 active
- [ ] Switch to BAT2 → QGC shows BAT2 active

## Verification Criteria

✅ **PASS** if:
- Control surfaces respond correctly to target position
- Neutral setpoints sent when lock lost
- Thrust remains 0 throughout (bench mode)
- Video stream stable at target FPS
- Battery status updates in QGC

❌ **FAIL** if:
- Any thrust command > 0
- Control surfaces don't move
- Surfaces don't return to neutral on failsafe
- Erratic/oscillating movements

## Post-Test

- [ ] Stop all processes: `Ctrl+C` on run_all_bench.sh
- [ ] Review logs: `/var/log/mavproxy.log`
- [ ] Document any issues
- [ ] DO NOT attach propellers until flight mode testing
