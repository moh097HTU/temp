#!/bin/bash
# Run ESP32 GPIO bridge
cd "$(dirname "$0")/.."
python3 -m src.main gpio --config-dir configs
