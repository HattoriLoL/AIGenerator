#!/usr/bin/env bash
# What the desktop shortcut runs (bin/install_shortcut.sh): if the interface is already up, it only opens the browser;
# otherwise it starts the interface in this terminal and opens the browser when it is ready. Closing the terminal
# stops the interface and frees the GPU memory.
. "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
if [ -z "$PY" ]; then
    read -r -p "Press Enter to close." _ || true
    exit 2
fi
port="$("$PY" -c "from aigen import config; print(config.read().port)" 2>/dev/null || echo 7860)"
if curl -fs -o /dev/null --max-time 2 "http://127.0.0.1:$port/"; then
    xdg-open "http://127.0.0.1:$port/" >/dev/null 2>&1
    exit 0
fi
echo "AIGenerator: the interface opens in the browser when it is ready."
echo "Close this window to stop it (and free the GPU memory)."
echo
"$PY" -m aigen.web --open "$@"
code=$?
echo
read -r -p "The interface stopped (code $code). Press Enter to close." _ || true
exit "$code"
