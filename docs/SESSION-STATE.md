# ZTA OS Berlin - SESSION-STATE (Stand V10.2 vom 23.11.2026)

## 1. Projektstatus & Meilenstein V10.2 (Team-Aufgaben, Push-Reminder & 6 Alltags-Features auf V10.1-Basis)
- **Git-Architektur**:
  - Hauptbranch **`main`** basiert sauber auf dem **V10.1 Full UI/UX Design-System Overhaul (`dd1b4d5`)** ohne den vorigen Co-Pilot-Schritt.
  - Der Co-Pilot-, MCP- und Handbuch-Stand ist unverändert auf dem eigenen Archiv-Branch **`archive/v10.2-copilot`** auf GitHub gesichert.
- **Wunsch der Inhaberin: Mobiles Team-Aufgaben-Board (`team_tasks`) & Push-Wächter**:
  - **Mitarbeiter-Rollen im Team ZTA**: Umschaltbar zwischen **Zetha (Inhaberin)**, **Sarah (Dispo & Casting)** und **Elias (Verträge, Reise & PR)** im Splash-Screen, im Aufgaben-Board sowie direkt über URL-Deep-Links (`?team=sarah&module=tasks`, `?team=elias&module=tasks`). Klient:innen bleiben strikt ausgesperrt (`Strict RBAC`).
  - **WhatsApp- & Sprachdiktat-Schnelleingabe (`POST /api/v10/team-tasks`)**: Kurzeingabe (z. B. `"Sarah: ZDF-Vertrag bei Mara prüfen! #dringend"`) oder Sprachdiktat (`SpeechRecognition` in `de-DE`) erkennt automatisch Empfänger:in, Priorität (`p1_urgent`, `p2_important`, `p3_routine`) und erwähnte Klient:innen.
  - **Push-Erinnerungen bis erledigt (`POST /api/v10/team-tasks/ping` & `toggle`)**: Persistenter roter Prio-1-Erinnerungsbanner, Push-Benachrichtigungen im Browser/PWA (`Notification` API + Service Worker `notificationclick`) und 1-Klick-WhatsApp-/Share-Reminder mit Deep-Link an Sarah, Elias oder Zetha. Beim Abhaken wird `push_active` sofort gestoppt.
- **Umgesetzte Alltags-Erweiterungen (Features 1, 2, 3, 4, 6, 7)**:
  - **FK 1 (Multi-Talent-Verfügbarkeits-Check)**: Umschalter im Sperrtermin-Rechner (`Aktuelle Klient:in` vs. `Ganzes Department prüfen` via `POST /api/v10/sperrtermin-rechner/multi`) gruppiert Talente in 100 % Frei (Grün), Unter Vorbehalt (Orange) und Blockiert (Rot) inkl. Sammel-Antworttext.
  - **FK 2 (1-Klick WhatsApp, E-Mail & Web-Share)**: Direkte Share-Buttons am DZR-Antworttext, in Zeitanfragen und bei orangen Sperrtermin-Kollisionen.
  - **FK 3 (48h-Fristen- & Aufgaben-Cockpit)**: Einklappbares Cockpit oben im Tab `Klient:innen` für E-Casting-Fristen, offene Prio-1 Team-Aufgaben und fehlende Stammdaten/Dokumente.
  - **FK 4 (Live-iCal-Abo `.ics`)**: Modal im Kalender-Header mit Abo-URL und 1-Klick `.ics`-Download (funktioniert online über `/api/ical/{client_id}.ics` sowie komplett offline auf GitHub Pages).
  - **FK 6 (Globale Schnellsuche `Cmd+K` / `Strg+K`)**: Lupen-Icon in der Top-App-Bar sucht in Echtzeit über Klient:innen, Anfragen, Caster:innen und Team-Aufgaben.
  - **FK 7 (Reise- & Hotel-Dispo-Check)**: Erkennt abweichende Drehorte zum Wohnort und bietet 1-Klick **Travel-Rider kopieren** sowie **Anreisetag (Vortag) im Kalender blocken**.

## 2. Qualitätssicherung & Live-Betrieb
- **Test-Gate**: `19 passed` in `pytest` (`tests/test_api_e2e.py`, `tests/test_domain_and_math.py`, `tests/test_storage_and_integrity.py`).
- **GitHub Pages Mobile/Desktop PWA**: `https://robboddenberg.github.io/zta-os/`
- **Synchronisierte Verzeichnisse**:
  - `D:\G-Drive\Canvas\zta-os`
  - `D:\G-Drive\100_Canvas_Apps\Canvas_Projekte\zta-os`
  - GitHub Repository: `https://github.com/robboddenberg/zta-os`
