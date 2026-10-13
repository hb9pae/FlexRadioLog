#!/usr/bin/env bash
set -e

# Argumente verarbeiten
AUTO_INSTALL_SERVICES=false
for arg in "$@"; do
    case "$arg" in
        --install-services|-s)
            AUTO_INSTALL_SERVICES=true
            ;;
        --help|-h)
            echo "Verwendung: $0 [OPTIONEN]"
            echo "Optionen:"
            echo "  --install-services, -s   Installiert, aktiviert und startet die Systemd-Dienste direkt"
            echo "  --help, -h               Zeigt diese Hilfe an"
            exit 0
            ;;
    esac
done

# In das Projekt-Stammverzeichnis wechseln
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"
PROJECT_DIR="$SCRIPT_DIR"

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

# Ziel-Benutzer und -Gruppe für den Dienstlauf ermitteln
if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    TARGET_USER="$SUDO_USER"
elif [ -n "$USER" ] && [ "$USER" != "root" ]; then
    TARGET_USER="$USER"
elif id -u pi >/dev/null 2>&1; then
    TARGET_USER="pi"
else
    TARGET_USER="$(id -un)"
fi
TARGET_GROUP="$(id -gn "$TARGET_USER" 2>/dev/null || echo "$TARGET_USER")"

echo ""
echo "=== Dateiberechtigungen & Benutzerkonfiguration ==="
echo "Dienst-Benutzer: $TARGET_USER (Gruppe: $TARGET_GROUP)"
echo "Projektpfad:     $PROJECT_DIR"

# Berechtigungen für das gesamte Projektverzeichnis anpassen (verhindert PermissionError bei Logs und DB)
if [ "$(id -u)" -eq 0 ]; then
    echo "Passe Eigentümer und Berechtigungen auf $TARGET_USER:$TARGET_GROUP an..."
    chown -R "$TARGET_USER:$TARGET_GROUP" "$PROJECT_DIR"
    chmod -R u+rwX,g+rX "$PROJECT_DIR"
else
    NEED_CHOWN=false
    if [ ! -w "$PROJECT_DIR" ]; then
        NEED_CHOWN=true
    fi
    for check_file in "$PROJECT_DIR/flexradiolog.log" "$PROJECT_DIR/flexradiolog.db" "$PROJECT_DIR/config.yaml"; do
        if [ -e "$check_file" ] && [ ! -w "$check_file" ]; then
            NEED_CHOWN=true
        fi
    done

    if [ "$NEED_CHOWN" = true ]; then
        if command -v sudo >/dev/null 2>&1; then
            echo "Schreibrechte im Projektverzeichnis fehlen. Korrigiere Eigentümer mittels sudo..."
            sudo chown -R "$TARGET_USER:$TARGET_GROUP" "$PROJECT_DIR"
            sudo chmod -R u+rwX,g+rX "$PROJECT_DIR"
        else
            echo "Warnung: Fehlende Schreibrechte in $PROJECT_DIR und 'sudo' ist nicht verfügbar."
        fi
    else
        chmod -R u+rwX,g+rX "$PROJECT_DIR" 2>/dev/null || true
    fi
fi

# Stelle sicher, dass vorhandene Log- und DB-Dateien beschreibbar sind
[ -f "$PROJECT_DIR/flexradiolog.log" ] && chmod 664 "$PROJECT_DIR/flexradiolog.log" 2>/dev/null || true
[ -f "$PROJECT_DIR/flexradiolog.db" ] && chmod 664 "$PROJECT_DIR/flexradiolog.db" 2>/dev/null || true

# Systemd-Service-Dateien dynamisch anpassen
echo "Passe Systemd-Service-Vorlagen für Benutzer '$TARGET_USER' und Pfad '$PROJECT_DIR' an..."
$PYTHON_BIN - <<EOF
import re
from pathlib import Path

