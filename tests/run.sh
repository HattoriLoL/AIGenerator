#!/usr/bin/env bash
# A suíte inteira: tests/test_contrato.py e tests/test_puros.py, em qualquer Python 3.11+, sem o torch nem a placa.
# Nenhum teste gera imagem (AGENTS.md, "Testing"). Código de saída 0 quando tudo passa.
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
py="${AIGEN_PYTHON_TESTES:-python3}"
falhou=0
for teste in test_contrato.py test_puros.py; do
    echo "== $teste"
    "$py" "$RAIZ/tests/$teste" || falhou=1
done
[ "$falhou" -eq 0 ] && echo "== tudo passou" || echo "== FALHOU" >&2
exit "$falhou"
