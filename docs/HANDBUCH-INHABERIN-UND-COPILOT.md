# ZTA OS V10.2: Handbuch fuer die Inhaberin (Zetha) & AI Co-Pilot Guide

Willkommen bei **ZTA OS**! Dieses Handbuch erklaert Schritt fuer Schritt und ohne Technik-Fachchinesisch, wie Sie die App im Agentur-Alltag auf dem Handy und Desktop nutzen, wie Ihre Klient:innen sich anmelden koennen und wie Sie Ihren **Claude AI Co-Pilot** direkt mit der App verbinden.

---

## 1. App am Handy und am Computer oeffnen & als App installieren

Sie koennen ZTA OS jederzeit ueber diesen Link oeffnen:
`https://robboddenberg.github.io/zta-os/`

### iPhone / iPad (Safari):
1. Oeffnen Sie den Link in **Safari**.
2. Tippen Sie unten in der Mitte auf das **Teilen-Symbol** (Quadrat mit Pfeil nach oben).
3. Waehlen Sie **"Zum Home-Bildschirm"** und tippen Sie oben rechts auf **"Hinzufuegen"**.
4. Danach erscheint das ZTA-Icon wie eine normale App auf Ihrem Homescreen.

### Android (Chrome):
1. Oeffnen Sie den Link in **Google Chrome**.
2. Tippen Sie oben rechts auf die **drei Punkte** und waehlen Sie **"App installieren"** bzw. **"Zum Startbildschirm hinzufuegen"**.

---

## 2. Anmeldung & echte Rollen (Team ZTA vs. Klient:in)

Auf dem Startbildschirm (Splash-Screen in ZTA Light Pink) gibt es drei Moeglichkeiten:

1. **Team ZTA (Agentur-Ansicht):** Vollzugriff auf alle 5 Departments (*Actors, Directors + Writers, NXT, PR & Commercial, Consulting*), Sperrtermin-Rechner, Gagen-Spiegel, Vertraege, Stammdaten, KI Co-Pilot und Zugangsrechte.
2. **Klient:in (Demo-Vorschau):** Zum Testen der eingeschraenkten Sicht.
3. **Persoenlicher Zugangscode (Echter Login):**
   - **Zetha (Super-Admin):** `ZTA-ADMIN-2026`
   - **Team Disposition:** `ZTA-TEAM-2026`
   - **Beispiel Langzeit-Klient:in (z. B. Mara Lindqvist):** `ZTA-CL01-2026` (jeweils `ZTA-CL01-2026` bis `ZTA-CL20-2026`)

> **Wichtige Sicherheitsregel (Strict RBAC):**
> Wenn sich eine Klient:in mit ihrem persoenlichen Code anmeldet, ist der Rollen-Wechsel im Header gesperrt. Sie sieht ausschliesslich ihren eigenen Kalender, darf eigene Sperrtermine eintragen und sieht **niemals** interne Auswertungen, Gagen-Spiegel-Einzelgagen anderer oder Referenz-Deals.
> Klient:innen aus **Consulting** oder **projektbezogener PR** sind standardmaessig gesperrt (`403 Forbidden`), koennen aber von Ihnen jederzeit im Reiter **Zugangsrechte** freigeschaltet werden.

---

## 3. Die 5 Haupt-Tabs im Agentur-Alltag

1. **From Z to A (Klient:innen):** Alle Talente nach Departments gegliedert. Ein Klick oeffnet direkt das Profil.
2. **Kalender & Sperrtermine:**
   - **ZTA Blue (`#0A1AE4` gefuellt):** Drehtage, ADR, Store Openings, Festivals.
   - **ZTA Blue umrandet:** E-Castings & Live-Castings.
   - **Orange:** Weicher Sperrtermin (unter Vorbehalt).
   - **Rot:** Verbindlicher Sperrtermin (Ort ist Pflichtfeld wegen An- und Abreisetagen!).
   - **Sperrtermin-Rechner (nur Team ZTA):** Start- und Enddatum eines angefragten Drehzeitraums (DZR) eingeben. Der Zeitraum wird in ZTA Pink hervorgehoben, alle Konflikte werden geprueft und Sie erhalten einen kopierfertigen Antwort-Text fuer das Casting-Buero.
