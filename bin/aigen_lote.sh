#!/usr/bin/env bash
# Gera as imagens de todos os pedidos de uma pasta (docs/opcoes.md).
#     bin/aigen_lote.sh --help
. "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
[ -n "$PY" ] || exit 2
exec "$PY" -m aigen.lote "$@"
