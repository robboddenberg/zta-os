# ZTA OS: Master-Prompt & Dokumentation des UI/UX Redesigns (V10 bis V10.2)

Dieses Dokument archiviert den vollständigen Master-Prompt sowie alle konkreten Design-, Architektur- und UX-Entscheidungen, die bei der Transformation von ZTA OS (Stand V10 -> V10.1 UI/UX Overhaul -> V10.2 Executive AI Co-Pilot) umgesetzt wurden.

---

## Teil 1: Der vollständige Master-Prompt (Konsolidiert V10 + V10.1 + V10.2)

### A. System- & Rollen-Definition
- **Rollen**: Senior Full-Stack Architect, Lead UI/UX Engineer (2026 Editorial SaaS & iOS PWA), QA Testing Lead, Graphic Designer.
- **Ziel**: Vollständige Web-Applikation **ZTA OS** für die Talent- und PR-Agentur **ZTA Management Berlin** als moderner, hochperformanter Ersatz für TimeTree auf Desktop, iOS und Android (PWA + FastAPI + GitHub Pages Offline-Sync).

### B. Corporate Identity & V10.1 Design-System ("ZTA Editorial Luxury & Modern iOS PWA")
- **Farb- & Surface-Architektur**:
  - `--bg-app: #F8FAFC` (Warmes Off-White statt grellem Reinweiß überall)
  - `--bg-surface: #FFFFFF` (Karten, Modals, Sheets)
  - `--bg-subtle: #F1F5F9` (Inputs, Segmented Controls)
  - `--zta-blue: #0A1AE4` (Primäre Markenfarbe nur für Primary-CTAs, aktive Tabs, Fokus-Zustände)
  - `--zta-pink: #F2D2C7` & `--zta-pink-soft: #FAF0EC` (Editorial-Akzent für KPI-Kacheln, Splash-Screen und DZR-Kalenderband ohne harte blaue Umrandung)
  - `--border-subtle: #E2E8F0` + weiche Elevation `0 1px 3px rgba(15, 23, 42, 0.04)` statt harter `1px solid #0A1AE4`-Rahmen
- **Semantische Status-Badges**:
  - Sperrtermin Orange (Vorbehalt): `#FFF7ED` / Border `#FDBA74` / Text `#EA580C`
  - Sperrtermin Rot (Verbindlich + Pflichtfeld Ort): `#FEF2F2` / Border `#FCA5A5` / Text `#DC2626`
  - Positiv / Gebucht / Vorhanden: `#ECFDF5` / Border `#A7F3D0` / Text `#059669`
- **Typografie & Formatierung**:
  - *Plus Jakarta Sans* / *Syne* (Display) + *Inter* / *Mulish* (UI/Fließtext)
  - `font-variant-numeric: tabular-nums` auf allen Zahlen, Daten und Geldbeträgen
  - Einzeilige Euro-Formatierung (`\u00A0€`), echte deutsche Umlaute (`ä, ö, ü, ß`), strikt keine Gedankenstriche

### C. Strict RBAC & Fachlogik (Zero Regression)
- **Team ZTA (Admin / Agentur)**: Vollzugriff auf alle 5 Departments (*Actors, Directors + Writers, NXT, PR & Commercial, Consulting*), Sperrtermin-Rechner, Zeitanfragen, Casting-Pipeline, Gagen-Spiegel, Stammdaten/Dokumenten-Checkliste, Executive AI Co-Pilot und Zugangsrechte-Steuerung.
- **Klient:in (Langzeit-Portal)**: Sieht ausschließlich eigene Termine und Richtgagen; darf nur eigene Sperrtermine anlegen (Pflichtfeld **Ort** bei **Rot**). Sieht **keine** internen Auswertungen, **keine** Referenz-Deals, **keine** Einzelgagen anderer und hat **keine** Antwort-Buttons bei Zeitanfragen. Consulting & projektbezogene PR erhalten `403 Forbidden`.
- **Zero-Error Cent-Mathematik**: Alle Beträge in `int` Cents (`Decimal` mit `ROUND_HALF_UP`).

