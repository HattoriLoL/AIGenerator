# O Python do ambiente do AIGenerator, para os lançadores (fonte: ". bin/_python.sh"). Põe em PY o Python e a raiz do
# repositório no PYTHONPATH. A ordem: a variável AIGEN_PYTHON e o .venv da raiz (o que o bin/instalar.sh cria).
# Sem nenhum, avisa e PY fica vazio: quem chamou termina com 2.
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${AIGEN_PYTHON:-}"
if [ -z "$PY" ] && [ -x "$RAIZ/.venv/bin/python" ]; then
    PY="$RAIZ/.venv/bin/python"
fi
if [ -z "$PY" ]; then
    echo "ERRO: o ambiente do AIGenerator não está instalado: rode bin/instalar.sh (ou defina AIGEN_PYTHON)" >&2
fi
export PYTHONPATH="$RAIZ${PYTHONPATH:+:$PYTHONPATH}"