3. **Zeitanfragen & Casting-Pipeline:** Zeitanfragen anlegen, E-Casting-Deadlines eintragen (automatische 48-Stunden-Erinnerung fuer die interne ZTA-Sichtung!) und den Dropbox-Vertragslink hinterlegen.
4. **Gagen-Spiegel:** Last Achieved vs. aktuelle Richtgage (MW / MA sowie ZDF-Laengenformel `MWF`, `MW60`, `MWFA`) und Zielgage 2027. Bei Abschluss ueber dem Richtwert wird die Richtgage automatisch angehoben.
5. **Stammdaten & Dokumente:** Plausibilitaetspruefung fuer IBAN (22 Zeichen), BIC, Steuer-ID (11 Ziffern, Schutz vor USt-IdNr.-Verwechslung), SV-Nummer und Checkliste (Steuerklasse-6-Schutz, PKV-Bescheinigung, Geburtsurkunde Kind).

---

## 4. Der Executive AI Co-Pilot & die 9 Playbooks (A bis I)

Oben rechts in der Leiste (nur fuer **Team ZTA** sichtbar) finden Sie den Button **"AI Co-Pilot & Handbuch"**. Dort koennen Sie mit einem Klick 9 fertige Agentur-Assistenten ausfuehren:

- **Playbook A (Weekly Executive Briefing):** *"Was steht diese Woche an?"* Zeigt alle kritischen 48h-Castings, bestaetigte Drehtage, offene Zeitanfragen und den Provisions-Snapshot.
- **Playbook B (News & Notification Triage):** Sortiert alle Neuigkeiten in **Rot (Sofort handeln)**, **Orange (Ruecksprache)** und **Blau (Info)**.
- **Playbook C (DZR-Verfuegbarkeit & Gagen-Check):** Prueft fuer eine Klient:in einen Drehzeitraum inkl. Richtgage und fertigem Antworttext.
- **Playbook D (Booking & Auto-Offset):** Fuehrt einen Vertragsabschluss aus, berechnet Gage, Provision und Auszahlung exakt auf den Cent und traegt den Drehtag in den Kalender ein. **Mit Sicherheits-Abfrage (`CONFIRM` / `CANCEL`)!**
- **Playbook E (Stammblatt & Payroll Readiness):** Findet sofort fehlende Steuer-IDs, falsche IBANs oder fehlende Dokumente, damit niemand versehentlich in Steuerklasse 6 abgerechnet wird.
- **Playbook F (48h E-Casting & Recall Radar):** Alle laufenden Castings sortiert nach interner ZTA-Sichtungsfrist (2 Tage vor Caster-Deadline).
- **Playbook G (Jahresgespraech & Gagen-Upgrade Dossier):** Komplettes Vorbereitungs-Dossier mit 4 Branchen-Indikatoren, Referenz-Deals und Gagen-Ziel 2027.
- **Playbook H (Multi-Talent Besetzungs-Matcher):** *"Wer aus unserem Actors-Roster ist vom 18. bis 26.11. komplett frei?"* Ideal fuer spontane Caster-Anfragen.
- **Playbook I (Zugangsrechte & Rollen-Governance):** Zeigt alle Konten, Rollen und Login-Codes auf einen Blick. Im Reiter **"Zugangsrechte"** koennen Sie per Klick einzelne Klient:innen freischalten oder sperren.

---

## 5. Ihren eigenen Claude Agenten direkt mit ZTA OS verbinden

Sie koennen **Claude** so einrichten, dass Claude direkt Ihre ZTA-OS Daten abfragen, DZR-Checks fahren oder Zugangsrechte fuer Sie verwalten kann:

### Variante A: Claude Desktop (mit MCP Server)
1. Starten Sie lokal den ZTA-OS Server (`uvicorn backend.app.main:app --port 8020`).
2. Oeffnen Sie in Claude Desktop die Datei `claude_desktop_config.json` und tragen Sie `scripts/zta_mcp_server.py` ein (eine fertige Kopiervorlage finden Sie direkt in der App im Reiter **"Claude & Handbuch"**).
3. Danach koennen Sie Claude einfach fragen: *"Claude, mach mir das Weekly Briefing fuer ZTA"* oder *"Pruefe ob Mara Lindqvist vom 18. bis 26.11. frei ist"*.

### Variante B: Claude Projekt / Custom GPT (mit System-Prompt & OpenAPI)
1. Im Reiter **"Claude & Handbuch"** innerhalb der App klicken Sie auf **"System-Prompt kopieren"**.
2. Fuegen Sie diesen Prompt als Projekt-Anweisung in Ihrem Claude-Projekt ein.
3. Optional koennen Sie ueber `/api/copilot/openapi.json` die komplette API-Schnittstelle anbinden.
