#!/usr/bin/env bash
# Installs AIGenerator on Linux with one command (docs/installation.md):
#     ./setup.sh [--no-models] [--no-shortcut] [--verify] [--no-gpu-check] [--icon FILE] [--remove-shortcut]
# Safe to run again: it skips what is already done and never overwrites your files. The steps:
#   1. the NVIDIA GPU check (nvidia-smi);
#   2. uv, installed with its official installer when it is missing;
#   3. "uv sync": the environment in .venv (Python 3.12 and PyTorch for CUDA 12.8, from pyproject.toml);
#   4. "python -m aigen.install" with that Python: the folders, the models, config.local.ini and the shortcut.
# The same options as setup.bat (Windows). Exit code: 0 done, 1 a step failed, 2 a wrong option or no NVIDIA GPU.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USAGE="usage: ./setup.sh [--no-models] [--no-shortcut] [--verify] [--no-gpu-check] [--icon FILE] [--remove-shortcut]"
HELP="  --no-models        do not download the models
  --no-shortcut      do not create the shortcut
  --verify           check the SHA256 of the models already in place too
  --no-gpu-check     continue without an NVIDIA GPU
  --icon FILE        the shortcut's icon (.svg or .png)
  --remove-shortcut  only remove the shortcut, and stop"

gpu_check=1
remove=0
args=("$@")
while [ $# -gt 0 ]; do
    case "$1" in
        --no-gpu-check) gpu_check=0 ;;
        --remove-shortcut) remove=1 ;;
        --no-models|--no-shortcut|--verify|--icon=*) ;;
        --icon) [ $# -ge 2 ] || { echo "ERROR: --icon needs a file" >&2; exit 2; }; shift ;;
        -h|--help) echo "$USAGE"; echo "$HELP"; exit 0 ;;
        *) echo "$USAGE" >&2; echo "ERROR: unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

find_uv() {
    command -v uv && return 0
    for c in "${UV_INSTALL_DIR:+$UV_INSTALL_DIR/uv}" "${XDG_BIN_HOME:+$XDG_BIN_HOME/uv}" "$HOME/.local/bin/uv" \
             "$HOME/.cargo/bin/uv"; do
        if [ -n "$c" ] && [ -x "$c" ]; then echo "$c"; return 0; fi
    done
    return 1
}

if [ "$remove" = 0 ]; then
    if [ "$gpu_check" = 1 ]; then
        if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
            echo "ERROR: no NVIDIA GPU found (nvidia-smi is missing or did not answer). AIGenerator needs an NVIDIA" \
                 "GPU with its driver installed. To install anyway: ./setup.sh --no-gpu-check" >&2
            exit 2
        fi
        echo "== NVIDIA GPU: $(nvidia-smi -L | head -n 1)"
    fi

    if ! UV="$(find_uv)"; then
        echo "== Installing uv (https://docs.astral.sh/uv/)"
        if command -v curl >/dev/null 2>&1; then
            curl -LsSf https://astral.sh/uv/install.sh | sh || true
        elif command -v wget >/dev/null 2>&1; then
            wget -qO- https://astral.sh/uv/install.sh | sh || true
        fi
        if ! UV="$(find_uv)"; then
            echo "ERROR: uv could not be installed (it needs curl or wget). Install it by hand" \
                 "(https://docs.astral.sh/uv/getting-started/installation/) and run ./setup.sh again" >&2
            exit 1
        fi
    fi
    echo "== uv: $UV"

    echo "== The environment (uv sync: Python 3.12 and PyTorch for CUDA 12.8; a few GB the first time)"
    if ! (cd "$ROOT" && "$UV" sync); then
        echo "ERROR: \"uv sync\" failed: see the messages above, then run ./setup.sh again" >&2
        exit 1
    fi
fi

echo "== Folders, models, configuration and shortcut"
. "$ROOT/bin/_python.sh"
[ -n "$PY" ] || exit 2
exec "$PY" -m aigen.install ${args[@]+"${args[@]}"}
