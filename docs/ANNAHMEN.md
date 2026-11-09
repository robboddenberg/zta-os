# ZTA OS: Architektur- & Design-Annahmen

Stand: 2026-11-09

1. **Synthetische Testphase (100 % DSGVO-konform)**:
   - Alle 20 ausgelieferten Klienten-Profile in `scripts/build_initial_data.py` sind vollstaendig fiktiv und repräsentieren realistisch die 4 Sparten der Agentur (10 Schauspiel, 4 Regie & Drehbuch, 3 NXT, 3 PR & Commercial).
   - Echte Klientendaten liegen ausschliesslich lokal in `data/data.json` und werden durch `.gitignore` niemals in Git eingecheckt.

2. **Zero-Error-Finanzlogik (Ganzzahl-Cents)**:
   - Gemäß `app_development_guidelines_richtlinien.txt` (Prinzip 3) werden sämtliche Geldbeträge als Ganzzahlen in Cent (`_cents: int`) gespeichert und über `Decimal` mit `ROUND_HALF_UP` berechnet.
   - Provisionssätze werden in Basispunkten (`commission_rate_bp: int`, z. B. `1000` = 10,00 %, `1200` = 12,00 %, `2000` = 20,00 %, `2500` = 25,00 %) gespeichert, sodass auch Bruchteile von Prozenten ohne Gleitkommafehler abbildbar sind.

3. **Auto-Offset & Event-Driven Workflows**:
   - Gemäß Prinzip 4 lösen Statusänderungen in Zeitanfragen und Verträgen automatisch konsistente Folgeaktionen in Kalender, Liquiditätsplanung und Auszahlungsstatus aus.
   - Über `/api/webhooks/ingest` können externe Automatisierungen (wie n8n) neue Anfragen, Sperrtermine oder Zahlungseingänge einspielen.

4. **Mobile-First Klienten-Ansicht (iOS Safari PWA)**:
   - Im Header kann jederzeit zwischen den 4 Rollen (*Inhaberin*, *Agentur/PR*, *Klient:in (Mobile Portal)*, *IT/Admin*) sowie dem aktuell simulierten Klienten-Profil gewechselt werden.
   - Alle Formularelemente nutzen `font-size: 16px` oder größer, um ungewollten Auto-Zoom unter iOS Safari zu verhindern.