### D. V10.2 Executive AI Co-Pilot, 9 Playbooks (A bis I) & Claude-Integration
- 30 REST-Endpunkte mit Multi-Tenancy (`X-Tenant-ID: zta-berlin`), VVV-Prüfung (`WARNING_COMMISSION_CAP_EXCEEDED`), Confirmation Gate (`CONFIRM` / `CANCEL`) und `409 Conflict` Versionierung.
- 9 Playbooks (A: Weekly Briefing, B: News Triage, C: DZR & Fee Check, D: Booking & Auto-Offset, E: Payroll Readiness, F: 48h Casting Radar, G: Jahresgespräch-Dossier, H: Multi-Talent Matcher, I: Access Governance).
- Direkte Claude-Anbindung via `scripts/zta_mcp_server.py` (MCP stdio JSON-RPC 2.0), `/api/copilot/system-prompt` und `/api/copilot/openapi.json`.

---

## Teil 2: Was konkret im UI/UX Redesign (V10.1 -> V10.2) verändert wurde

| Bereich | Vorher (Retro-Wireframe V10.0) | Nachher (Modern 2026 V10.1 / V10.2) |
| :--- | :--- | :--- |
| **Kopfzeile & Platz am Handy** | Riesiger Header mit vielen blauen Pill-Buttons, der fast die halbe Bildschirmhöhe am iPhone blockierte. | Kompakte `56px` Sticky Top-App-Bar (`backdrop-blur-md`) mit iOS Segmented Role-Switch, Quick-Switcher und aufklappbarem **Tools Slide-Over Sheet** für sekundäre Aktionen. |
| **Rahmen & Schatten** | Überall harte `1px solid #0A1AE4` Rahmen und schwere Boxen. | Ruhiges `#F8FAFC` Off-White, weiße Cards mit feinen `#E2E8F0` Hairlines und sanften Schatten. |
| **Icons & Texte** | Gemischte System-Emojis, fehlende Umlaute (`ue/ae/oe`), sichtbare Dev-Regel-Banner. | Einheitliche `1.75px` Lucide-Vektor-SVGs (0 % Emojis), echte deutsche Umlaute, Entfernung aller Dev-Banner. |
| **Kalender-Lesbarkeit** | Abgeschnittene Texte in kleinen Monatszellen (`"Ta..."`, `"Dr..."`). | TimeTree/Apple Calendar Hybrid: `Monat \| Woche \| Tages-Agenda` Umschalter, `Heute`-Button, durchgehendes `#FAF0EC` DZR-Band und vollständige **Tages-Agenda** unter dem Raster. |
| **Anfragen & Pipeline** | Schlichte Liste ohne visuellen Fortschritt. | 4-stufiger visueller Pipeline-Stepper (`Zeitanfrage -> E-Casting -> Live-Casting -> Gebucht`), automatische Ausgrauung bei abgelaufenem DZR ohne Vertrag. |
| **Gagen & Stammdaten** | Unruhige Tabellen, umgebrochene `€`-Zeichen. | `tabular-nums` ohne Zeilenumbruch, ruhige ZDF-GVR-Info-Card (`MWF/MW60/MWFA`), 2x2 `#FAF0EC` KPI-Grid und **iOS-Grouped-List** mit Inline-Bearbeitung und Plausibilitätscheck. |
| **KI & Zugangsrechte (V10.2)** | Keine direkte Co-Pilot-Oberfläche, nur statischer Demo-Switch. | In-App **Co-Pilot Drawer** (Playbooks A bis I + `CONFIRM`/`CANCEL` Gate), echte Login-Codes (`ZTA-ADMIN-2026`, `ZTA-CL01-2026`) mit `isLockedClientSession`-Sperre sowie druckfähiges **Inhaberin-Handbuch** (`handbuch.html`). |
