#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <model.onnx> <output-dir>" >&2
  exit 2
fi

MODEL="$1"
OUTPUT="$2"
mkdir -p "$OUTPUT"

cat <<'EOF'
This is an integration guide, not an SDK replacement.
Use the Hailo AI Software Suite and Dataflow Compiler version approved by the
competition environment to parse, optimize, calibrate, and compile the ONNX
model for Hailo-10H. Record the exact commands and versions in the benchmark
report. Do not commit proprietary binaries or datasets.

Typical sequence (fill in the exact tool versions you use):
  hailortc <model.onnx> \
    --format=INT8 \
    --extra-config '{"calibration": {"data": {"dataset": {"source": "folder", "folder-path": "<images>"}}}}' \
    <output-dir>/model.hef
EOF

printf 'Input model: %s\nOutput directory: %s\n' "$MODEL" "$OUTPUT"
printf 'Next: build HailoModel("<output>/model.hef") in a target env with the Hailo driver installed.\n'
