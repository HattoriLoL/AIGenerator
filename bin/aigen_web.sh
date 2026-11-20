#!/usr/bin/env bash
# A interface web, em http://127.0.0.1:7860 (docs/web.md).
#     bin/aigen_web.sh --help
. "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
[ -n "$PY" ] || exit 2
exec "$PY" -m aigen.web "$@"
