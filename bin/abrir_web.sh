#!/usr/bin/env bash
# O que o atalho da área de trabalho roda (bin/instalar_atalho.sh): se a interface já está no ar, só abre o navegador;
# senão, sobe a interface neste terminal e abre o navegador quando ela fica pronta. Fechar o terminal desliga a
# interface e solta a memória da placa.
. "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
if [ -z "$PY" ]; then
    read -r -p "Enter para fechar." _ || true
    exit 2
fi
porta="$("$PY" -c "from aigen import config; print(config.ler().porta)" 2>/dev/null || echo 7860)"
if curl -fs -o /dev/null --max-time 2 "http://127.0.0.1:$porta/"; then
    xdg-open "http://127.0.0.1:$porta/" >/dev/null 2>&1
    exit 0
fi
echo "AIGenerator: a interface abre no navegador quando estiver pronta."
echo "Feche esta janela para desligar (e soltar a memória da placa de vídeo)."
echo
"$PY" -m aigen.web --abrir "$@"
codigo=$?
echo
read -r -p "A interface parou (código $codigo). Enter para fechar." _ || true
exit "$codigo"
