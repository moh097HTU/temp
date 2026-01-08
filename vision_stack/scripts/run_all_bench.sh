#!/bin/bash
# Run all vision stack components in bench mode
# Usage: ./run_all_bench.sh [GCS_IP]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../configs"
GCS_IP="${1:-${GCS_IP:-192.168.1.100}}"

export GCS_IP
export MODE="bench_px4_v1_16"
export PYTHONPATH="${SCRIPT_DIR}/.."

echo "=============================================="
echo "  DRONE VISION STACK - BENCH MODE"
echo "=============================================="
echo ""
echo "  GCS IP: ${GCS_IP}"
echo "  Mode: ${MODE}"
echo ""
echo "  ⚠️  WARNING: REMOVE PROPELLERS BEFORE TESTING"
echo ""
echo "=============================================="
echo ""

# Start MAVProxy first
echo "[1/7] Starting MAVProxy..."
"${SCRIPT_DIR}/run_mavproxy.sh" "${GCS_IP}" &
sleep 2

# Start vision stack components
echo "[2/7] Starting perception..."
python3 -m src.main perception --config-dir "${CONFIG_DIR}" --mode "${MODE}" &
sleep 1

echo "[3/7] Starting targeting..."
python3 -m src.main targeting --config-dir "${CONFIG_DIR}" --mode "${MODE}" &
sleep 1

echo "[4/7] Starting control..."
python3 -m src.main control --config-dir "${CONFIG_DIR}" --mode "${MODE}" &
sleep 1

echo "[5/7] Starting MAVLink bridge..."
python3 -m src.main mavlink --config-dir "${CONFIG_DIR}" --mode "${MODE}" &
sleep 1

echo "[6/7] Starting video streamer..."
python3 -m src.main video --config-dir "${CONFIG_DIR}" --gcs-ip "${GCS_IP}" &
sleep 1

echo "[7/7] Starting ESP32 GPIO bridge..."
python3 -m src.main gpio --config-dir "${CONFIG_DIR}" &

echo ""
echo "=============================================="
echo "  All components started!"
echo "  Press Ctrl+C to stop all"
echo "=============================================="

# Wait for any child to exit
wait
