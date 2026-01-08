#!/bin/bash
# Run control node
cd "$(dirname "$0")/.."
python3 -m src.main control --config-dir configs --mode "${MODE:-bench_px4_v1_16}"
