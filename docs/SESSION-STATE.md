# ZTA OS Berlin - SESSION-STATE (Stand V10.3 vom 28.11.2026)

## 1. Projektstatus & Meilenstein V10.3 (Multi-Agent Audit Perfection & GitHub PWA Haertung)
- **Git-Architektur**:
  - Hauptbranch **`main`** enthaelt den vollstaendig ueberarbeiteten Stand **V10.3** auf Basis von V10.2 (`b58b5dd`).
  - Archiv-Branch **`archive/v10.2-copilot`** bleibt unveraendert auf GitHub gesichert.
- **Backend-Security, Datenintegritaet & Domain-Logik**:
  - **Neue Endpunkte**: `POST /api/calendar/event` (behebt den bisherigen 404-Datenverlust bei ZTA-Terminen und blockierten Reisetagen), `POST /api/v10/team-tasks/update` und `DELETE /api/v10/team-tasks/{task_id}` (jeweils mit `if_revision` / `409 Conflict` Schutz).
  - **Security & Auth**: `GET /api/ical/{client_id}.ics` und `POST /api/webhooks/ingest` erzwingen ihre Tokens/Secrets nun auch bei fehlendem Parameter/Header mit `hmac.compare_digest`. `POST /api/portal/respond` prueft strikt auf `client_id`-Zugehoerigkeit (IDOR-Schutz). `contract_dropbox_url` erzwingt `http(s)://`. `POST /api/portal/blocker` nutzt `raise_on_error=True` (sauberes HTTP 400 statt 500 bei fehlendem Ort).
  - **Logik & Persistenz**: `parse_eur_to_cents` parst deutsche Tausenderpunkte (`"1.850 EUR"` -> `185000` Cent) korrekt, lehnt Booleans ab und wirft `ValueError` (HTTP 400). `generate_client_ical` escaped RFC-5545-Sonderzeichen und normalisiert invertierte Daten. `compute_sperrtermin_rechner` dedupliziert Casting-Treffer; `compute_multi_talent_dzr_check` stuft `option`-Events korrekt als `option_orange` ein. `parse_and_create_team_task` nutzt Wortgrenzen-Regex (kein Fehltrigger bei `"mp3"` oder einzelnem `"!"`). `StorageEngine` nutzt `_replace_with_retry` gegen kurzzeitige Windows-/Drive-Locks.
- **Frontend, PWA, GitHub Pages Paritaet & Barrierefreiheit (`index.html`, `sw.js`, `manifest.json`)**:
  - **XSS-Schutz**: Zentrale `escapeHtml()`- und `safeHttpUrl()`-Absicherung ueber alle `.innerHTML`-Templates sowie `data-*`-Attribut-Dispatch beim Reise-Dispo-Button.
  - **GitHub Pages Offline-Paritaet**: `loadInitialState()` ueberspringt `/api/state` auf `github.io` / `file:` (null rote 404-Konsolenfehler), dynamisches `getTodayIso()` ersetzt fest einprogrammierte November-Daten, Offline-iCal nutzt vollstaendiges RFC-5545 mit exklusivem `DTEND` und versteckt tote Server-Abo-URLs offline.
  - **Alltags- & Design-Features**: Tag-/Nacht-Modus (`Dark Mode`) mit `localStorage`-Persistenz, echter **Fokus-Filter** (blendet erledigte Aufgaben, verfallene Anfragen und sekundaere Details aus), Top-Bar Online/Offline-Pill (`Live` vs. `PWA Lokal`), Bearbeiten & Loeschen von Team-Aufgaben, sowie **JSON-Backup Export & Import** in `toolsSheet`.
  - **A11y & Service Worker**: `role="dialog"`, `aria-modal="true"`, vollstaendiger `Escape`- und Backdrop-Close, Pfeiltasten-Navigation in `Cmd+K`, Kontrast `#64748B`, Touch-Targets >= 40/44px. `sw.js` (`zta-os-v10-3-v1`) umgeht `/api/`, liefert Offline-Fallback fuer Deep-Links (`?team=sarah&module=tasks`) und leitet `notificationclick` ans Ziel.
- **Synchronisation & Paritaets-Check**:
  - Root (`index.html`, `manifest.json`, `sw.js`, `icon.svg`, `seed-v10.json`) und `frontend/` sind SHA-256-identisch; ungenutztes `frontend/shim.js` wurde entfernt.
  - `scripts/sync_github.ps1` spiegelt die 5 PWA-Dateien vor jedem Commit automatisch von Root nach `frontend/`, prueft deren SHA-256-Paritaet und bricht bei einem fehlgeschlagenen `git push` sauber mit Exit-Code ab. (Ein `.github/workflows/ci.yml` wurde wegen fehlendem `workflow`-Scope des lokalen `gh`-Tokens bewusst nicht eingecheckt.)

## 2. Qualitaetssicherung & Live-Betrieb
- **Test-Gate**: `22 passed` in `pytest -v` (`tests/test_api_e2e.py`, `tests/test_domain_and_math.py`, `tests/test_storage_and_integrity.py`).
- **GitHub Pages Mobile/Desktop PWA**: `https://robboddenberg.github.io/zta-os/`
- **GitHub Repository**: `https://github.com/robboddenberg/zta-os`
