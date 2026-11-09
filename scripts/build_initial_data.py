"""Erzeugt den synthetischen Initialbestand (20 fiktive Profile ueber 4 Sparten) fuer ZTA OS."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import load_config
from backend.app.logic import calculate_contract_financials, compute_casting_schedule
from backend.app.models import utc_now_iso
from backend.app.storage import StorageEngine


def build_synthetic_dataset() -> dict:
    now = utc_now_iso()
    tenant = "zta-berlin"

    raw_clients = [
        # 10 Schauspiel (10 % bis 12 % Provision = 1000 bis 1200 bp)
        ("cl-01", "Mara Lindqvist", "schauspiel", "Berlin", "28-36", 1200, 185000, ["Schwedisch", "Englisch", "Reiten", "Violine"], "Charakterdarstellerin (Tatort, Nordic Noir, Arthouse Kino)."),
        ("cl-02", "Tarik Yilmaz", "schauspiel", "Berlin / Koeln", "32-40", 1200, 210000, ["Tuerkisch", "Englisch", "Boxen", "Stunt-Basics"], "Hauptrollen in High-End-Serien und Kinospielfilmen."),
        ("cl-03", "Helene von Berg", "schauspiel", "Berlin / Muenchen", "45-55", 1200, 240000, ["Franzoesisch", "Klavier", "Buehnenerfahrung"], "Ensemble- und Hauptrollen in historischen Stoffen und Dramen."),
        ("cl-04", "Jonas Karg", "schauspiel", "Berlin / Hamburg", "25-33", 1000, 145000, ["Norddeutsch", "Gitarre", "Segeln"], "Vielseitiger Charakterkopf fuer Kino, Streaming und Theater."),
        ("cl-05", "Amina Rahimi", "schauspiel", "Berlin", "24-31", 1000, 160000, ["Farsi", "Englisch", "Zeitgenoessischer Tanz"], "Preistraegerin Nachwuchspreis, Fokus Streaming-Drama und Kino."),
        ("cl-06", "Leander Paulsen", "schauspiel", "Berlin / Wien", "38-46", 1200, 195000, ["Wienerisch", "Fechten", "Bariton"], "Kino- und TV-Protagonist, regelmaessig am Burgtheater und DT."),
        ("cl-07", "franka Seidel", "schauspiel", "Berlin / Leipzig", "30-38", 1000, 155000, ["Spanisch", "Synchron", "Klettern"], "Starke Praesenz in Krimi-Reihen und Ensemble-Komoedien."),
        ("cl-08", "Matteo Rossi", "schauspiel", "Berlin / Rom", "29-37", 1200, 175000, ["Italienisch", "Englisch", "Motorrad"], "Internationale Koproduktionen und deutsche Primetime-Formate."),
        ("cl-09", "Sina Lichtwark", "schauspiel", "Berlin", "50-60", 1200, 225000, ["Englisch", "Chanson", "Hörspiel"], "Renommierte Charakterdarstellerin und gefragte Hoerspielsprecherin."),
        ("cl-10", "Bela Korff", "schauspiel", "Berlin / Zuerich", "34-42", 1000, 165000, ["Schweizerdeutsch", "Franzoesisch", "Ski Alpin"], "DACH-Crossover-Darsteller fuer Serie und Kino."),
        # 4 Regie & Drehbuch (10 % bis 12 % Provision)
        ("cl-11", "Clara Vester", "regie_drehbuch", "Berlin", "35-45", 1200, 320000, ["Serien-Regie", "Showrunnerin", "Drehbuch"], "Regisseurin fuer mehrteilige Streaming-Miniserien und Fernsehfilme."),
        ("cl-12", "David Kinski", "regie_drehbuch", "Berlin / Muenchen", "40-50", 1200, 350000, ["Kinoregie", "Writers Room", "Thriller"], "Autor und Regisseur mit Fokus auf Polit-Thriller und Festival-Stoffe."),
        ("cl-13", "Nori Sato", "regie_drehbuch", "Berlin", "31-39", 1000, 280000, ["Drehbuch", "High-Concept", "Englisch"], "Drehbuchautorin fuer deutsch-britische Koproduktionen."),
        ("cl-14", "Jakob Thaler", "regie_drehbuch", "Berlin / Hamburg", "44-52", 1200, 310000, ["Komoedie", "Freitagabend-Reihe", "Schnittaufsicht"], "Erfahrener TV- und Kinoregisseur mit hoher Termintreue."),
        # 3 NXT (Nachwuchs, 10 % Provision)
        ("cl-15", "Lilli Sonnenschein", "nxt", "Berlin", "19-24", 1000, 110000, ["UdK Berlin", "Gesang", "Skateboard"], "Absolventin Schauspielschule, erste Serien-Hauptrolle abgedreht."),
        ("cl-16", "Noah Bektas", "nxt", "Berlin", "20-26", 1000, 115000, ["Ernst Busch", "Rap", "Basketball"], "Junges Ausnahmetalent fuer Coming-of-Age und Young-Adult-Serien."),
        ("cl-17", "Mila Kowalski", "nxt", "Berlin / Warschau", "21-27", 1000, 110000, ["Polnisch", "Englisch", "Ballett"], "Zweisprachiges Nachwuchstalent mit Fokus auf europaeisches Arthouse."),
        # 3 PR & Commercial (20 % bis 25 % Provision = 2000 bis 2500 bp)
        ("cl-18", "Soraya Brandt", "pr_commercial", "Berlin", "27-35", 2000, 450000, ["Brand Ambassador", "Moderation", "Beauty & Tech"], "Testimonial fuer internationale Kampagnen, Keynotes und Red-Carpet-PR."),
        ("cl-19", "Viktor Falk", "pr_commercial", "Berlin / Frankfurt", "36-44", 2500, 520000, ["Automotive", "Voice-Over", "Event-Host"], "Markengesicht fuer Premium-Kampagnen, TV-Spots und Corporate Events."),
        ("cl-20", "Elena Moretti", "pr_commercial", "Berlin / Mailand", "26-34", 2000, 400000, ["Fashion PR", "Editorial", "Italienisch"], "Luxus- und Lifestyle-Kooperationen, Print-Strecken und Bewegtbild-Spots."),
    ]

    clients = {}
    for cid, name, div, loc, age_range, comm_bp, fee_cents, skills, bio in raw_clients:
        fixed_name = name[0].upper() + name[1:]
        clients[cid] = {
            "name": fixed_name,
            "division": div,
            "location": loc,
            "playing_age": age_range,
            "commission_rate_bp": comm_bp,
            "default_daily_fee_cents": fee_cents,
            "skills": skills,
            "bio": bio,
            "email": f"{cid}@synthetisch.zta-os.local",
            "phone": f"+49 170 555{cid[-2:]}00",
            "ical_token": f"tok-{cid}-zta2026",
            "status": "active",
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 36 realistische Kalendereintraege im November / Dezember 2026
    raw_events = [
        ("ev-01", "cl-01", "dzr", "Tatort Berlin: Stille Wasser (DZR)", "rbb / ARD Degeto", "2026-11-04", "2026-11-18", True, 0, "confirmed"),
        ("ev-02", "cl-01", "dt", "Drehtag 1-3 Tatort Berlin", "rbb / ARD Degeto", "2026-11-10", "2026-11-12", True, 0, "confirmed"),
        ("ev-03", "cl-01", "sperr", "Familienhochzeit Stockholm", "", "2026-11-21", "2026-11-23", True, 0, "confirmed"),
        ("ev-04", "cl-01", "nachsyn", "ADR Studio Babelsberg", "UFA Fiction", "2026-11-26", "2026-11-26", True, 0, "confirmed"),
        ("ev-05", "cl-02", "option", "Serie: Nachtschicht X (1. Option)", "Wiedemann & Berg", "2026-11-09", "2026-11-15", True, 1, "tentative"),
        ("ev-06", "cl-02", "dt", "Drehtag Kinospielfilm 'Glut'", "Komplizen Film", "2026-11-19", "2026-11-22", True, 0, "confirmed"),
        ("ev-07", "cl-02", "sperr", "Zahnarzt / Privat", "", "2026-11-27", "2026-11-27", True, 0, "confirmed"),
        ("ev-08", "cl-03", "dzr", "Historienserie 'Die Konigin' Block 2", "Constantin Television", "2026-11-02", "2026-11-14", True, 0, "confirmed"),
        ("ev-09", "cl-03", "aufnahme", "Hoerspiel WDR (Studio Koeln)", "WDR", "2026-11-24", "2026-11-25", True, 0, "confirmed"),
        ("ev-10", "cl-04", "option", "SOKO Potsdam (1. Option)", "Bantry Bay", "2026-11-11", "2026-11-14", True, 1, "tentative"),
        ("ev-11", "cl-04", "sperr", "Theatergastspiel Kampnagel", "Kampnagel Hamburg", "2026-11-20", "2026-11-22", True, 0, "confirmed"),
        ("ev-12", "cl-05", "dt", "Netflix-Serie 'Echoes' Drehtage", "Gaumont Germany", "2026-11-08", "2026-11-13", True, 0, "confirmed"),
        ("ev-13", "cl-05", "casting", "Live-Recall Kinofilm 'Nordwind'", "Anja Dihrberg Casting", "2026-11-17", "2026-11-17", False, 0, "confirmed"),
        ("ev-14", "cl-06", "sperr", "Vorstellungsserie Burgtheater Wien", "Burgtheater", "2026-11-05", "2026-11-10", True, 0, "confirmed"),
        ("ev-15", "cl-06", "option", "ZDF-Mehrteiler 'Der Hafen' (1. Option)", "Network Movie", "2026-11-16", "2026-11-25", True, 1, "tentative"),
        ("ev-16", "cl-07", "dt", "Erzgebirgskrimi Drehtag", "NFP", "2026-11-12", "2026-11-14", True, 0, "confirmed"),
        ("ev-17", "cl-08", "option", "International Thriller 'Torino' (1. Option)", "Cattleya / Beta", "2026-11-15", "2026-11-24", True, 1, "tentative"),
        ("ev-18", "cl-09", "aufnahme", "Deutschlandfunk Kultur Hoerspiel", "DLF Kultur", "2026-11-09", "2026-11-11", True, 0, "confirmed"),
        ("ev-19", "cl-10", "sperr", "Urlaub Engadin", "", "2026-11-25", "2026-11-30", True, 0, "confirmed"),
        ("ev-20", "cl-11", "dzr", "Regie-Vorbereitung Miniserie 'Kaltfront'", "Studio Hamburg", "2026-11-03", "2026-11-28", True, 0, "confirmed"),
        ("ev-21", "cl-12", "option", "Drehbuch-Klausur Staffel 2", "X Filme", "2026-11-16", "2026-11-20", True, 1, "tentative"),
        ("ev-22", "cl-13", "sperr", "Pitching-Tage London", "", "2026-11-18", "2026-11-20", True, 0, "confirmed"),
        ("ev-23", "cl-14", "dt", "Schnittabnahme Feinschnitt", "Ziegler Film", "2026-11-10", "2026-11-13", True, 0, "confirmed"),
        ("ev-24", "cl-15", "casting", "Kamera-Casting 'Junges Licht'", "Suse Marquardt Casting", "2026-11-12", "2026-11-12", False, 0, "confirmed"),
        ("ev-25", "cl-16", "option", "ARD Mediathek Serie 'Block 36' (1. Option)", "Sommerhaus", "2026-11-17", "2026-11-26", True, 1, "tentative"),
        ("ev-26", "cl-17", "sperr", "Pruefungswoche Schauspielschule", "", "2026-11-09", "2026-11-13", True, 0, "confirmed"),
        ("ev-27", "cl-18", "dt", "Global Beauty Campaign Shoot Paris", "L'Aurore Paris", "2026-11-11", "2026-11-13", True, 0, "confirmed"),
        ("ev-28", "cl-19", "option", "E-Mobility TV-Spot (1. Option)", "Jung von Matt / Markenfilm", "2026-11-18", "2026-11-20", True, 1, "tentative"),
        ("ev-29", "cl-20", "dt", "Editorial & Social Shoot Mailand", "Studio Milano", "2026-11-14", "2026-11-16", True, 0, "confirmed"),
        ("ev-30", "cl-01", "option", "Kinofilm 'Winterlicht' (1. Option Dez)", "Walker + Worm", "2026-12-03", "2026-12-14", True, 1, "tentative"),
    ]

    calendar_events = {}
    for ev_id, cid, ev_type, title, prod, s_date, e_date, all_day, opt_rank, status in raw_events:
        calendar_events[ev_id] = {
            "client_id": cid,
            "event_type": ev_type,
            "title": title,
            "production_company": prod,
            "start_date": s_date,
            "end_date": e_date,
            "all_day": all_day,
            "option_rank": opt_rank,
            "expires_at": "2026-11-16" if ev_type == "option" else "",
            "status": status,
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 8 realistische Zeitanfragen (inquiries)
    raw_inquiries = [
        ("inq-01", "cl-01", "ZDF-Herzkino: Stuerme ueber Ruegen", "Relevant Film", "Katja Behrens", "2026-11-19", "2026-11-25", 4, 740000, "open", "pending"),
        ("inq-02", "cl-02", "Polizeiruf 110: Grenzgang", "Filmpool Fiction", "Markus Lindner", "2026-11-10", "2026-11-14", 3, 630000, "open", "fits"),
        ("inq-03", "cl-04", "Nord Nord Mord: Kalte Gischt", "Network Movie", "Simone Kroll", "2026-11-12", "2026-11-18", 4, 580000, "open", "pending"),
        ("inq-04", "cl-05", "Kinospielfilm 'Transit 99'", "23/5 Filmproduktion", "Hannah Weiss", "2026-11-23", "2026-11-29", 5, 800000, "open", "fits"),
        ("inq-05", "cl-07", "Grossstadtrevier Staffel 39", "Letterbox Filmproduktion", "Janick Voigt", "2026-11-16", "2026-11-20", 3, 465000, "open", "pending"),
        ("inq-06", "cl-12", "Regie-Anfrage 'Schattenkabinett' (6 Folgen)", "Real Film Berlin", "Dr. Miriam Roth", "2026-11-15", "2026-11-24", 8, 2800000, "open", "question"),
        ("inq-07", "cl-16", "Netflix Young-Adult 'Neonstadt'", "Bilkis Film", "Elena Sturm", "2026-11-18", "2026-11-24", 4, 460000, "open", "pending"),
        ("inq-08", "cl-18", "Tech-Keynote & Kampagne 'FutureNow 2026'", "Scholz & Friends", "finn Berger", "2026-11-24", "2026-11-26", 2, 950000, "open", "fits"),
    ]

    inquiries = {}
    for iid, cid, proj, prod, contact, s_date, e_date, days, gage_cents, st, c_resp in raw_inquiries:
        inquiries[iid] = {
            "client_id": cid,
            "project_title": proj,
            "production_company": prod,
            "contact_person": contact[0].upper() + contact[1:],
            "start_date": s_date,
            "end_date": e_date,
            "requested_shooting_days": days,
            "offered_gage_cents": gage_cents,
            "status": st,
            "client_response": c_resp,
            "client_comment": "Klingt super, Drehbuch-Auszug waere toll!" if c_resp == "question" else "",
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 6 Castings & E-Castings (mit automatischem Sichtungstermin 2 Tage vor Deadline)
    raw_castings = [
        ("cast-01", "cl-01", "Kinofilm 'Glasstadt'", "Kommissarin Maja Holm", "Nina Haun Casting", "e_casting", "2026-11-11", "open", "fits", "https://dropbox.zta-os.local/tapes/cast-01"),
        ("cast-02", "cl-04", "ARD-Eventserie '1989'", "Journalist Paul", "Siegfried Wagner Casting", "e_casting", "2026-11-13", "tape_uploaded", "fits", "https://dropbox.zta-os.local/tapes/cast-02"),
        ("cast-03", "cl-05", "Streaming-Thriller 'Dark Fiber'", "Lead: Daria", "Emrah Ertem Casting", "live_casting", "2026-11-15", "open", "pending", ""),
        ("cast-04", "cl-15", "Kino-Debuet 'Sommerflimmern'", "Hauptrolle Cleo", "Liza Stutzky Casting", "e_casting", "2026-11-10", "open", "question", "https://dropbox.zta-os.local/tapes/cast-04"),
        ("cast-05", "cl-17", "EU-Koproduktion 'Baltic Wind'", "Klara", "Boesen & Martell", "e_casting", "2026-11-18", "open", "fits", ""),
        ("cast-06", "cl-19", "Commercial 'Alpine Luxury Watch'", "Hero Testimonial", "SpotCast Berlin", "e_casting", "2026-11-12", "submitted", "fits", "https://dropbox.zta-os.local/tapes/cast-06"),
    ]

    castings = {}
    for cast_id, cid, proj, role_name, cd, c_type, dl_date, t_status, c_resp, link in raw_castings:
        sched = compute_casting_schedule(dl_date, reference_date="2026-11-09", tape_status=t_status)
        castings[cast_id] = {
            "client_id": cid,
            "project_title": proj,
            "role_name": role_name,
            "casting_director": cd,
            "casting_type": c_type,
            "deadline_date": sched["deadline_date"],
            "internal_review_date": sched["internal_review_date"],
            "tape_status": t_status,
            "client_response": c_resp,
            "upload_link": link,
            "urgency": sched["urgency"],
            "countdown_label": sched["countdown_label"],
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 10 Vertraege (alle Betraege exakt in Cent berechnet)
    raw_contracts = [
        ("con-01", "cl-01", "Tatort Berlin: Stille Wasser", "rbb / ARD Degeto", "schauspiel", "final_signed", 8, 1480000, 0, 1200, "2026-11"),
        ("con-02", "cl-02", "Kinospielfilm 'Glut'", "Komplizen Film", "schauspiel", "invoiced", 6, 1260000, 0, 1200, "2026-11"),
        ("con-03", "cl-03", "Historienserie 'Die Koenigin' Block 2", "Constantin Television", "schauspiel", "paid", 10, 2400000, 0, 1200, "2026-10"),
        ("con-04", "cl-05", "Netflix-Serie 'Echoes'", "Gaumont Germany", "schauspiel", "final_signed", 6, 960000, 150000, 1000, "2026-11"),
        ("con-05", "cl-07", "Erzgebirgskrimi Folge 14", "NFP", "schauspiel", "paid", 3, 465000, 0, 1000, "2026-10"),
        ("con-06", "cl-11", "Regievertrag Miniserie 'Kaltfront'", "Studio Hamburg", "regie_drehbuch", "final_signed", 25, 4500000, 0, 1200, "2026-12"),
        ("con-07", "cl-14", "TV-Komoedie 'Verliebt in Lissabon'", "Ziegler Film", "regie_drehbuch", "invoiced", 22, 3800000, 0, 1200, "2026-11"),
        ("con-08", "cl-15", "ZDFneo-Serie 'Wach'", "Turbokultur", "nxt", "negotiation", 5, 550000, 0, 1000, "2026-12"),
        ("con-09", "cl-18", "Global Beauty Campaign 'L'Aurore'", "L'Aurore Paris", "pr_commercial", "final_signed", 3, 1200000, 1800000, 2000, "2026-11"),
        ("con-10", "cl-19", "Automotive Jahres-Kampagne 2026", "Jung von Matt", "pr_commercial", "paid", 4, 1500000, 2500000, 2500, "2026-10"),
    ]

    contracts = {}
    for con_id, cid, proj, prod, div, status, days, gage_c, buyout_c, rate_bp, pay_month in raw_contracts:
        calc = calculate_contract_financials(
            division=div,
            gage_cents=gage_c,
            buyout_cents=buyout_c,
            commission_rate_bp=rate_bp,
            engagement_days=days,
        )
        is_paid = status == "paid"
        contracts[con_id] = {
            "client_id": cid,
            "project_title": proj,
            "production_company": prod,
            "division": div,
            "status": status,
            "engagement_days": days,
            "gage_cents": calc["gage_cents"],
            "buyout_cents": calc["buyout_cents"],
            "total_gross_cents": calc["total_gross_cents"],
            "commission_rate_bp": calc["commission_rate_bp"],
            "commission_cents": calc["commission_cents"],
            "agency_vat_cents": calc["agency_vat_cents"],
            "client_payout_cents": calc["client_payout_cents"],
            "paid_amount_cents": calc["commission_cents"] if is_paid else 0,
            "outstanding_cents": 0 if is_paid else calc["commission_cents"],
            "payout_month": pay_month,
            "client_payout_status": "freigegeben_zum_monatsende" if is_paid else "geplant_zum_monatsende",
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 12 Zeiterfassungs-Eintraege (time_logs) fuer Aufwand-vs.-Provisions-Auswertung
    raw_time_logs = [
        ("tl-01", "cl-01", "Vertragsverhandlung & Dispo Tatort Berlin", "dispo", 180, "2026-11-02"),
        ("tl-02", "cl-01", "E-Casting Sichtung & Feedback 'Glasstadt'", "casting", 75, "2026-11-08"),
        ("tl-03", "cl-02", "Drehplan-Abgleich 'Glut' & Optionen", "dispo", 150, "2026-11-04"),
        ("tl-04", "cl-03", "Reise- & Vertragsabrechnung Block 2", "vertrag", 210, "2026-10-28"),
        ("tl-05", "cl-04", "Terminkoordination SOKO + Kampnagel", "dispo", 120, "2026-11-06"),
        ("tl-06", "cl-05", "Buyout-Verhandlung Netflix 'Echoes'", "vertrag", 160, "2026-11-05"),
        ("tl-07", "cl-11", "Stufenvertrag Regie 'Kaltfront' Pruefung", "vertrag", 240, "2026-11-03"),
        ("tl-08", "cl-14", "Abrechnung & Schnitt-Termine Lissabon", "vertrag", 135, "2026-11-07"),
        ("tl-09", "cl-15", "Aufbau-Coaching & Demoband-Sichtung", "betreuung", 190, "2026-11-04"),
        ("tl-10", "cl-18", "PR-Briefing & Buyout-Klaerung Paris", "pr", 140, "2026-11-06"),
        ("tl-11", "cl-19", "Exklusivitaets-Pruefung Automotive", "pr", 165, "2026-10-25"),
        ("tl-12", "cl-07", "Nachsynchron- und Drehtagkoordination", "dispo", 90, "2026-11-01"),
    ]

    time_logs = {}
    for tl_id, cid, desc, cat, mins, d_str in raw_time_logs:
        time_logs[tl_id] = {
            "client_id": cid,
            "description": desc,
            "category": cat,
            "duration_minutes": mins,
            "log_date": d_str,
            "logged_by": "Zetha",
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 6 In-App-Feedback- & Triage-Eintraege (aus dem ZTA OS Projekt-Hub)
    raw_feedback = [
        ("FB-001", "Antwortvorlage soll bestehende Optionen mit Rang nennen", "Wenn im Zeitraum schon eine 1. Option liegt, soll der Text automatisch eine 2. Option vorschlagen.", "wunsch", "erledigt", "inhaberin", "Zetha", "inquiries"),
        ("FB-002", "Interner Sichtungstermin bei E-Castings (2 Tage vor Frist)", "Wir muessen die Tapes 48 Stunden vor Casting-Deadline sichten koennen.", "wunsch", "erledigt", "inhaberin", "Zetha", "castings"),
        ("FB-003", "Warnhinweis im Klienten-Portal bei Sperrtermin-Konflikten", "Wenn ein Klient auf dem iPhone einen Sperrtermin eintraegt, wo schon eine Option liegt, sofort gelb warnen.", "wunsch", "umgesetzt_zu_pruefen", "inhaberin", "Zetha", "portal"),
        ("FB-004", "PR & Commercial Provision auf 20 % bis 25 % voreinstellen", "In der PR-Sparte gelten andere Saetze als in der klassischen Schauspielvermittlung.", "wunsch", "erledigt", "agentur", "PR-Leitung", "contracts"),
        ("FB-005", "Gagen-Auszahlungsregel (Monatsende) im Portal erklaeren", "Spart uns jede Woche 5 Rueckfragen per WhatsApp, wann das Geld ueberwiesen wird.", "idee", "umgesetzt_zu_pruefen", "inhaberin", "Zetha", "portal"),
        ("FB-006", "Dunkelmodus fuer abendliche Drehbuch- und Tape-Sichtung", "Abends am Laptop und iPhone bitte ein ruhiges dunkles Studio-Theme.", "wunsch", "erledigt", "inhaberin", "Zetha", "cockpit"),
    ]

    feedback_items = {}
    for fb_id, title, desc, cat, st, role, name, view_ctx in raw_feedback:
        feedback_items[fb_id] = {
            "title": title,
            "description": desc,
            "category": cat,
            "status": st,
            "reported_by_role": role,
            "reported_by_name": name,
            "view_context": view_ctx,
            "element_selector": "",
            "device_hint": "iPhone Safari / Desktop",
            "app_version": "1.0.0",
            "created_at": now,
            "updated_at": now,
            "tenant_id": tenant,
        }

    settings = {
        "agency_profile": {
            "agency_name": "ZTA Management Berlin",
            "default_tenant_id": tenant,
            "payout_policy": "Auszahlung von Klientengagen erfolgt gesammelt zum Monatsende nach Zahlungseingang.",
            "casting_review_lead_days": 2,
            "synthetic_test_mode": True,
            "updated_at": now,
        }
    }

    return {
        "clients": clients,
        "calendar_events": calendar_events,
        "inquiries": inquiries,
        "castings": castings,
        "contracts": contracts,
        "time_logs": time_logs,
        "feedback_items": feedback_items,
        "audit_logs": {},
        "settings": settings,
    }


def main() -> None:
    cfg = load_config()
    storage = StorageEngine(cfg.data_path)
    storage.ensure_dirs()
    dataset = build_synthetic_dataset()
    state = storage.write_new_state(dataset)
    print(
        f"[ZTA OS Seeding] {len(dataset['clients'])} synthetische Klienten-Profile, "
        f"{len(dataset['calendar_events'])} Termine, {len(dataset['inquiries'])} Zeitanfragen, "
        f"{len(dataset['castings'])} Castings und {len(dataset['contracts'])} Vertraege "
        f"in '{cfg.data_path}' gespeichert (Revision {state['meta']['revision']})."
    )


if __name__ == "__main__":
    main()
