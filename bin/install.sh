#!/usr/bin/env bash
# Installs the AIGenerator environment in the root's .venv, with uv (https://docs.astral.sh/uv/): Python 3.12 and
# PyTorch for CUDA 12.8 (what RTX 50 cards need). Creates the model folders. Downloads no model: see
# docs/installation.md (and bin/download_extras.sh for the upscaler and the face detector).
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is not installed: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 2
fi
cd "$ROOT"
uv sync
mkdir -p models/checkpoints models/loras models/upscalers models/detectors characters output
"$ROOT/.venv/bin/python" -c "import torch; print('torch', torch.__version__, '| CUDA:', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no GPU')"
echo "Done. The checkpoint is still missing: docs/installation.md"
