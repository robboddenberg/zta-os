# ZTA OS Berlin - SESSION-STATE (Stand V10.1 vom 14.11.2026)

## 1. Projektstatus & UI/UX Design-System Overhaul V10.1
- **Spezifikations-Stand**: Vollständige Umsetzung von `ZTA-App_Stand_V10_2026-11-13.md` (50 Features, P1 bis P21, F1 bis F35, A1 bis A21) kombiniert mit dem **V10.1 Full UI/UX Design-System Overhaul ("ZTA Editorial Luxury & Modern iOS PWA")**.
- **Design-System V10.1 (Abschnitt 1 & 2)**:
  - **Farb- & Surface-Architektur**: Warmes Off-White `--bg-app: #F8FAFC`, reine weiße Surfaces `#FFFFFF`, dezentes Slate `#F1F5F9`, Primärfarbe `--zta-blue: #0A1AE4`, Editorial-Akzente `--zta-pink: #F2D2C7` und `--zta-pink-soft: #FAF0EC` sowie feine Hairlines `--border-subtle: #E2E8F0` mit weicher Elevation statt harter `1px solid #0A1AE4`-Rahmen.
  - **Semantische Status-Badges**: Halbtransparente Badges für Sperrtermin Orange (`#FFF7ED` / `#EA580C`), Sperrtermin Rot (`#FEF2F2` / `#DC2626`) und Positiv/Gebucht/Vorhanden (`#ECFDF5` / `#059669`).
  - **Typografie & Umlaute**: *Plus Jakarta Sans* (700) und *Inter* (400, 500, 600), globales `font-variant-numeric: tabular-nums` auf allen Finanz-, Datums- und KPI-Werten, einzeilige Währungsformatierung (`\u00A0€`), echte deutsche Umlaute (`ä, ö, ü, ß`) in allen Texten und Seed-Daten, Entfernung aller sichtbaren Developer-Spec-Banner und Zusammenführung auf einen einzigen kompakten Kontext-Header pro Ansicht.
  - **Einheitliches Vektor-Icon-Set (0 % System-Emojis)**: Durchgängige 1.75px Lucide-SVG-Vektor-Icons in Top-App-Bar, iOS Segmented Control, Modulen und nativer iOS Bottom-Navigation (ohne blaue Ellipsen um aktive Icons).
- **Strict RBAC & 4 Kernmodule (Abschnitt 3)**:
  - **Tab `Klient:innen` (Roster)**: Einklappbare Notification-Card mit `4px` `#0A1AE4` Akzentstreifen, rahmenlose Department-Filter-Chips (`border-radius: 8px`) und ruhige Klient:innen-Cards mit weichen Initial-Avataren.
  - **Modul 1: `Kalender`**: TimeTree/Apple Calendar Hybrid mit Ansichts-Umschalter (`Monat | Woche | Tages-Agenda`), `Heute`-Sprung, nahtlosem 7-Spalten-Raster, durchgehendem `#FAF0EC` DZR-Band, interaktiver **Tages-Agenda** unter dem Kalender für volle Lesbarkeit ohne Textabschnitte sowie Sperrtermin-Rechner und Leitfragen-Formular (Pflichtfeld **Ort** bei **Rot**).
  - **Modul 2: `Anfragen`**: Moderne Formular-Controls (`border-radius: 10px`, Soft-Focus-Ring), 4-stufiger visueller Pipeline-Stepper (`Zeitanfrage -> E-Casting -> Live-Casting -> Gebucht`), automatische Ausgrauung bei begonnenem DZR ohne Buchung und `Gebucht`-Erkennung über Dropbox-Link.
  - **Modul 3: `Gagen`**: Ruhige Info-Card für das ZDF-GVR-Modell (`MWF / MW60 / MWFA`), `tabular-nums` Finanzkacheln ohne Zeilenumbruch bei `€`, Auto-Upgrade bei höherem Abschluss und geschützte interne Referenz-Deals.
  - **Modul 4: `Stammdaten`**: 2x2 KPI-Grid auf `#FAF0EC` (nur Team ZTA), **iOS-Grouped-List** für persönliche/steuerliche Stammdaten und Rider-Präferenzen inkl. Inline-Bearbeitung, Plausibilitätscheck und Änderungshistorie sowie Unterlagen-Checkliste mit 1-Klick-Stammblatt-Kopie.

## 2. Qualitätssicherung & Live-Betrieb
- **Test-Gate**: `18 passed` in `pytest` (`tests/test_api_e2e.py`, `tests/test_domain_and_math.py`, `tests/test_storage_and_integrity.py`).
- **Lokaler Server**: `http://127.0.0.1:8020`
- **GitHub Pages Mobile/Desktop PWA**: `https://robboddenberg.github.io/zta-os/`
- **Synchronisierte Verzeichnisse**:
  - `D:\G-Drive\Canvas\zta-os`
  - `D:\G-Drive\100_Canvas_Apps\Canvas_Projekte\zta-os`
  - GitHub Repository: `https://github.com/robboddenberg/zta-os`
