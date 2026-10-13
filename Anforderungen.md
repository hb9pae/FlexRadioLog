# FlexRadio 6400 Monitoring Server (FlexRadioLog)
**Anforderungsspezifikation, Architektur und Projektplan**

---

## 1. Allgemeines & Zielsetzung
- **Ziel:** Autarker, zuverlässiger Hintergrunddienst (Daemon) zur lückenlosen Überwachung, Protokollierung und Auswertung des Betriebs eines FlexRadio 6400.
- **Hardware Radio:** FlexRadio 6400
- **Radio IP-Adresse:** `192.168.84.24` (SmartSDR TCP-Steuerungsport: `4992`)
- **Zielplattform:** Raspberry Pi (Raspberry Pi OS / Linux, Python 3.10+)
- **Hintergrundbetrieb:** Linux `systemd`-Service mit automatischem Neustart
- **Persistenz:** Lokale SQLite-Datenbank (`flexradiolog.db`)
- **Schnittstelle:** REST-API via FastAPI (JSON) für externe Visualisierungs- und Auswerteprogramme (ohne Authentifizierung im lokalen LAN)

---

## 2. Bestätigte Architekturentscheidungen & Spezifikation

### 2.1 Benutzer-Identifikation & Sitzungsverwaltung (Login -> Logout)
- **Benutzererkennung via IP & Rufzeichen:**
  - Identifikation basiert auf der **IP-Adresse** des verbundenen Clients in Kombination mit einer konfigurierbaren **IP-Allocation-Tabelle** (Zuordnung von IP-Adressen zu Funkamateuren/Rufzeichen).
  - Ergänzend wird der vom Client übermittelte Stationsname (`station`), Clientname (`name`, z. B. SmartSDR-Win, SmartSDR-iOS) sowie die Client-UUID erfasst.
- **Sitzungszyklus:**
  - **Login:** Das Radio meldet `client <uuid> connected=1 ip=<IP> ...`. Erzeugt einen neuen Session-Eintrag mit Startzeitstempel und aufgelöstem Rufzeichen.
  - **Logout:** Das Radio meldet `client <uuid> connected=0 ...` oder Trennung. Schließt die Session mit Endzeitstempel und berechnet die exakte Nutzungsdauer in Sekunden.
  - **Ausfallsicherheit:** Beim Start prüft der Dienst auf nicht abgeschlossene Sitzungen (z. B. nach Stromausfall oder abruptem Radio-Neustart) und schließt diese konsistent ab.

### 2.2 PTT-Tastungen & Frequenzprotokollierung (Detaillierte Einzel-Events)
- **Granularität:** Jede einzelne PTT-Aktivierung wird als detailliertes Event geloggt (keine reine Pauschalzählung).
- **Interlock-Überwachung:**
  - **PTT Start:** Erkennung des Statusübergangs zu `interlock state=TRANSMITTING` (oder `state=PTT_REQUESTED`). Zeitstempel wird festgehalten.
  - **PTT Ende:** Erkennung des Statusübergangs zu `interlock state=READY`. Dauer der Sendung wird präzise errechnet.
- **Frequenz- & Modus-Erfassung:**
  - Überwachung der Slice-Receiver (`sub slice all`).
  - Beim Senden wird der aktive TX-Slice (`tx=1`) ausgewertet:
    - Exakte Frequenz in Hz (z. B. `14074000`)
    - Amateurfunkband (automatisch abgeleitet, z. B. `20m`, `40m`, `80m`)
    - Betriebsart / Mode (z. B. `USB`, `LSB`, `CW`, `DIGU`, `FM`)
- **Zuordnung:**
  - Jedes PTT-Event wird der aktuellen Session des sendenden Benutzers (`tx_client_handle`) zugeordnet.

### 2.3 Datenbankmodell (SQLite)
Das relationale Datenmodell in SQLite umfasst vier zentrale Tabellen:

1. **`ip_allocations`** (Benutzer- & IP-Zuordnung):
   - `id` (INTEGER PRIMARY KEY)
   - `ip_address` (TEXT UNIQUE) - IP-Adresse des Clients (z. B. 192.168.84.50)
   - `callsign` (TEXT) - Rufzeichen / Operator-Name (z. B. HB9XYZ)
   - `operator_name` (TEXT) - Name des Funkamateurs
   - `notes` (TEXT) - Bemerkungen (z. B. "Shack PC", "iPad Remote")

