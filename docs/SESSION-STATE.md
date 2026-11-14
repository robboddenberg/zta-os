# ZTA OS Berlin - SESSION-STATE (Stand V10 vom 14.11.2026)

## 1. Projektstatus & Abnahme
- **Spezifikations-Stand**: Vollstaendige Umsetzung von `ZTA-App_Stand_V10_2026-11-13.md` (50 Features, 21 Probleme P1 bis P21, 35 Entscheidungen F1 bis F35, 21 Audit-Punkte A1 bis A21) sowie des abgenommenen **V10 Master-Prompts**.
- **Corporate Identity (Abschnitt 1)**:
  - Primaerfarbe ZTA Blue `#0A1AE4` (und `#0B1AE5` fuer Ueberschriften).
  - Akzent- & Startfarbe ZTA Light Pink `#F2D2C7` (Splash-Screen, DZR-Markierungen im Kalender, 4 Branchen-Indikator-Kacheln).
  - Hintergrund Reinweiss `#FFFFFF` mit feinen 1px Trennlinien.
  - Typografie: Geometrische Display-Sans (Stil *Danmark Bold* / *Syne*) fuer Ueberschriften und *Mulish* (16px) fuer Fliesstext und Navigation.
  - UI-Komponenten: 1px Outline-Buttons in `#0A1AE4`, minimalistische Eingabefelder nur mit blauer Unterlinie, Orange (`#EA580C`) und Rot (`#DC2626`) ausschliesslich fuer Sperrtermine.
- **Strict RBAC (Abschnitt 2)**:
  - Sofort umschaltbarer Role-Switch im Demo-/Dev-Header zwischen **Team ZTA (Admin / Agentur)** und **Klient:in (Langzeit-Klient:in)** inklusive Reset-Button (`/api/v10/reset` + `localStorage`).
  - Consulting- und projektbezogene PR-Klient:innen haben keinen eigenen App-Zugang (`403 Forbidden` auf `/api/v10/client-view/{client_id}`).
  - Strikte Negative Constraints fuer Rolle `Klient:in`: sieht keine internen Auswertungen, keine Branchen-Indikatoren, keine Referenz-Deals, keine zuletzt erzielten Einzelgagen und hat keine Antwort-Buttons bei Zeitanfragen.
- **4 Kernmodule (Abschnitt 3)**:
  1. **Modul 1: Monatskalender & Sperrtermin-Rechner**: TimeTree-inspirierter Monatskalender (`#0A1AE4` gefuellte ZTA-Termine, `#0A1AE4` umrandete Castings/Fristen, Orange/Rot gefuellte Sperrtermine mit Ortsangabe, Leitfrage *"Wuerdest du dafuer einen Drehtag absagen?"*, striktes Pflichtfeld **Ort** bei Stufe **Rot**, `#F2D2C7` DZR-Hervorhebung und kopierbarer Antwort-Textbaustein inkl. Anreise-Hinweis fuer Vor-/Folgetage).
  2. **Modul 2: Zeitanfragen & Casting-Pipeline**: Separate Listenansicht mit strukturierten Eckdaten (ohne lange Synopsen), automatischem Gagen-Richtwert-Vorschlag, ohne manuellen Absage-Button (automatische Ausgrauung bei begonnenem DZR ohne Buchung), 3-stufiger Casting-Pipeline (`Zeitanfrage -> E-Casting -> Live-Casting`) mit Kalender-Synchronisation und automatischer `Gebucht`-Erkennung ueber den Dropbox-Vertragslink.
  3. **Modul 3: Gagen-Spiegel & Richtwerte**: 6 Kategorien (`Streamer`, `ARD/Degeto`, `ZDF` inkl. GVR Formatlaengen-Modell `MWF`/`MW60`/`MWFA`, `Kino`, `Kino/Streaming`, `International` mit Wochengage), `MW` vs. `MA` (+10 % Buyout), automatische Richtwert-Anhebung bei hoeherem Abschluss und geschuetzte interne Referenz-Deals.
  4. **Modul 4: Stammdaten, Dokumente & Interne Auswertung**: 4 Kennzahlen-Kacheln auf `#F2D2C7` (*Zeitanfragen, E-Castings, Live-Castings, Buchungen*) mit Gespraechsleitfaden und Jahresrueckblick, strukturierte Stammdaten mit Plausibilitaetscheck (IBAN, BIC, Steuer-ID vs. USt-IdNr., SV-Nummer, Steuerklasse), Aenderungshistorie mit Gueltig-ab-Datum, abgetrennter Rider/Praeferenzen-Bereich sowie Unterlagen-Checkliste mit Stammblatt-Vorausfuellung.

## 2. Qualitaetssicherung & Betrieb
- **Tests**: `18 passed` in `pytest` (`tests/test_api_e2e.py`, `tests/test_domain_and_math.py`, `tests/test_storage_and_integrity.py`).
- **Port**: `http://127.0.0.1:8020`
- **Synchronisierte Verzeichnisse**:
  - `D:\G-Drive\Canvas\zta-os`
  - `D:\G-Drive\100_Canvas_Apps\Canvas_Projekte\zta-os`
  - GitHub Private Repo: `https://github.com/robboddenberg/zta-os`
