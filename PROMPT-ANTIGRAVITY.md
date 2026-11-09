# Antigravity Initialisierungs-Prompt: ZTA-OS (Agentur-Betriebssystem)

Wir bauen eine neue App in `D:\G-Drive\Canvas\zta-os`.
Grundlage sind alle Dateien in `D:\G-Drive\Canvas\00-app-standard\` (`HANDBUCH.md`, `app_development_guidelines_richtlinien.txt`, `init-new-app.ps1`, `NEUE-APP-VORLAGE.md`), die bestehenden Referenz-Apps in `D:\G-Drive\Canvas\` (`Klarschiff`, `Leben backup`) sowie die Fachspezifikation aus dem ZTA OS Projekt-Hub (Version 9).

## 1. Projektziel: ZTA-OS (Zentrales Talent- & Agentur-Betriebssystem)

Ein massgeschneidertes, hochmodernes Betriebssystem fuer eine Berliner Schauspiel-, Regie-, Nachwuchs- und PR-Agentur (4 Sparten: **Schauspiel**, **Regie & Drehbuch**, **NXT**, **PR & Commercial**).
Die App loest fragmentierte Inselloesungen (TimeTree, Dropbox, E-Mail/WhatsApp-Ketten, Excel-Listen) ab und spart ueber 60 % der administrativen Koordinationszeit.

## 2. Rollen-Konzept & Ansichten (Multi-Tenancy & RBAC)

Ein nahtloser Rollen-Umschalter im Header ermoeglicht im Test- und Produktivbetrieb den sofortigen Perspektivwechsel zwischen den 4 Hauptrollen:

1. **Inhaberin (Super-Admin)**:
   - Kompletter Ueberblick ueber alle 4 Sparten, Finanzen, Provisionen, Liquiditaets-Timeline, Vertraege, Zeiterfassung/Rentabilitaet pro Klient:in und Triage-Board.
2. **Angestellte / Agentur-Management (1 bis 2 Personen, inkl. Leitung PR & Commercial)**:
   - Operatives Tagesgeschaeft: Verfuegbarkeits-Matrix ("Wer ist frei?"), Zeitanfragen mit automatischer Konflikterkennung, 1-Klick-Antwortgenerator (fuer Casting-Direktor:innen und Produktionen), E-Casting-Koordination (mit automatischeminternem Sichtungstermin 2 Tage vor Deadline) und Klienten-Dossiers.
3. **Klient:innen (15 bis 25 Personen, Mobile-First iPhone Self-Service Portal)**:
   - Extrem aufgeraeumte iOS-Safari-optimierte PWA-Ansicht fuer Schauspieler:innen und Regisseur:innen.
   - **Sperrtermine in 3 Schritten eintragen** (mit sofortiger Konfliktwarnung, falls im Zeitraum bereits eine Option oder ein Drehtag liegt).
   - **Offene Zeitanfragen & E-Castings beantworten** mit 3 grossen Touch-Buttons: *"Passt mir"*, *"Passt mir nicht"*, *"Ich habe eine Frage"*.
   - **Eigene Termine & Gagen-Status einsehen** (inkl. transparentem Hinweis zur Gagen-Auszahlung zum Monatsende).
4. **IT & Administration**:
   - Wartungsfreie Systemsteuerung, Health-Monitor, Backup-Rotation (`.bak.1` bis `.bak.5`), n8n-Webhook-Ingestion-Logs, iCal-Feed-Verwaltung, In-App-Feedback-Triage-Board und Seeding-Steuerung.

## 3. Einhaltung von `00-app-standard` (HANDBUCH.md & APP RULES v1.0)

- **Prinzip 1 (Portabilitaet, Docker & Multi-Tenancy)**:
  - Strikte Trennung von Core-Logik (`backend/app/logic.py`), Datenhaltung (`backend/app/storage.py` -> `data/data.json`) und UI (`frontend/`).
  - Jedes Dokument fuehrt `tenant_id` (Standard: `"zta-berlin"`) und Benutzer-/Klienten-Scoping.
  - Vollstaendige Bereitstellung via `start.ps1`, `start.sh`, `Dockerfile`, `docker-compose.yml` und `.env.example`.
- **Prinzip 2 (Sequenzielles 8-Rollen-Framework + 3-Rollen-Methodik)**:
  - Projektdirektor, Systemarchitekt, Datenbank-Experte, UI/UX-Designer, Mathematiker/Domain-Logiker, Fachspezifischer Stratege, DevOps/n8n-Spezialist, QA/Test-Engineer.
- **Prinzip 3 (Mathematische & Daten-Integritaet / Zero-Error-Policy)**:
  - **Keine Gleitkommafehler**: Alle Geldbetraege (`gage_cents`, `buyout_cents`, `commission_cents`, `net_payout_cents`) werden ausschliesslich als Ganzzahlen in Cent (`int`) gespeichert und mit `Decimal` berechnet.
  - Automatische Pruefung der gesetzlichen Provisions-Obergrenzen nach Vermittler-Verguetungsverordnung (Warnhinweis ab 14 % bzw. 18 % bei Schauspiel, Standard 10 %/12 % Schauspiel bzw. 20 %/25 % PR & Commercial).
- **Prinzip 4 (Automatisierung, n8n-Ingestion & Auto-Offset)**:
  - Entkoppelte Webhook-Schnittstelle (`/api/webhooks/ingest`) fuer externe Trigger (z. B. eingehende E-Mail-Zeitanfragen oder Zahlungsabgleiche via n8n).
  - **Auto-Offset & Subsystem-Verknuepfung**:
    - Uebernahme einer Zeitanfrage legt automatisch den Kalendereintrag (`option` / `dzr` / `dt`) und optional einen Vertragsentwurf an.
    - Vertragsstatus `final_signed` aktualisiert deterministisch die Provisionsvorschau und Liquiditaets-Timeline.
    - Verbuchung eines Zahlungseingangs (`paid`) gleicht die offene Forderung per Auto-Offset aus und schaltet im Klienten-Portal die Auszahlungsfreigabe zum Monatsende aktiv.
- **Prinzip 5 (Testbarkeit & QA-Gates)**:
  - Vollstaendige `pytest`-Suite fuer Storage, 409-Konflikte, Backup-Rotation, Konflikt-Engine, Cent-Mathematik, Auto-Offset, fehlertolerante Parser und REST-Endpunkte.
- **Synthetische Testphase (20 fiktive Profile)**:
  - `scripts/build_initial_data.py` erzeugt 20 realistische, 100 % fiktive Klienten-Profile ueber alle 4 Sparten mit Terminen, Zeitanfragen, Castings, Vertraegen, Zeiterfassung und In-App-Feedback-Tickets.
