# The Python of the AIGenerator environment, for the launchers (source it: ". bin/_python.sh"). Sets PY to the Python
# and puts the repository root on PYTHONPATH. The order: the AIGEN_PYTHON variable and the root's .venv (the one
# bin/install.sh creates). With neither, it warns and PY stays empty: the caller ends with 2.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${AIGEN_PYTHON:-}"
if [ -z "$PY" ] && [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
fi
if [ -z "$PY" ]; then
    echo "ERROR: the AIGenerator environment is not installed: run bin/install.sh (or set AIGEN_PYTHON)" >&2
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
