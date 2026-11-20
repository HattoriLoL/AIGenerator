#!/usr/bin/env bash
# Generates images (docs/options.md).
#     bin/aigen.sh --help
. "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
[ -n "$PY" ] || exit 2
exec "$PY" -m aigen.generate "$@"
