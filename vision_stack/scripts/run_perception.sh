#!/bin/bash
# Run perception node
cd "$(dirname "$0")/.."
python3 -m src.main perception --config-dir configs --mode "${MODE:-bench_px4_v1_16}"
