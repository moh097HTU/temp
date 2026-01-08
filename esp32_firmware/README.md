# ESP32 Battery Switch Firmware

Simple firmware for ESP32 to read battery switch status and output to Jetson GPIO.

## Hardware Setup

```
┌─────────────────┐
│     ESP32       │
│                 │
│  GPIO26 ◄───────┼─── Battery 1 switch
│  GPIO27 ◄───────┼─── Battery 2 switch
│                 │
│  GPIO32 ────────┼───► Jetson GPIO 17 (BAT1_ACTIVE)
│  GPIO33 ────────┼───► Jetson GPIO 18 (BAT2_ACTIVE)
│                 │
│  GND ───────────┼─── Common ground
└─────────────────┘
```

## Flashing

1. Install PlatformIO or Arduino IDE
2. Connect ESP32 via USB
3. Flash `src/main.cpp`

## Operation

- Reads battery switch inputs at 50 Hz
- Outputs debounced status to Jetson GPIO
- Active-high output (HIGH = battery active)
