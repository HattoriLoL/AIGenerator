#!/usr/bin/env bash
# Baixa os dois modelos auxiliares para as pastas padrão do config.ini (os dois com licença para uso comercial):
#   - o upscaler RealESRGAN_x4plus_anime_6B (BSD-3-Clause) para o hires fix;
#   - a cascata lbpcascade_animeface (MIT) para a correção de rosto.
# Um arquivo que já existe não é baixado de novo. O checkpoint (o Pony) não: docs/instalacao.md.
set -eu
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
baixar() {
    destino="$RAIZ/$1"; url="$2"
    if [ -f "$destino" ]; then echo "já existe: $1"; return; fi
    mkdir -p "$(dirname "$destino")"
    curl -fsSL --retry 3 -o "$destino.parcial" "$url" && mv "$destino.parcial" "$destino" && echo "baixado: $1"
}
baixar models/upscalers/RealESRGAN_x4plus_anime_6B.pth \
    https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth
baixar models/detectors/lbpcascade_animeface.xml \
    https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/lbpcascade_animeface.xml
