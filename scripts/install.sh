#!/usr/bin/env bash
set -e

echo "=== FlexRadioLog Installation für Raspberry Pi ==="

# Prüfe Python Version
PYTHON_BIN=$(which python3)
if [ -z "$PYTHON_BIN" ]; then
    echo "Fehler: python3 nicht gefunden! Bitte installieren: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

echo "Verwende Python: $PYTHON_BIN"

# Virtuelle Umgebung anlegen falls nicht vorhanden
if [ ! -d ".venv" ]; then
    echo "Erstelle virtuelle Umgebung .venv..."
    $PYTHON_BIN -m venv .venv
fi

echo "Aktualisiere pip und installiere Abhängigkeiten..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .

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

echo ""
echo "=== Installation erfolgreich! ==="
echo "Manueller Start:"
echo "  ./scripts/run.sh"
echo ""
echo "Einrichtung als Systemd-Dienst (Autostart beim Booten):"
echo "  sudo cp scripts/flexradiolog.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable flexradiolog"
echo "  sudo systemctl start flexradiolog"
echo "  sudo systemctl status flexradiolog"