2. **`sessions`** (Benutzer-Sitzungen):
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
   - `client_uuid` (TEXT) - Eindeutige FlexRadio Client-UUID
   - `client_handle` (TEXT) - Hex-Handle der Session
   - `client_ip` (TEXT) - IP-Adresse des Clients
   - `callsign` (TEXT) - Aufgelöstes Rufzeichen aus IP-Allocation (Fallback: Radio-Stationsname)
   - `client_name` (TEXT) - Softwaretyp (SmartSDR-Win, SmartSDR-iOS, Maestro etc.)
   - `station` (TEXT) - Vom Client gemeldeter Stationsname
   - `start_time` (DATETIME) - Verbindungszeitpunkt
   - `end_time` (DATETIME, NULLABLE) - Trennungszeitpunkt
   - `duration_seconds` (INTEGER, NULLABLE) - Gesamte Nutzungsdauer
   - `is_active` (BOOLEAN) - Status (1 = aktuell online, 0 = beendet)

3. **`ptt_events`** (Detaillierte PTT-Aussendungen):
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
   - `session_id` (INTEGER FOREIGN KEY -> sessions.id)
   - `start_time` (DATETIME) - Startzeitpunkt der Sendung
   - `end_time` (DATETIME) - Endzeitpunkt der Sendung
   - `duration_seconds` (REAL) - Sendedauer in Sekunden (auf Millisekunden genau)
   - `frequency_hz` (INTEGER) - Frequenz in Hz
   - `band` (TEXT) - Amateurfunkband (z. B. "20m")
   - `mode` (TEXT) - Betriebsart (z. B. "USB", "FT8")
   - `tx_slice_id` (INTEGER) - ID des sendenden Slice-Empfängers

4. **`system_events`** (Betriebs- & Verbindungsprotokoll):
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
   - `timestamp` (DATETIME)
   - `event_type` (TEXT) - INFO, WARNING, DISCONNECT, RECONNECT
   - `message` (TEXT) - Meldungstext

### 2.4 REST-API für externes Auswerteprogramm (FastAPI)
- **Authentifizierung:** Keine Authentifizierung im lokalen Netzwerk (LAN-Zugriff frei).
- **Interaktive Dokumentation:** OpenAPI & Swagger UI automatisch unter `http://<Raspberry-IP>:8000/docs`.
- **Endpunkte:**
  - `GET /api/status`: Aktueller Verbindungsstatus zum Radio, aktuell aktive Sitzungen, Systemzustand.
  - `GET /api/allocations`: Verwaltung der IP-zu-Rufzeichen-Zuordnungen (CRUD).
  - `POST /api/allocations`: Neue IP-Zuordnung anlegen oder aktualisieren.
  - `GET /api/sessions`: Abfrage aller Sitzungen mit Filteroptionen (`callsign`, `from_date`, `to_date`, `is_active`, Pagination: `limit`, `offset`).
  - `GET /api/sessions/{id}`: Detailinformationen zu einer Sitzung inklusive aggregierter Statistiken.
  - `GET /api/sessions/{id}/ptt`: Alle PTT-Events einer bestimmten Sitzung.
  - `GET /api/ptt`: Übergreifende Liste aller PTT-Events mit Filtern (`callsign`, `band`, `mode`, `from_date`, `to_date`).
  - `GET /api/stats/summary`: Zusammenfassende Statistiken (Gesamte Nutzungsdauer je Rufzeichen, PTT-Anzahl und Sendedauer je Band und Operator).

---

## 3. Architektur & Evaluierung der Anbindung

### 3.1 Evaluierungsergebnis: Direkter asynchroner TCP-Client (Variante 1)
- **Gewählte Lösung:** Eigenständiger `asyncio` TCP-Client, der sich direkt mit Port 4992 des FlexRadio verbindet.
- **Gründe:**
  - Die PyPI-Bibliothek `flexclient` befindet sich im Pre-Alpha-Zustand, ist für VITA-49 Audiostreams konzipiert und unzuverlässig für 24/7-Dauerbetrieb.
  - Das SmartSDR TCP-Protokoll auf Port 4992 ist ein simples, robustes ASCII-Zeilenprotokoll.
  - Durch den direkten `asyncio`-Client hat der Dienst volle Kontrolle über Reconnect-Zyklen, Verbindungsabbrüche und Timeout-Management.

### 3.2 Protokollablauf (SmartSDR Port 4992)
1. **Verbindungsaufbau:** TCP-Verbindung zu `192.168.84.24:4992`.
2. **Initialisierung:** Radio sendet Versionskennung (`V...`) und Handle (`H...`).
3. **Abonnements (Subscriptions):**
   - `C1|sub client all\n` -> Benachrichtigung bei Client-Verbindungen und -Trennungen.
   - `C2|sub interlock all\n` -> Benachrichtigung über PTT-Zustände (`TRANSMITTING`, `READY`).
   - `C3|sub slice all\n` -> Benachrichtigung über Frequenzen, Modes und TX-Slice.
