#!/bin/bash
# Run targeting node
cd "$(dirname "$0")/.."
python3 -m src.main targeting --config-dir configs --mode "${MODE:-bench_px4_v1_16}"
