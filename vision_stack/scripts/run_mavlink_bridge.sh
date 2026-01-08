#!/bin/bash
# Run MAVLink bridge
cd "$(dirname "$0")/.."
python3 -m src.main mavlink --config-dir configs --mode "${MODE:-bench_px4_v1_16}"
