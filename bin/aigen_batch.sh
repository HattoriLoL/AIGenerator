#!/usr/bin/env bash
# Generates the images of every request in a folder (docs/options.md).
#     bin/aigen_batch.sh --help
. "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
[ -n "$PY" ] || exit 2
exec "$PY" -m aigen.batch "$@"
