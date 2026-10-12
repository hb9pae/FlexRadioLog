# FlexRadioLog

Autarker Monitoring- und Logging-Server für **FlexRadio 6400** (SmartSDR TCP-API) auf einem **Raspberry Pi**.

---

## 🚀 Übersicht & Funktionen

- **Benutzer- & Sitzungs-Monitoring:**
  - Automatische Erkennung bei Verbindungsaufbau und Verbindungsabbruch von Benutzern (SmartSDR Windows, iOS, MacOS, Maestro).
  - Exakte Erfassung der Sitzungsdauer (Login -> Logout).
- **IP-zu-Rufzeichen-Zuordnung:**
  - Automatische Identifikation des Funkamateurs über eine konfigurierbare IP-Allocations-Tabelle (mit Fallback auf gemeldeten Stationsnamen).
- **Detailliertes PTT- & Frequenz-Logging:**
  - Jede PTT-Tastung wird als Einzelereignis mit Startzeitstempel, Endzeitstempel, Sendedauer in Sekunden, Sendefrequenz (in Hz), Amateurfunkband (z. B. 20m, 40m, 80m) und Betriebsart (z. B. USB, FT8, CW) erfasst.
- **Leichtgewichtige Persistenz:**
  - Transaktionssichere SQLite-Datenbank (`flexradiolog.db`) mit automatischer Bereinigung verwaister Sitzungen bei Stromausfall / Radio-Neustart.
- **REST-API für Visualisierung:**
  - Schnelle FastAPI-Schnittstelle mit interaktiver Swagger-Dokumentation unter `http://<IP>:8000/docs`.
- **24/7 Hintergrundbetrieb:**
  - Robuster Reconnect-Mechanismus bei Netzwerkunterbrechung oder ausgeschaltetem FlexRadio.
  - Vorkonfigurierte `systemd`-Service-Unit für Linux/Raspberry Pi OS.

---

## 🛠️ Systemarchitektur

```
+-----------------------------------------------------------+
|                      FlexRadio 6400                       |
|                     192.168.84.24:4992                    |
+-----------------------------+-----------------------------+
                              | TCP (SmartSDR ASCII-Protokoll)
                              v
+-----------------------------------------------------------+
|          Raspberry Pi Service (FlexRadioLog)              |
|                                                           |
|  +-----------------------------------------------------+  |
|  | 1. Radio Client (asyncio TCP-Stream & Reconnect)    |  |
|  |    - Subscriptions: client, interlock, slice        |  |
|  +--------------------------+--------------------------+  |
|                             |                             |
|                             v                             |
|  +-----------------------------------------------------+  |
|  | 2. State Tracker & SQLite Persistenz (SQLAlchemy)   |  |
|  |    - IP-Allocation Auflösung                        |  |
|  |    - Session-Tracking (Login/Logout, Dauer)         |  |
|  |    - PTT-Event-Tracking (Start, Ende, Frequenz/Band)|  |
|  +--------------------------+--------------------------+  |
|                             ^                             |
|                             |                             |
|  +-----------------------------------------------------+  |
|  | 3. FastAPI REST-Server (:8000)                      |  |
|  |    - OpenAPI / Swagger UI Dokumentation             |  |
|  +--------------------------+--------------------------+  |
+-----------------------------+-----------------------------+
                              | HTTP / JSON REST-API
                              v
+-----------------------------------------------------------+
|          Externes Auswerteprogramm (Visualisierung)        |
+-----------------------------------------------------------+
```

---

## 📦 Installation auf dem Raspberry Pi

### 1. Repository klonen & vorbereiten
```bash
git clone <repo-url> /opt/flexradiolog
cd /opt/flexradiolog
```

### 2. Installationsskript ausführen
```bash
./scripts/install.sh
```
Das Skript erstellt die virtuelle Python-Umgebung, installiert alle notwendigen Pakete und legt bei Bedarf eine Standard-Konfiguration an.

