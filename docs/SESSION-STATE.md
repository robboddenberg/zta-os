# ZTA OS Berlin - SESSION-STATE (Stand V10.2 vom 15.11.2026)

## 1. Projektstatus & Meilenstein V10.2 (Executive AI Co-Pilot, 9 Playbooks, Multi-User Access Governance & Handbuch)
- **V10.1 Basis**: Vollständige Umsetzung von `ZTA-App_Stand_V10_2026-11-13.md` (50 Features) im Design-System "ZTA Editorial Luxury & Modern iOS PWA".
- **V10.2 Executive AI Co-Pilot & Governance**:
  - **30 REST-Endpunkte & Multi-Tenancy Isolation**: Vollständige REST-API (`X-Tenant-ID: zta-berlin`), gesetzliche VVV-Prüfung (`WARNING_COMMISSION_CAP_EXCEEDED` bei >14 % / 1400 bp), Optimistic Concurrency (`409 Conflict` via `version`), atomare Sync-Endpunkte (`/api/sync/drive`, `/api/sync/github-pages`) sowie verpflichtendes **Destructive Action Confirmation Gate** (`CONFIRM` / `CANCEL`).
  - **9 Operative Playbooks (A bis I)** über `POST /api/copilot/playbook` und den In-App **Co-Pilot Drawer** (strikt nur für Team ZTA sichtbar):
    - Playbook A (`weekly_briefing`): Weekly Executive Briefing
    - Playbook B (`news_triage`): 3-Stufen Notification & News Triage (Rot / Orange / ZTA Blue)
    - Playbook C (`dzr_fee_check`): DZR-Verfügbarkeit & Gagen-Check inkl. Caster-Textbaustein
    - Playbook D (`booking_auto_offset`): End-to-End Booking & Auto-Offset (mit Confirmation Gate)
    - Playbook E (`payroll_readiness`): Stammblatt & Payroll Readiness Check (Steuerklasse-6-Schutz)
    - Playbook F (`casting_radar_48h`): 48h E-Casting & Recall Radar
    - Playbook G (`annual_review_dossier`): Jahresgespräch & Gagen-Upgrade Dossier 2027
    - Playbook H (`multi_talent_matcher`): Multi-Talent Besetzungs-Matcher
    - Playbook I (`access_governance`): Zugangsrechte & Rollen-Governance Matrix
  - **Echter Multi-User Login & Access Governance (`access_accounts`)**:
    - Persönliche Zugangscodes auf dem Splash-Screen (`ZTA-ADMIN-2026`, `ZTA-TEAM-2026`, `ZTA-CL01-2026` bis `ZTA-CL20-2026`), `isLockedClientSession`-Sperre im Header für eingeloggte Klient:innen, `403 Forbidden` bei gesperrten Consulting-/PR-Konten sowie UI-Verwaltung zum Aktivieren/Sperren.
  - **Direkte Claude-Anbindung**:
    - `scripts/zta_mcp_server.py` (stdio JSON-RPC 2.0 MCP-Server für Claude Desktop) + `/api/copilot/system-prompt` + `/api/copilot/openapi.json`.
  - **Inhaberin-Handbuch (Laien-Anleitung & PDF-Druck)**:
    - `docs/HANDBUCH-INHABERIN-UND-COPILOT.md` sowie druckfähige HTML-Seite `frontend/handbuch.html` (und `/handbuch.html` im Root).

## 2. Qualitätssicherung & Live-Betrieb
- **Test-Gate**: `19 passed` in `pytest` (`tests/test_api_e2e.py`, `tests/test_domain_and_math.py`, `tests/test_storage_and_integrity.py`).
- **GitHub Pages Mobile/Desktop PWA**: `https://robboddenberg.github.io/zta-os/` (Handbuch: `https://robboddenberg.github.io/zta-os/handbuch.html`)
- **Synchronisierte Verzeichnisse**:
  - `D:\G-Drive\Canvas\zta-os`
  - `D:\G-Drive\100_Canvas_Apps\Canvas_Projekte\zta-os`
  - GitHub Repository: `https://github.com/robboddenberg/zta-os`
