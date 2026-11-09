# ZTA OS: Vollstaendiges Feature-Inventar & 8-Rollen-Spezifikation

Stand: 2026-11-09
Referenzen: `00-app-standard/HANDBUCH.md`, `00-app-standard/app_development_guidelines_richtlinien.txt`, `ZTA OS Projekt-Hub (v9)`

---

## 1. Durchlauf des sequenziellen 8-Rollen-Frameworks (APP RULES v1.0)

### [1] Projektdirektor
- **Mission**: Abloesung von TimeTree, Dropbox, WhatsApp-Ketten und verteilten Tabellen durch ein zentrales, DSGVO-konformes Agentur-Betriebssystem mit mindestens 60 % Zeitersparnis in der Termin-, Casting- und Vertragskoordination.
- **Zielgruppe & Rollen**:
  1. **Inhaberin (Super-Admin)**: Gesamtsteuerung ueber alle 4 Sparten (`schauspiel`, `regie_drehbuch`, `nxt`, `pr_commercial`), Finanzen, Provisionen, Liquiditaet, Zeiterfassung/Rentabilitaet und Triage-Board.
  2. **Agentur-Management / PR-Leitung (Angestellte)**: Operatives Tagesgeschaeft, Verfuegbarkeits-Matrix, Zeitanfragen, Konfliktpruefung, 1-Klick-Antwortgenerator, E-Castings und Klienten-Dossiers.
  3. **Klient:innen (Self-Service Mobile PWA)**: iPhone-optimierte Oberflaeche fuer Sperrtermine in 3 Schritten, Rueckmeldungen auf Anfragen/Castings (*"Passt mir"*, *"Passt mir nicht"*, *"Ich habe eine Frage"*) sowie Einsicht in eigene Termine und Gagen-Auszahlungsstatus.
  4. **IT & Administration**: System-Health, Backup-Rotation (`.bak.1..5`), n8n-Webhook-Ingestion, iCal-Feeds, Triage-Board und synthetisches Seeding (20 fiktive Profile).
- **Portabilitaet**: Lokal lauffaehig (`start.ps1` / `start.sh`), containerisiert (`Dockerfile` + `docker-compose.yml`), mandantenfaehig (`tenant_id`, `user_id`) und bereit fuer Cloudflare Tunnel sowie den geplanten Ubuntu Server LTS Homeserver.

### [2] Systemarchitekt
- **Schichtenmodell**:
  - `backend/app/config.py`: Zentrale Umgebungskonfiguration (`DATA_PATH`, `PORT`, `DEFAULT_TENANT_ID`, `WEBHOOK_SECRET`, `GEMINI_API_KEY`).
  - `backend/app/models.py`: Strikte Pydantic-v2-Schemata mit Schema-Migration (`migrate_schema`) und Mandanten-Scoping (`tenant_id`).
  - `backend/app/storage.py`: Thread-sichere, atomare JSON-Storage-Engine (`tempfile` + `os.fsync` + `os.replace`), Backup-Rotation (`.bak.1` bis `.bak.5`), Google-Drive-Konfliktkopie-Erkennung und Optimistic Locking (`409 Conflict` via `if_revision`).
  - `backend/app/logic.py`: Reine, deterministische Domain-Logik (Verfuegbarkeits-Engine, Konflikterkennung, Monatsraster, Antwortvorlagen-Generator, Casting-Countdown mit 2 Werktagen Vorlauf, Cent-genaue Provisions- & Liquiditaetsmathematik, Auto-Offset-Trigger, iCal-Export, fehlertoleranter CSV/JSON-Importer).
  - `backend/app/ai.py`: Optionale KI-Assistenz (Antwort-Veredelung, Vertrags-/Anfrage-Extraktion) mit 100 % deterministischem Offline-Fallback.
  - `backend/app/main.py`: FastAPI REST-API inkl. `/api/health`, `/api/state`, `/api/mutate`, Fach-Endpunkten, `/api/webhooks/ingest` (n8n) und PWA-Auslieferung.

