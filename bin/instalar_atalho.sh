#!/usr/bin/env bash
# Cria o atalho "AIGenerator" no menu de aplicativos (Linux, padrão freedesktop: GNOME, KDE, ...), que roda o
# bin/abrir_web.sh num terminal. O atalho guarda o caminho deste clone, por isso é gerado aqui e não é versionado.
#     bin/instalar_atalho.sh [icone.svg|icone.png]       (sem ícone: o ícone de gráficos do sistema)
#     bin/instalar_atalho.sh --remover
set -eu
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASTA="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ATALHO="$PASTA/aigenerator.desktop"
if [ "${1:-}" = "--remover" ]; then
    rm -f "$ATALHO" && echo "removido: $ATALHO"
    exit 0
fi
icone="applications-graphics"
if [ -n "${1:-}" ]; then
    [ -f "$1" ] || { echo "ERRO: ícone não encontrado: $1" >&2; exit 2; }
    icone="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
fi
mkdir -p "$PASTA"
cat > "$ATALHO" <<FIM
[Desktop Entry]
Type=Application
Name=AIGenerator
Comment=Personagens de anime com o Pony Diffusion XL (interface web local)
Exec="$RAIZ/bin/abrir_web.sh"
Path=$RAIZ
Icon=$icone
Terminal=true
Categories=Graphics;
StartupNotify=false
FIM
chmod +x "$ATALHO"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$PASTA" >/dev/null 2>&1 || true
echo "atalho criado: $ATALHO"
echo "Procure \"AIGenerator\" no menu de aplicativos; para a barra lateral: botão direito > Fixar no Dash."
