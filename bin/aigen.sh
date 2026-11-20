#!/usr/bin/env bash
# Gera imagens (docs/opcoes.md).
#     bin/aigen.sh --help
. "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
[ -n "$PY" ] || exit 2
exec "$PY" -m aigen.gerar "$@"
