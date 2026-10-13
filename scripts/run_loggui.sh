#!/usr/bin/env bash
set -e

# Wechsel in Projektverzeichnis
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

LOGGUI_DIST_DIR="$SCRIPT_DIR/loggui/dist"

# Prüfe, ob das Frontend bereits gebaut wurde
if [ ! -d "$LOGGUI_DIST_DIR" ] || [ ! -f "$LOGGUI_DIST_DIR/index.html" ]; then
    echo "LogGui dist/ nicht gefunden. Baue Frontend..."
    if command -v npm >/dev/null 2>&1; then
        cd "$SCRIPT_DIR/loggui"
        npm install
        npm run build
        cd "$SCRIPT_DIR"
    else
        echo "Fehler: $LOGGUI_DIST_DIR existiert nicht und npm ist nicht installiert."
        echo "Bitte LogGui vorab bauen (npm run build) oder npm installieren."
        exit 1
    fi
fi

PORT=8080
echo "Starte LogGui Webserver auf Port $PORT (Verzeichnis: $LOGGUI_DIST_DIR)..."
echo "Zugriff über Browser: http://<raspberry-pi-ip>:$PORT"

# Verwende Python 3 http.server zur Bereitstellung der statischen SPA
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

exec "$PYTHON_EXEC" -m http.server "$PORT" --directory "$LOGGUI_DIST_DIR" --bind 0.0.0.0
