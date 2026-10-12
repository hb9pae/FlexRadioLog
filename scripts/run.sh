#!/usr/bin/env bash
set -e

# Wechsel in Projektverzeichnis
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

echo "Starte FlexRadioLog Server..."
exec "$PYTHON_EXEC" -m flexradiolog.main -c config.yaml
