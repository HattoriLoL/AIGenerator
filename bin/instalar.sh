#!/usr/bin/env bash
# Instala o ambiente do AIGenerator no .venv da raiz, com o uv (https://docs.astral.sh/uv/): Python 3.12 e o PyTorch
# para CUDA 12.8 (o que as placas RTX 50 pedem). Cria as pastas dos modelos. Não baixa nenhum modelo: veja
# docs/instalacao.md (e bin/baixar_auxiliares.sh para o upscaler e o detector de rosto).
set -eu
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v uv >/dev/null 2>&1; then
    echo "ERRO: o uv não está instalado: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 2
fi
cd "$RAIZ"
uv sync
mkdir -p models/checkpoints models/loras models/upscalers models/detectors personagens saida
"$RAIZ/.venv/bin/python" -c "import torch; print('torch', torch.__version__, '| CUDA:', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'sem placa')"
echo "Pronto. Falta o checkpoint: docs/instalacao.md"