### [3] Datenbank-Experte
- **Normalisierte Collections in `data/data.json`**:
  - `clients`: 20 synthetische Klient:innen mit Sparte (`division`), Standorten, Spielalter, Skills, Provisionssatz in Basispunkten/Prozent, Vita-Daten, geheimem `ical_token` und `tenant_id`.
  - `calendar_events`: Termine pro Klient:in mit Typ (`sperr`, `option`, `dzr`, `dt`, `nachsyn`, `aufnahme`, `casting`), Zeitraum (`start_date`, `end_date`), Ganztags-/Uhrzeitangabe, Optionsrang (`option_rank`), Ablaufdatum (`expires_at`), Status (`confirmed`, `tentative`, `cancelled`) und Audit-Trail.
  - `inquiries`: Zeitanfragen von Produktionen/Casting-Bueros mit Zeitraum, angefragten Drehtagen, Gagen-Angebot in Cent (`offered_gage_cents`), Konfliktstatus, generierter Antwortvorlage, Klienten-Rueckmeldung (`client_response`: `pending`, `fits`, `declined`, `question`) und Verknuepfung zu erzeugten Kalendereintraegen/Vertraegen.
  - `castings`: Castings & E-Castings mit Einladung, Frist (`deadline_date`), automatisch berechnetem internen ZTA-Sichtungstermin (`internal_review_date` = 2 Tage vor Deadline), Upload-/Tape-Status, Klienten-Rueckmeldung und Countdown-Bewertung.
  - `contracts`: Vertraege & Gagen mit Status (`draft`, `negotiation`, `final_signed`, `invoiced`, `paid`), Betraegen strikt als Ganzzahl in Cent (`gage_cents`, `buyout_cents`, `commission_rate_bp`, `commission_cents`, `agency_tax_cents`, `client_payout_cents`), gesetzlicher Deckel-Pruefung und Auszahlungsmonat (`payout_month`, Auszahlung immer zum Monatsende).
  - `time_logs`: Zeiterfassung pro Klient:in und Projekt in Minuten (`duration_minutes`), Kategorie und berechneter Effizienz-Kennzahl (Provision in Cent pro eingesetzter Stunde).
  - `feedback_items`: In-App Melden-System & Triage-Board mit Status (`neu`, `angenommen`, `zurueckgestellt`, `abgelehnt`, `in_arbeit`, `umgesetzt_zu_pruefen`, `erledigt`), Typ (`bug`, `wunsch`, `frage`, `idee`), erfasstem View-/Element-Kontext und Rollen-Herkunft.
  - `audit_logs`: Chronologisches Protokoll aller wichtigen Mutationen, Webhook-Ingests und Auto-Offset-Verknuepfungen.

### [4] UI/UX-Designer
- **Charakterstarkes Thema ("Berlin Talent Editorial & Studio Desk")**:
  - Edles, kontrastreiches Editorial-Design (inspiriert von modernen Film-/Talent-Agenturen mit warmem Papier-/Elfenbein-Ton im Tagmodus und tiefem Studio-Anthrazit im Nachtmodus, kombiniert mit praezisen Gold-/Bernstein- und Smaragd-Akzenten).
  - **ADHS- & Burnout-sensibler Fokus-Filter**: 1-Klick-Schalter *"Fokus: Heute & Dringend"* (blendet erledigte/zukuenftige Routine aus und zeigt nur offene Konflikte, anstehende Casting-Fristen und ungepruefte Zeitanfragen).
  - **Mobile-First iOS Safari PWA**: Eigene, ablenkungsfreie Smartphone-Ansicht fuer Klient:innen mit grossen Touch-Flächen (`>= 48px`), `viewport-fit=cover` und 3-Schritt-Sperrtermin-Assistent.
  - **In-App Kollaboration**: Immer erreichbarer *"Melden"*-Knopf (unter 30 Sekunden inkl. *"Auf etwas zeigen"*-Elementauswahl) und Funktionskatalog mit *"Wie geht das?"*-Kurz-Hilfe.

### [5] Mathematiker & Domain-Logiker (Zero-Error-Policy)
- **Ausschliesslich Ganzzahl-Cents (`int`) & `Decimal`**:
  - Keine `float`-Arithmetik fuer Geldbetraege.
  - `total_gross_cents = gage_cents + buyout_cents`
  - `commission_cents = round_half_up(total_gross_cents * commission_rate_bp / 10000)`
  - `client_payout_cents = total_gross_cents - commission_cents`
- **Deterministische Datums- & Konfliktlogik**:
  - Zwei Zeitraeume $[A_{start}, A_{end}]$ und $[B_{start}, B_{end}]$ ueberlappen genau dann, wenn $A_{start} \le B_{end}$ und $B_{start} \le A_{end}$.
  - Tages-Prioritaet im Monatsraster: `belegt` (`sperr`, `dt`, `nachsyn`, `aufnahme`) > `teilweise` (`dzr`, `casting` oder Uhrzeit-Termin) > `option` (`option`) > `frei`.

### [6] Fachspezifischer Stratege (Schauspiel- & Medienagentur)
- **Sparten-Logik**:
  - `schauspiel`: Standard-Provision 10 % bis 12 % (1000 bis 1200 bp).
  - `regie_drehbuch`: Standard-Provision 10 % bis 12 %, laengere Projektphasen (Drehbuch/Vorbereitung/Dreh/Schnitt).
  - `nxt`: Nachwuchs-Sparte (10 % Provision, Fokus auf Castings & Aufbau).
  - `pr_commercial`: Werbe-, Event- und Marken-Kooperationen (20 % bis 25 % Provision, 2000 bis 2500 bp).
- **Gesetzliche Provisions-Pruefung (Vermittler-Verguetungsverordnung)**:
  - Bei Arbeitsverhaeltnissen im Bereich Schauspiel/Regie warnt das System automatisch, sobald ein Provisionssatz ueber 14 % (1400 bp, bis 7 Tage) bzw. ueber 18 % (1800 bp, ab 8 Tage) eingestellt wird (Ausnahme: `pr_commercial` / Werbe-Buyouts).
