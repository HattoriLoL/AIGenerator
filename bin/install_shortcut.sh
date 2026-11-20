#!/usr/bin/env bash
# Creates the "AIGenerator" shortcut in the application menu (Linux, freedesktop standard: GNOME, KDE, ...), which runs
# bin/open_web.sh in a terminal. The shortcut stores the path of this clone, so it is generated here and not versioned.
#     bin/install_shortcut.sh [icon.svg|icon.png]       (without an icon: the system's graphics icon)
#     bin/install_shortcut.sh --remove
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FOLDER="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
SHORTCUT="$FOLDER/aigenerator.desktop"
if [ "${1:-}" = "--remove" ]; then
    rm -f "$SHORTCUT" && echo "removed: $SHORTCUT"
    exit 0
fi
icon="applications-graphics"
if [ -n "${1:-}" ]; then
    [ -f "$1" ] || { echo "ERROR: icon not found: $1" >&2; exit 2; }
    icon="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
fi
mkdir -p "$FOLDER"
cat > "$SHORTCUT" <<END
[Desktop Entry]
Type=Application
Name=AIGenerator
Comment=Anime characters with Pony Diffusion XL (local web interface)
Exec="$ROOT/bin/open_web.sh"
Path=$ROOT
Icon=$icon
Terminal=true
Categories=Graphics;
StartupNotify=false
END
chmod +x "$SHORTCUT"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$FOLDER" >/dev/null 2>&1 || true
echo "shortcut created: $SHORTCUT"
echo "Look for \"AIGenerator\" in the application menu; for the dock: right click > Pin to Dash."
