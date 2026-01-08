#!/bin/bash
# Run video streamer
cd "$(dirname "$0")/.."
python3 -m src.main video --config-dir configs --gcs-ip "${GCS_IP:-192.168.1.100}"