- **Auszahlungsregel**: Klientengagen werden konsistent zum **Monatsende** des jeweiligen Zahlungseingangsmonats (`payout_schedule = "end_of_month"`) ausgewiesen.

### [7] DevOps- & Automatisierungs-Spezialist
- **n8n-Webhook-Ingestion (`POST /api/webhooks/ingest`)**:
  - Nimmt strukturierte oder halb-strukturierte Events entgegen (`inquiry.received`, `payment.settled`, `calendar.blocker`, `casting.invited`) und verarbeitet sie fehlertolerant.
- **Intelligente Verknuepfungen (Auto-Offset)**:
  1. **Anfrage -> Kalender & Vertrag**: Wird eine Zeitanfrage durch die Agentur als `option` oder `confirmed` uebernommen, legt das System automatisch den passenden Kalendereintrag (`option` bzw. `dzr`) und auf Wunsch einen Vertragsentwurf (`draft`) mit der angefragten Gage in Cent an.
  2. **Sperrtermin -> Konfliktwarnung**: Traegt ein Klient im Portal einen Sperrtermin ein, prueft die Engine sofort alle bestehenden Optionen/Drehtage im Zeitraum und markiert Konflikte sichtbar fuer die Agentur.
  3. **Zahlungseingang -> Auto-Offset**: Wird ein Vertrag oder ein Zahlungs-Webhook auf `paid` gesetzt, gleicht das System die offene Provisionsforderung automatisch aus (`outstanding_cents = 0`) und setzt den Klienten-Status auf *"Auszahlung zum Monatsende freigegeben"*.

### [8] QA- & Test-Engineer
- Vollstaendige `pytest`-Abdeckung fuer:
  - Storage-Atomaritaet, `.bak.1..5` Rotation, `409 Conflict` und Schutz vor ueberschriebenen korrupten Dateien.
  - Cent-genaue Finanzberechnungen inkl. Grenzfaellen (0 Cent, ungerade Cent-Betraege, 14 %/18 % Gesetzesschwelle, PR-25 %-Satz).
  - Konflikt- und Verfuegbarkeits-Engine (Randtage, mehrtaegige DZR vs. Sperrtermin, "Wer ist frei?"-Filter).
  - Auto-Offset-Ketten (Anfrage -> Kalender/Vertrag, Zahlung -> Forderungsausgleich) und fehlertoleranter CSV/JSON-Parser.

---

## 2. Feature-Matrix (F01 bis F20 + Kollaboration A1 bis A12)

| ID | Feature | Prioritaet | Status in ZTA OS |
| --- | --- | --- | --- |
| F01 | Rollen-Konzept & schneller Rollen-Umschalter (Inhaberin, Agentur/PR, Klient:in, IT) | Must | Implementiert |
| F02 | Klienten-Dossier (4 Sparten, Stammdaten, Skills, Vita, verknuepfte Vorgaenge) | Must | Implementiert |
| F03 | Kalender & Monats-Verfuegbarkeits-Matrix (`sperr`, `option`, `dzr`, `dt`, `nachsyn`, `aufnahme`, `casting`) | Must | Implementiert |
| F04 | iCal-Kalender-Export & Abo-Feed (`.ics` pro Klient:in mit geheimem Token) | Should | Implementiert |
| F05 | Zeitanfragen, Konfliktpruefung & 1-Klick-Antwortgenerator + Kalender-Uebernahme | Must | Implementiert |
| F06 | Castings & E-Castings inkl. internem Sichtungstermin (2 Tage vor Deadline) & Countdown | Must | Implementiert |
| F07 | Mobiles Klienten-Portal (iPhone-optimiert: Sperrtermine in 3 Schritten, 3-Button-Antwort) | Must | Implementiert |
| F08 | Zeiterfassung pro Klient:in & Projekt | Must | Implementiert |
| F09 | Aufwand-vs.-Provisions-Auswertung (Effizienz & Rentabilitaet pro Klient:in) | Should | Implementiert |
| F10 | Vertrags- & Gagenuebersicht (`draft`, `negotiation`, `final_signed`, `invoiced`, `paid`) | Should | Implementiert |
| F11 | Liquiditaets-Timeline aus `final_signed` / `invoiced` / `paid` Vertraegen | Should | Implementiert |
| F12 | Provisionssaetze (10/12 % Schauspiel, 20/25 % PR) + 14 %/18 % Gesetzesschwellen-Warnung | Should | Implementiert |
| F14 | Dossier-/Vita-Zusammenfassung (kopier- & druckfertige Kurzvita) | Should | Implementiert |
| F16 | IT-Admin-Cockpit (Health, Backups, n8n-Webhook-Ingest, CSV/JSON-Import, Komplett-Export) | Must | Implementiert |
| F18 | Charakterstarkes ZTA-Editorial-Design (Tag/Nacht-Modus, Fokus-Filter) | Must | Implementiert |
| F20 | Transparenter Gagen-Auszahlungsstatus im Klienten-Portal (Monatsende-Regel) | Should | Implementiert |
| A1-A12 | In-App "Melden"-Button (< 30s), Element-Picker, Triage-Board & Funktionskatalog | Must | Implementiert |
