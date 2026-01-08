#!/bin/bash
# Run OAK bridge standalone
cd "$(dirname "$0")/.."
python3 -m src.oak.oak_bridge