4. **Ereignisverarbeitung:** Eingehende Statuszeilen (`S...`) werden asynchron geparst, Zustände im Memory aktualisiert und in die SQLite-Datenbank persistiert.
5. **Auto-Reconnect:** Bricht die TCP-Verbindung ab (z. B. Radio ausgeschaltet), wartet der Dienst und versucht kontinuierlich die Wiederverbindung.

---

## 4. Projektplan & To-Do-Liste

### Phase 1: Spezifikation & Architekturentwurf
- [x] Anforderungen analysiert und verifiziert
- [x] Protokoll- und Bibliotheksrecherche (SmartSDR TCP vs. flexclient) abgeschlossen
- [x] Klärung mit Auftraggeber abgeschlossen:
  - Detaillierte Einzel-Events für PTT
  - REST-API via FastAPI ohne LAN-Authentifizierung
  - Benutzeridentifikation über IP + Rufzeichen (Allocations-Tabelle)
- [x] Spezifikation und Datenbankmodell finalisiert

### Phase 2: Projekt-Setup & Basiskomponenten
- [x] Python-Projektstruktur aufgesetzt (`pyproject.toml`, Abhängigkeiten: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `aiosqlite`, `greenlet`, `pydantic`, `pytest`)
- [x] Konfigurationsmanagement erstellt (`config.py` & `config.yaml` für Radio-IP, Port, DB-Pfad)
- [x] Logging eingerichtet (strukturiertes Logging für Konsolen- und File-Output)
- [x] Datenbank-Modelle & Migration/Initialisierung (SQLAlchemy mit SQLite)

### Phase 3: FlexRadio Protokoll-Engine & Collector
- [x] Asynchroner TCP-Socket-Client mit Reconnect-Logik (`RadioClient`)
- [x] SmartSDR-Protokoll-Parser für `client`, `interlock` und `slice`
- [x] Session-Manager (Login/Logout-Erkennung, Zuordnung über IP-Allocation-Tabelle, Dauernberechnung)
- [x] PTT-Tracker (Start-/Endzeit-Erfassung, Frequenz- und Bandbestimmung, Dauer)
- [x] Unit-Tests und Mock-Radio-Server zur isolierten Simulation des FlexRadio 6400 (30 Tests)

### Phase 4: REST-API Entwicklung
- [x] FastAPI-Applikation initialisiert und Lifecycle (Start/Stop des Collectors) eingebunden
- [x] Endpunkte für Status und IP-Allocations implementiert
- [x] Endpunkte für Sessions und PTT-Events (inkl. Filter & Paginierung) implementiert
- [x] Endpunkte für aggregierte Statistiken implementieren
- [x] API-Tests mit `httpx` / `pytest` (33 Tests)

### Phase 5: Bereitstellung & Raspberry Pi Integration
- [x] Systemd-Unit-Datei (`scripts/flexradiolog.service`) für Daemon-Hintergrundbetrieb erstellt
- [x] Start- und Installations-Skript für Raspberry Pi bereitgestellt (`scripts/install.sh`, `scripts/run.sh`)
- [x] Dokumentation zur Inbetriebnahme und Anbindung des externen Auswerteprogramms erstellt (`README.md`)
- [ ] End-to-End-Validierung vor Ort mit dem physischen FlexRadio 6400 (`192.168.84.24`)

# Erweiterung LogGui
Das LogGui erlaubt die Auswertung der Logs in der Datenbank. 
Der Benutzer kann die Auswertungen mit einem Web-Browser abrufen und dabei vordefinierte oder 
individuelle Zeitintervalle oder Benutzer betrachten.

## Standardauswertungen
- [x] Belegung FlexRadio 6400 der letzten 24 h, einer Kalenderwoche oder eines Kalendermonats
- [x] Auswahl Benutzer (einzeln oder alle)
- [x] Export der Daten in ein CSV-File (Auswahl Datumsfenster, Benutzer) mit UTF-8 BOM für Excel
- [x] Weitere sinnvolle Auswertungen:
  - KPI Dashboard (Gesamtsitzungen, Belegungszeit, Sendedauer, TX Duty Cycle, Aktive Benutzer)
  - Visualisierung der Sendeaktivität nach Band (PTT Events)
  - Visualisierung der Belegung nach Operator (Top Operators)
  - Detailansicht pro Session mit Auflistung aller zugehörigen PTT-Transmissionsdaten (Frequenz, Band, Mode, TX-Slice)
- [x] Eigenständige Applikation auf Raspberry Pi (Port 8080) mit Systemd-Dienst (`scripts/loggui.service`) und Startskript (`scripts/run_loggui.sh`)


