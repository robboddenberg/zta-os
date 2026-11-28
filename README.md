# ZTA OS Berlin (Stand V10.3)

Zentrales Talent- & Agentur-Betriebssystem fuer **ZTA Management Berlin ("From Z to A")** nach dem Canvas-Standard (3-Rollen-Methodik, strikte Trennung von Code und Nutzerdaten, atomare JSON-Persistenz mit `.bak.1..5` und `409 Conflict` Revisionsschutz).

- **Live Mobile/Desktop PWA (GitHub Pages)**: https://robboddenberg.github.io/zta-os/
- **Team Deep-Links**: `?team=zetha&module=tasks`, `?team=sarah&module=tasks`, `?team=elias&module=tasks`

## Aktive V10.3 UI-Module & Rollen (Strict RBAC)

1. **Zwei strikt getrennte Zugriffsebenen**:
   - **Team ZTA (`team_zta`)**: Umschaltbar zwischen **Zetha (Inhaberin)**, **Sarah (Dispo & Casting)** und **Elias (Vertraege, Reise & PR)** inkl. Vollzugriff auf alle 6 Module.
   - **Klient:in (`klient`)**: Geschuetztes Langzeit-Portal fuer eigene Sperrtermine (Orange/Rot mit Ort-Pflicht bei Rot), Kalender, eigene Zeitanfragen (Leseansicht), eigene Gagen-Richtwerte und Stammdaten. Interne Referenz-Deals, Branchen-Indikatoren und Team-Aufgaben bleiben strikt gesperrt. Consulting-Profile besitzen keinen App-Zugang (`403`).

2. **Die 6 Module der V10.3-Oberflaeche**:
   - **Klient:innen Roster**: 20 Profile nach Departments (`Actors`, `Directors + Writers`, `NXT`, `PR & Commercial`, `Consulting`) inkl. **48h-Fristen- & Aufgaben-Cockpit**.
   - **Team-Aufgaben & Push-Waechter**: WhatsApp- und Sprachdiktat-Schnelleingabe (`de-DE`) mit Wortgrenzen-Erkennung, Faelligkeitsdatum, **Bearbeiten & Loeschen**, Prio-1-Banner, Browser-Push-Benachrichtigungen sowie 1-Klick-WhatsApp-/Share-Reminder mit Deep-Link.
   - **Kalender & Sperrtermin-Rechner**: Monats-, Wochen- und Tages-Agenda, Einzel- sowie **Multi-Talent-Department-Check** ("Wer ist im DZR frei?"), ZTA-Termin-Erfassung (`POST /api/calendar/event`), Reise-Dispo-Check (Travel-Rider kopieren & Anreisetag blocken) und RFC-5545 **iCal-Export / Live-Abo (.ics)**.
   - **Zeitanfragen & Casting-Pipeline**: Zeitanfragen-Erfassung, 4-Stufen-Pipeline inkl. automatischer Kalender-Synchronisation und Buchungs-Erkennung bei hinterlegtem Dropbox-Vertragslink (`https://`).
   - **Gagen-Spiegel & Richtwerte**: Zero-Error Cent-Mathematik, ZDF-Formatlaengen-Modell (GVR), automatische Richtwert-Anhebung bei hoeheren Abschluessen und interne Referenz-Deals (nur Team ZTA).
   - **Stammdaten, Unterlagen & Indikatoren**: iOS-Grouped-List Stammdaten mit Aenderungshistorie, Plausibilitaetspruefung, Dokumenten-Checkliste und Branchen-Interesse-Indikatoren.

3. **Alltags-, Design- & PWA-Qualitaet (V10.3)**:
   - **Tag-/Nacht-Modus (Dark Mode)** mit System-Erkennung und Persistenz.
   - **Echter Fokus-Filter** zum Ausblenden erledigter Aufgaben, verfallener Anfragen und sekundaerer Detailkarten.
   - **Online-/Offline-Status-Anzeige** in der Top-Bar (`Live` vs. `PWA Lokal`) plus **JSON-Backup Export & Import** fuer die lokale GitHub-Pages-PWA.
   - **Globale Schnellsuche (`Strg+K` / `Cmd+K`)** mit Pfeiltasten-Navigation, vollstaendiger `Escape`- und Modal-Barrierefreiheit (ARIA).
   - **Serverseitige Haertung**: Erzwingung von `ical_token` und `X-Webhook-Secret` via `hmac.compare_digest`, IDOR-Schutz bei Portal-Antworten, XSS-Escaping im Frontend und gehaerteter Service Worker (`sw.js`).

## Backend-Endpunkte in Vorbereitung (UI-Ausbau geplant)

Folgende Endpunkte sind im FastAPI-Backend bereits implementiert und getestet, aber in der V10.3-Oberflaeche bewusst noch nicht verdrahtet:
- Vertragsrechner, Liquiditaets-Timeline (`/api/analytics/liquidity`) und Rentabilitaet (`/api/analytics/effort-vs-commission`).
- Interaktive Portal-Antworten (`/api/portal/respond`), CSV/JSON-Bulk-Import (`/api/import/parse`) und Gemini-KI-Assistenz (`/api/ai/assist`).

## Schnellstart (Lokal mit FastAPI Live-Server)

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Die App laeuft danach unter `http://127.0.0.1:8020`.

## Tests & Qualitaetssicherung

```powershell
.\.venv\Scripts\pytest.exe -v
```

Das Sync-Skript `scripts/sync_github.ps1` erzwingt und prueft vor jedem Commit automatisch die SHA-256-Paritaet zwischen den GitHub-Pages-Dateien im Root und `frontend/`. Optional kann ein GitHub-Actions-CI-Workflow ergaenzt werden, sobald das lokale `gh`-Token den `workflow`-Scope besitzt (`gh auth refresh -h github.com -s workflow`).

## GitHub-Synchronisation & Docker

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync_github.ps1 -Message "Sync"
```

```bash
docker compose up --build -d
```