services = [
    Path("$PROJECT_DIR/scripts/flexradiolog.service"),
    Path("$PROJECT_DIR/scripts/loggui.service"),
]
target_user = "$TARGET_USER"
project_dir = "$PROJECT_DIR"

for path in services:
    if not path.is_file():
        continue
    content = path.read_text(encoding="utf-8")

    # User anpassen
    content = re.sub(r"^User=.*$", f"User={target_user}", content, flags=re.MULTILINE)

    # WorkingDirectory anpassen
    content = re.sub(r"^WorkingDirectory=.*$", f"WorkingDirectory={project_dir}", content, flags=re.MULTILINE)

    # Pfade in ExecStart anpassen
    content = re.sub(r"/opt/FlexRadioLog", project_dir, content)

    # ReadWritePaths setzen/aktualisieren
    if re.search(r"^ReadWritePaths=.*$", content, flags=re.MULTILINE):
        content = re.sub(r"^ReadWritePaths=.*$", f"ReadWritePaths={project_dir}", content, flags=re.MULTILINE)
    else:
        content = re.sub(r"(PrivateTmp=true)", rf"\1\nReadWritePaths={project_dir}", content)

    # Falls das Projekt unter /home liegt, ProtectHome=read-only abschalten
    if project_dir.startswith("/home/"):
        content = re.sub(r"^ProtectHome=.*$", "ProtectHome=false", content, flags=re.MULTILINE)

    path.write_text(content, encoding="utf-8")
print("Service-Dateien erfolgreich aktualisiert.")
EOF

echo ""
echo "=== Installation erfolgreich! ==="
echo "Manueller Start:"
echo "  Backend API:  ./scripts/run.sh"
echo "  Web Frontend: ./scripts/run_loggui.sh"
echo ""

# Prüfe, ob systemd auf dem System aktiv ist
HAS_SYSTEMD=false
if command -v systemctl >/dev/null 2>&1 && [ -d "/etc/systemd/system" ]; then
    HAS_SYSTEMD=true
fi

DO_INSTALL_SERVICES="$AUTO_INSTALL_SERVICES"

if [ "$HAS_SYSTEMD" = true ] && [ "$DO_INSTALL_SERVICES" = false ] && [ -t 0 ]; then
    echo "Systemd wurde erkannt."
    read -r -p "Möchtest du die Systemd-Dienste jetzt einrichten, aktivieren und starten? [j/N]: " USER_ANSWER
    case "$USER_ANSWER" in
        [jJyY]*)
            DO_INSTALL_SERVICES=true
            ;;
    esac
fi

if [ "$DO_INSTALL_SERVICES" = true ]; then
    echo ""
    echo "Richte Systemd-Dienste ein..."
    SUDO_PREFIX=""
    if [ "$(id -u)" -ne 0 ]; then
        SUDO_PREFIX="sudo"
    fi

    $SUDO_PREFIX cp "$PROJECT_DIR/scripts/flexradiolog.service" "$PROJECT_DIR/scripts/loggui.service" /etc/systemd/system/
    $SUDO_PREFIX systemctl daemon-reload
    $SUDO_PREFIX systemctl enable flexradiolog.service loggui.service
    $SUDO_PREFIX systemctl restart flexradiolog.service loggui.service
    echo "Dienste wurden installiert, aktiviert und gestartet!"
    echo ""
    echo "Statusprüfung:"
    $SUDO_PREFIX systemctl --no-pager status flexradiolog.service loggui.service || true
else
    echo "Einrichtung als Systemd-Dienste (Autostart beim Booten):"
    echo "  sudo cp scripts/flexradiolog.service scripts/loggui.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable flexradiolog loggui"
    echo "  sudo systemctl restart flexradiolog loggui"
    echo ""
    echo "Status und Logs prüfen:"
    echo "  sudo systemctl status flexradiolog loggui"
    echo "  journalctl -u flexradiolog -f"
fi
