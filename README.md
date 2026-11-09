# ZTA OS: Zentrales Talent- & Agentur-Betriebssystem

Massgeschneidertes Betriebssystem fuer Schauspiel-, Regie-, Nachwuchs- und PR-Agenturen nach dem Canvas-Standard (`00-app-standard/HANDBUCH.md` und `app_development_guidelines_richtlinien.txt`).

## Kernfunktionen

1. **4 Rollen & Ansichten (Multi-Tenancy Ready)**:
   - **Inhaberin (Super-Admin)**: Gesamtsteuerung ueber alle 4 Sparten (`Schauspiel`, `Regie & Drehbuch`, `NXT`, `PR & Commercial`), Vertraege, Provisionen, Liquiditaets-Timeline, Zeiterfassung/Rentabilitaet und Triage-Board.
   - **Agentur / PR-Management**: Verfuegbarkeits-Matrix (*"Wer ist frei?"*), Zeitanfragen mit automatischer Konflikterkennung, 1-Klick-Antwortgenerator, E-Casting-Koordination (inkl. Sichtungstermin 2 Tage vor Deadline) und Klienten-Dossiers.
   - **Klienten-Portal (iPhone PWA)**: Mobile-First Self-Service fuer Sperrtermine in 3 Schritten, schnelle Rueckmeldungen (*"Passt mir"*, *"Passt mir nicht"*, *"Ich habe eine Frage"*), eigene Termine und Auszahlungsstatus (Monatsende-Regel).
   - **IT & Administration**: System-Health, Backup-Rotation (`.bak.1..5`), n8n-Webhook-Ingestion (`/api/webhooks/ingest`), iCal-Feeds und synthetisches Seeding (20 fiktive Profile).
2. **Zero-Error-Finanzlogik**:
   - Alle Geldbetraege werden strikt als Ganzzahlen in Cent (`_cents: int`) gespeichert und via `Decimal` berechnet.
   - Automatische Pruefung der gesetzlichen Provisions-Obergrenzen nach Vermittler-Verguetungsverordnung (14 % / 18 % Warnung).
3. **Auto-Offset & Event-Driven Workflows**:
   - Bestaetigte Zeitanfragen erzeugen automatisch Kalendereintraege (`option` / `dzr`) und Vertragsentwuerfe.
   - Zahlungseingaenge gleichen offene Provisionsforderungen per Auto-Offset aus.

## Schnellstart (Windows PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Die App laeuft danach unter `http://127.0.0.1:8020`.

## Tests ausfuehren

```powershell
.\.venv\Scripts\pytest.exe
```

## Docker-Start

```bash
docker compose up --build -d
```