### 3. Konfiguration anpassen (`config.yaml`)
```yaml
radio:
  host: "192.168.84.24"   # IP des FlexRadio 6400
  port: 4992              # Standard-Port für SmartSDR TCP
  reconnect_interval_sec: 3.0
  reconnect_max_backoff_sec: 30.0

database:
  url: "sqlite+aiosqlite:///flexradiolog.db"

api:
  host: "0.0.0.0"
  port: 8000

logging:
  level: "INFO"
  file_path: "flexradiolog.log"

initial_allocations:
  - ip_address: "192.168.84.100"
    callsign: "HB9XYZ"
    operator_name: "Operator Shack"
    notes: "Hauptplatz"
```

### 4. Als Systemd-Dienst einrichten (Autostart)
```bash
sudo cp scripts/flexradiolog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable flexradiolog
sudo systemctl start flexradiolog

# Status und Logs prüfen
sudo systemctl status flexradiolog
journalctl -u flexradiolog -f
```

---

## 🌐 REST-API Dokumentation (Schnittstelle für Auswerteprogramm)

Nach dem Start ist die interaktive Swagger-Dokumentation direkt im Browser erreichbar:
👉 `http://<Raspberry-IP>:8000/docs`

### Wichtigste Endpunkte

| Methode | Endpunkt | Beschreibung |
| :--- | :--- | :--- |
| `GET` | `/api/status` | Aktueller Status (Funkgerät verbunden, aktive Clients, PTT aktiv). |
| `GET` | `/api/allocations` | Liste aller IP-zu-Rufzeichen-Zuordnungen. |
| `POST` | `/api/allocations` | Neue IP-Zuordnung anlegen oder aktualisieren. |
| `DELETE` | `/api/allocations/{id}` | IP-Zuordnung löschen. |
| `GET` | `/api/sessions` | Benutzer-Sitzungen abfragen (Filter: `callsign`, `is_active`, `from_date`, `to_date`, `limit`, `offset`). |
| `GET` | `/api/sessions/{id}` | Detailansicht einer Sitzung inkl. aller zugehörigen PTT-Events. |
| `GET` | `/api/sessions/{id}/ptt` | Alle PTT-Events einer Sitzung. |
| `GET` | `/api/ptt` | Alle PTT-Events abfragen (Filter: `callsign`, `band`, `mode`, `from_date`, `to_date`, `limit`). |
| `GET` | `/api/stats/summary` | Aggregierte Gesamtstatistiken (Sitzungsdauer je Operator, PTT-Anzahl und Sendedauer je Band). |

### Beispiel-Abfragen

#### Radio-Status:
```bash
curl http://localhost:8000/api/status
```
```json
{
  "host": "192.168.84.24",
  "port": 4992,
  "is_connected": true,
  "connected_at": "2026-10-12T14:30:00",
  "last_message_at": "2026-10-12T14:31:05",
  "reconnect_count": 0,
  "radio_version": "3.4.24.112",
  "radio_handle": "01234567",
  "active_clients": 1,
  "is_transmitting": false
}
```

#### Zusammenfassende Statistiken:
```bash
curl http://localhost:8000/api/stats/summary
```
```json
{
  "total_sessions": 12,
  "active_sessions": 1,
  "total_usage_seconds": 18450,
  "total_ptt_count": 84,
  "total_ptt_duration_seconds": 642.5,
  "per_operator": [
    {
      "callsign": "HB9XYZ",
      "session_count": 8,
      "total_usage_seconds": 12300,
      "ptt_count": 62,
      "total_ptt_duration_seconds": 510.2
    }
  ],
  "per_band": [
    {
      "band": "20m",
      "ptt_count": 50,
      "total_ptt_duration_seconds": 412.0
    },
    {
      "band": "40m",
      "ptt_count": 34,
      "total_ptt_duration_seconds": 230.5
    }
  ]
}
```

---

## 🧪 Tests ausführen

Das Projekt verfügt über eine umfassende Test-Suite (inklusive Mock-Radio-Server):
```bash
# Virtuelle Umgebung aktivieren
source .venv/bin/activate

# Alle Tests ausführen
pytest -v
```
