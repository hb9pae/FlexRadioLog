#!/usr/bin/env bash
set -e

# In das Projekt-Stammverzeichnis wechseln
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "=== FlexRadioLog & LogGui Installation für Raspberry Pi ==="

# Prüfe Python Version
PYTHON_BIN=$(command -v python3 || true)
if [ -z "$PYTHON_BIN" ]; then
    echo "Fehler: python3 wurde nicht gefunden!"
    echo "Bitte installieren: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

echo "Verwende Python: $PYTHON_BIN"

# Prüfe Mindestversion Python >= 3.11
if ! $PYTHON_BIN -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
    PY_VER=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "unbekannt")
    echo "Fehler: FlexRadioLog benötigt mindestens Python 3.11 (Gefunden: $PY_VER)."
    echo "Auf älteren Raspberry Pi OS Versionen (z. B. Bullseye) bitte auf Bookworm aktualisieren."
    exit 1
fi

# Prüfe ob python3-venv / ensurepip vorhanden ist (wird auf Debian/Raspberry Pi oft separat benötigt)
if ! $PYTHON_BIN -c "import ensurepip" >/dev/null 2>&1; then
    echo "Fehler: Das Python-Modul 'ensurepip' (bzw. python3-venv) ist nicht verfügbar."
    echo "Auf Debian / Raspberry Pi OS muss das Paket 'python3-venv' installiert werden:"
    echo ""
    echo "  sudo apt update && sudo apt install -y python3-venv python3-pip"
    echo ""
    exit 1
fi

# Prüfe bestehende .venv: Falls unvollständig oder von anderer Architektur kopiert -> aufräumen
if [ -d ".venv" ]; then
    if [ ! -f ".venv/bin/python" ] || ! .venv/bin/python -c "import sys" >/dev/null 2>&1 || ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
        echo "Bestehende .venv ist ungültig, unvollständig oder stammt von einem anderen System (z. B. Mac)."
        echo "Bereinige fehlerhafte .venv und erstelle sie neu..."
        rm -rf .venv
    fi
fi

# Virtuelle Umgebung anlegen falls nicht vorhanden
if [ ! -d ".venv" ]; then
    echo "Erstelle virtuelle Umgebung .venv..."
    if ! $PYTHON_BIN -m venv .venv; then
        echo ""
        echo "Fehler beim Erstellen der virtuellen Umgebung!"
        echo "Bitte sicherstellen, dass python3-venv installiert ist:"
        echo "  sudo apt update && sudo apt install -y python3-venv python3-pip"
        echo ""
        rm -rf .venv
        exit 1
    fi
fi

echo "Aktualisiere pip und installiere Abhängigkeiten..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

# Frontend (LogGui) bauen falls npm vorhanden
if command -v npm >/dev/null 2>&1; then
    echo "Baue LogGui Web-Frontend..."
    (cd loggui && npm install && npm run build)
else
    if [ -d "loggui/dist" ] && [ -f "loggui/dist/index.html" ]; then
        echo "npm nicht gefunden, aber vorkompiliertes loggui/dist ist vorhanden."
    else
        echo "Hinweis: npm nicht gefunden und loggui/dist fehlt."
        echo "Für das Web-Frontend (LogGui) bitte Node.js installieren:"
        echo "  sudo apt update && sudo apt install -y nodejs npm"
        echo "oder 'loggui/dist' vorab bereitstellen."
    fi
fi

# Konfigurationsdatei prüfen
if [ ! -f "config.yaml" ]; then
    echo "Erstelle Standard config.yaml..."
    cat <<EOF > config.yaml
radio:
  host: "192.168.84.24"
  port: 4992
  reconnect_interval_sec: 3.0
  reconnect_max_backoff_sec: 30.0
  timeout_sec: 10.0

database:
  url: "sqlite+aiosqlite:///flexradiolog.db"
  echo: false

api:
  host: "0.0.0.0"
  port: 8000
  title: "FlexRadioLog API"

logging:
  level: "INFO"
  file_path: "flexradiolog.log"

initial_allocations:
  - ip_address: "192.168.84.100"
    callsign: "HB9XYZ"
    operator_name: "Operator Shack"
    notes: "Hauptplatz"
EOF
fi

PROJECT_DIR="$SCRIPT_DIR"

echo ""
echo "=== Installation erfolgreich! ==="
echo "Manueller Start:"
echo "  Backend API:  ./scripts/run.sh"
echo "  Web Frontend: ./scripts/run_loggui.sh"
echo ""
echo "Einrichtung als Systemd-Dienste (Autostart beim Booten auf Raspberry Pi):"
if [ "$PROJECT_DIR" != "/opt/FlexRadioLog" ]; then
    echo "Hinweis: Das Projekt befindet sich in '$PROJECT_DIR' (Dienstdateien erwarten standardmäßig '/opt/FlexRadioLog')."
    echo "Option A (Empfohlen): Verschieben nach /opt/FlexRadioLog:"
    echo "  sudo mkdir -p /opt && sudo mv \"$PROJECT_DIR\" /opt/FlexRadioLog"
    echo "Option B: Pfad in den Service-Dateien anpassen:"
    echo "  sed -i 's|/opt/FlexRadioLog|$PROJECT_DIR|g' scripts/*.service"
    echo ""
fi
echo "  sudo cp scripts/flexradiolog.service scripts/loggui.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable flexradiolog loggui"
echo "  sudo systemctl start flexradiolog loggui"
echo "  sudo systemctl status flexradiolog loggui"
