"""Erzeugt den synthetischen V10-Initialbestand (20 fiktive Profile, 5 Departments, 50 Features) fuer ZTA OS."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import load_config
from backend.app.logic import (
    calculate_contract_financials,
    compute_casting_schedule,
    evaluate_inquiry_v10,
)
from backend.app.models import utc_now_iso
from backend.app.storage import StorageEngine


def _make_avatar_svg_url(initials: str, bg_hex: str = "#F2D2C7", fg_hex: str = "#0A1AE4") -> str:
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120'>"
        f"<circle cx='60' cy='60' r='58' fill='{bg_hex}' stroke='{fg_hex}' stroke-width='2.5'/>"
        f"<text x='60' y='71' font-family='Helvetica,Arial,sans-serif' font-size='34' font-weight='700' "
        f"fill='{fg_hex}' text-anchor='middle'>{initials}</text></svg>"
    )
    return "data:image/svg+xml;utf8," + svg.replace("#", "%23").replace(" ", "%20")


def build_synthetic_dataset() -> dict:
    now = utc_now_iso()
    tenant = "zta-berlin"

    raw_clients = [
        # 10 Actors (division='schauspiel', department='actors', Langzeit mit App-Zugang)
        ("cl-01", "Mara Lindqvist", "schauspiel", "actors", True, "langzeit", "Berlin", "28-36", 1200, 185000, ["Schwedisch", "Englisch", "Reiten", "Violine"], "Charakterdarstellerin (Tatort, Nordic Noir, Arthouse Kino).", True),
        ("cl-02", "Tarik Yilmaz", "schauspiel", "actors", True, "langzeit", "Berlin / Koeln", "32-40", 1200, 210000, ["Tuerkisch", "Englisch", "Boxen", "Stunt-Basics"], "Hauptrollen in High-End-Serien und Kinospielfilmen.", False),
        ("cl-03", "Helene von Berg", "schauspiel", "actors", True, "langzeit", "Berlin / Muenchen", "45-55", 1200, 240000, ["Franzoesisch", "Klavier", "Buehnenerfahrung"], "Ensemble- und Hauptrollen in historischen Stoffen und Dramen.", True),
        ("cl-04", "Jonas Karg", "schauspiel", "actors", True, "langzeit", "Berlin / Hamburg", "25-33", 1000, 145000, ["Norddeutsch", "Gitarre", "Segeln"], "Vielseitiger Charakterkopf fuer Kino, Streaming und Theater.", False),
        ("cl-05", "Amina Rahimi", "schauspiel", "actors", True, "langzeit", "Berlin", "24-31", 1000, 160000, ["Farsi", "Englisch", "Zeitgenoessischer Tanz"], "Preistraegerin Nachwuchspreis, Fokus Streaming-Drama und Kino.", False),
        ("cl-06", "Leander Paulsen", "schauspiel", "actors", True, "langzeit", "Berlin / Wien", "38-46", 1200, 195000, ["Wienerisch", "Fechten", "Bariton"], "Kino- und TV-Protagonist, regelmaessig am Burgtheater und DT.", True),
        ("cl-07", "Franka Seidel", "schauspiel", "actors", True, "langzeit", "Berlin / Leipzig", "30-38", 1000, 155000, ["Spanisch", "Synchron", "Klettern"], "Starke Praesenz in Krimi-Reihen und Ensemble-Komoedien.", False),
        ("cl-08", "Matteo Rossi", "schauspiel", "actors", True, "langzeit", "Berlin / Rom", "29-37", 1200, 175000, ["Italienisch", "Englisch", "Motorrad"], "Internationale Koproduktionen und deutsche Primetime-Formate.", False),
        ("cl-09", "Sina Lichtwark", "schauspiel", "actors", True, "langzeit", "Berlin", "50-60", 1200, 225000, ["Englisch", "Chanson", "Hoerspiel"], "Renommierte Charakterdarstellerin und gefragte Hoerspielsprecherin.", False),
        ("cl-10", "Bela Korff", "schauspiel", "actors", True, "langzeit", "Berlin / Zuerich", "34-42", 1000, 165000, ["Schweizerdeutsch", "Franzoesisch", "Ski Alpin"], "DACH-Crossover-Darsteller fuer Serie und Kino.", False),
        # 4 Directors + Writers (division='regie_drehbuch', department='directors_writers', Langzeit)
        ("cl-11", "Clara Vester", "regie_drehbuch", "directors_writers", True, "langzeit", "Berlin", "35-45", 1200, 320000, ["Serien-Regie", "Showrunnerin", "Drehbuch"], "Regisseurin fuer mehrteilige Streaming-Miniserien und Fernsehfilme.", True),
        ("cl-12", "David Kinski", "regie_drehbuch", "directors_writers", True, "langzeit", "Berlin / Muenchen", "40-50", 1200, 350000, ["Kinoregie", "Writers Room", "Thriller"], "Autor und Regisseur mit Fokus auf Polit-Thriller und Festival-Stoffe.", False),
        ("cl-13", "Nori Sato", "regie_drehbuch", "directors_writers", True, "langzeit", "Berlin", "31-39", 1000, 280000, ["Drehbuch", "High-Concept", "Englisch"], "Drehbuchautorin fuer deutsch-britische Koproduktionen.", False),
        ("cl-14", "Jakob Thaler", "regie_drehbuch", "directors_writers", True, "langzeit", "Berlin / Hamburg", "44-52", 1200, 310000, ["Komoedie", "Freitagabend-Reihe", "Schnittaufsicht"], "Erfahrener TV- und Kinoregisseur mit hoher Termintreue.", False),
        # 3 NXT (division='nxt', department='nxt', Langzeit-Nachwuchs)
        ("cl-15", "Lilli Sonnenschein", "nxt", "nxt", True, "langzeit", "Berlin", "19-24", 1000, 110000, ["UdK Berlin", "Gesang", "Skateboard"], "Absolventin Schauspielschule, erste Serien-Hauptrolle abgedreht.", False),
        ("cl-16", "Noah Bektas", "nxt", "nxt", True, "langzeit", "Berlin", "20-26", 1000, 115000, ["Ernst Busch", "Rap", "Basketball"], "Junges Ausnahmetalent fuer Coming-of-Age und Young-Adult-Serien.", False),
        ("cl-17", "Mila Kowalski", "nxt", "nxt", True, "langzeit", "Berlin / Warschau", "21-27", 1000, 110000, ["Polnisch", "Englisch", "Ballett"], "Zweisprachiges Nachwuchstalent mit Fokus auf europaeisches Arthouse.", False),
        # 3 PR & Commercial / Consulting (inkl. projektbezogen ohne eigenen App-Zugang gemaess Regel 42!)
        ("cl-18", "Soraya Brandt", "pr_commercial", "pr_commercial", True, "langzeit", "Berlin", "27-35", 2000, 450000, ["Brand Ambassador", "Moderation", "Red Carpet PR"], "Langzeit-PR-Klientin fuer Markenbotschaften, Keynotes und Red-Carpet.", False),
        ("cl-19", "Viktor Falk", "pr_commercial", "pr_commercial", False, "projektbezogen", "Berlin / Frankfurt", "36-44", 2500, 520000, ["Projekt-PR", "Voice-Over", "Event-Host"], "Projektbezogener PR-Klient (kein eigener Klienten-Login gemaess Feature 42).", False),
        ("cl-20", "Elena Moretti", "pr_commercial", "consulting", False, "projektbezogen", "Berlin / Mailand", "26-34", 2000, 400000, ["Consulting", "Festival-Strategie", "Positionierung"], "Consulting-Mandat (Projekt-Klientin ohne eigenen App-Zugang gemaess Feature 42).", False),
    ]

    clients = {}
    for cid, name, div, dept, has_access, eng_type, loc, age_range, comm_bp, fee_cents, skills, bio, has_kids in raw_clients:
        parts = name.split(" ")
        initials = (parts[0][0] + parts[-1][0]).upper()
        num_suffix = cid[-2:]
        clients[cid] = {
            "name": name,
            "photo_url": _make_avatar_svg_url(initials),
            "division": div,
            "department": dept,
            "has_app_access": has_access,
            "engagement_type": eng_type,
            "location": loc,
            "playing_age": age_range,
            "commission_rate_bp": comm_bp,
            "default_daily_fee_cents": fee_cents,
            "skills": skills,
            "bio": bio,
            "email": f"{cid}@synthetisch.zta-os.local",
            "phone": f"+49 170 555{num_suffix}00",
            "ical_token": f"tok-{cid}-zta2026",
            "aliases": {
                "legal_name": f"{name} (Amtlich)",
                "stage_name": name,
                "nickname": parts[0],
                "billing_company": f"{parts[-1]} Media GbR" if dept == "directors_writers" else "",
            },
            "master_data": {
                "address": {
                    "value": f"Torstrasse 1{num_suffix}, 10119 Berlin",
                    "valid_from": "2026-01-01",
                    "source_doc": "Meldebescheinigung 2026",
                    "confirmed_by": "Zetha",
                    "history": [
                        {
                            "old_value": f"Kastanienallee {num_suffix}, 10435 Berlin",
                            "valid_from": "2023-04-01",
                            "source_doc": "Altes Stammblatt 2023",
                        }
                    ],
                },
                "iban": {
                    "value": f"DE893704004405320130{num_suffix}",
                    "valid_from": "2025-06-01",
                    "source_doc": "Bankbestaetigung Qonto/C24",
                    "confirmed_by": "Zetha",
                    "history": [],
                },
                "bic": {
                    "value": "COBADEFFXXX",
                    "valid_from": "2025-06-01",
                    "source_doc": "Bankbestaetigung",
                    "confirmed_by": "Zetha",
                    "history": [],
                },
                "tax_id": {
                    "value": f"123456789{num_suffix}",
                    "valid_from": "2020-01-01",
                    "source_doc": "Finanzamt Berlin Mitte",
                    "confirmed_by": "Zetha",
                    "history": [],
                },
                "sv_number": {
                    "value": f"150490L0{num_suffix}8",
                    "valid_from": "2020-01-01",
                    "source_doc": "Sozialversicherungsausweis",
                    "confirmed_by": "Zetha",
                    "history": [],
                },
                "tax_class": {
                    "value": "I" if not has_kids else "II (Mit Kinderfreibetrag)",
                    "valid_from": "2026-01-01",
                    "source_doc": "ELStAM Auszug 2026",
                    "confirmed_by": "Zetha",
                    "history": [],
                },
                "health_insurance": {
                    "value": "Techniker Krankenkasse (TK)",
                    "valid_from": "2025-01-01",
                    "source_doc": "Mitgliedsbescheinigung 2026",
                    "confirmed_by": "Zetha",
                    "history": [],
                },
                "employment_mode": {
                    "value": "Unstaendig beschaeftigt (Schauspiel/Regie)",
                    "valid_from": "2026-01-01",
                    "source_doc": "Stammblatt-Pruefung",
                    "confirmed_by": "Zetha",
                    "history": [],
                },
            },
            "rider_preferences": {
                "diet": "Vegetarisch / Hafermilch am Set",
                "allergies": "Keine bekannt",
                "travel": "BahnCard 50 (1. Klasse bei Nachtreise), Heimschlaefer Berlin",
                "hotel": "Ruhiges Einzelzimmer ab 4 Sterne",
            },
            "has_children": has_kids,
            "status": "active",
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 30 realistische Kalendereintraege (ZTA-Termine #0A1AE4, Castings #0A1AE4 umrandet, Sperrtermine Rot/Orange mit Ort!)
    raw_events = [
        ("ev-01", "cl-01", "zta_termin", "dzr", "zta", "Berlin", "Tatort Berlin: Stille Wasser (DZR)", "rbb / ARD Degeto", "2026-11-04", "2026-11-18", True, 0, "confirmed"),
        ("ev-02", "cl-01", "zta_termin", "dt", "zta", "Berlin", "Drehtag 1-3 Tatort Berlin", "rbb / ARD Degeto", "2026-11-10", "2026-11-12", True, 0, "confirmed"),
        ("ev-03", "cl-01", "sperrtermin", "sperr", "rot", "Stockholm", "Familienhochzeit Stockholm", "", "2026-11-21", "2026-11-23", True, 0, "confirmed"),
        ("ev-04", "cl-01", "zta_termin", "nachsyn", "zta", "Babelsberg", "ADR Studio Babelsberg", "UFA Fiction", "2026-11-26", "2026-11-26", True, 0, "confirmed"),
        ("ev-05", "cl-02", "sperrtermin", "option", "orange", "Koeln", "Theater-Option Schauspiel Koeln", "Wiedemann & Berg", "2026-11-09", "2026-11-15", True, 1, "tentative"),
        ("ev-06", "cl-02", "zta_termin", "dt", "zta", "Berlin", "Drehtag Kinospielfilm 'Glut'", "Komplizen Film", "2026-11-19", "2026-11-22", True, 0, "confirmed"),
        ("ev-07", "cl-02", "sperrtermin", "sperr", "rot", "Berlin", "Facharztermin / Verbindlich gesperrt", "", "2026-11-27", "2026-11-27", True, 0, "confirmed"),
        ("ev-08", "cl-03", "zta_termin", "dzr", "zta", "Muenchen", "Historienserie 'Die Koenigin' Block 2", "Constantin Television", "2026-11-02", "2026-11-14", True, 0, "confirmed"),
        ("ev-09", "cl-03", "zta_termin", "aufnahme", "zta", "Koeln", "Hoerspielaufnahme WDR Studio", "WDR", "2026-11-24", "2026-11-25", True, 0, "confirmed"),
        ("ev-10", "cl-04", "sperrtermin", "option", "orange", "Potsdam", "Option Lesung Potsdam", "Bantry Bay", "2026-11-11", "2026-11-14", True, 1, "tentative"),
        ("ev-11", "cl-04", "sperrtermin", "sperr", "rot", "Hamburg", "Theatergastspiel Kampnagel Hamburg", "Kampnagel Hamburg", "2026-11-20", "2026-11-22", True, 0, "confirmed"),
        ("ev-12", "cl-05", "zta_termin", "dt", "zta", "Berlin", "Netflix-Serie 'Echoes' Drehtage", "Gaumont Germany", "2026-11-08", "2026-11-13", True, 0, "confirmed"),
        ("ev-13", "cl-05", "casting", "casting", "casting", "Berlin", "Live-Casting Kinofilm 'Nordwind'", "Anja Dihrberg Casting", "2026-11-17", "2026-11-17", False, 0, "confirmed"),
        ("ev-14", "cl-06", "sperrtermin", "sperr", "rot", "Wien", "Vorstellungsserie Burgtheater Wien", "Burgtheater", "2026-11-05", "2026-11-10", True, 0, "confirmed"),
        ("ev-15", "cl-06", "sperrtermin", "option", "orange", "Hamburg", "Option ZDF-Mehrteiler 'Der Hafen'", "Network Movie", "2026-11-16", "2026-11-25", True, 1, "tentative"),
        ("ev-16", "cl-07", "zta_termin", "dt", "zta", "Chemnitz", "Erzgebirgskrimi Drehtag", "NFP", "2026-11-12", "2026-11-14", True, 0, "confirmed"),
        ("ev-17", "cl-08", "sperrtermin", "option", "orange", "Turin", "Option Thriller 'Torino'", "Cattleya / Beta", "2026-11-15", "2026-11-24", True, 1, "tentative"),
        ("ev-18", "cl-09", "zta_termin", "aufnahme", "zta", "Berlin", "Deutschlandfunk Kultur Hoerspielaufnahme", "DLF Kultur", "2026-11-09", "2026-11-11", True, 0, "confirmed"),
        ("ev-19", "cl-10", "sperrtermin", "sperr", "rot", "Zuerich", "Verbindlicher Sperrtermin Zuerich", "", "2026-11-25", "2026-11-30", True, 0, "confirmed"),
        ("ev-20", "cl-11", "zta_termin", "dzr", "zta", "Hamburg", "Regie-Vorbereitung Miniserie 'Kaltfront'", "Studio Hamburg", "2026-11-03", "2026-11-28", True, 0, "confirmed"),
        ("ev-21", "cl-12", "sperrtermin", "option", "orange", "Berlin", "Drehbuch-Klausur Staffel 2", "X Filme", "2026-11-16", "2026-11-20", True, 1, "tentative"),
        ("ev-22", "cl-13", "sperrtermin", "sperr", "rot", "London", "Pitching-Tage London", "", "2026-11-18", "2026-11-20", True, 0, "confirmed"),
        ("ev-23", "cl-14", "zta_termin", "dt", "zta", "Berlin", "Schnittabnahme Feinschnitt", "Ziegler Film", "2026-11-10", "2026-11-13", True, 0, "confirmed"),
        ("ev-24", "cl-15", "casting", "casting", "casting", "Berlin", "Live-Casting 'Junges Licht'", "Suse Marquardt Casting", "2026-11-12", "2026-11-12", False, 0, "confirmed"),
        ("ev-25", "cl-16", "sperrtermin", "option", "orange", "Berlin", "ARD Mediathek Serie 'Block 36'", "Sommerhaus", "2026-11-17", "2026-11-26", True, 1, "tentative"),
        ("ev-26", "cl-17", "sperrtermin", "sperr", "rot", "Berlin", "Pruefungswoche Schauspielschule", "", "2026-11-09", "2026-11-13", True, 0, "confirmed"),
        ("ev-27", "cl-18", "zta_termin", "dt", "zta", "Berlin", "Store Opening & Brand Event Kurfuerstendamm", "L'Aurore Paris", "2026-11-11", "2026-11-13", True, 0, "confirmed"),
        ("ev-28", "cl-19", "sperrtermin", "option", "orange", "Frankfurt", "E-Mobility Keynote Option", "Jung von Matt", "2026-11-18", "2026-11-20", True, 1, "tentative"),
        ("ev-29", "cl-20", "zta_termin", "dt", "zta", "Berlin", "Festival / Berlinale Pre-Panel", "Studio Milano", "2026-11-14", "2026-11-16", True, 0, "confirmed"),
        ("ev-30", "cl-01", "sperrtermin", "option", "orange", "Muenchen", "Option Kinofilm 'Winterlicht'", "Walker + Worm", "2026-11-18", "2026-11-19", True, 1, "tentative"),
    ]

    calendar_events = {}
    for ev_id, cid, cat, ev_type, level, loc, title, prod, s_date, e_date, all_day, opt_rank, status in raw_events:
        calendar_events[ev_id] = {
            "client_id": cid,
            "category": cat,
            "event_type": ev_type,
            "level": level,
            "location": loc,
            "title": title,
            "production_company": prod,
            "start_date": s_date,
            "end_date": e_date,
            "would_cancel_shoot_day": level == "rot",
            "all_day": all_day,
            "option_rank": opt_rank,
            "expires_at": "2026-11-16" if ev_type == "option" else "",
            "status": status,
            "tenant_id": tenant,
            "updated_at": now,
        }

    # 8 strukturierte Zeitanfragen & Casting-Pipeline (V10 Modul 2: ohne Synopsis, mit Pipeline-Stufen & Dropbox-Vertrag!)
    raw_inquiries = [
        (
            "inq-01", "cl-01", "2026-11-12", "Nina Haun Casting", "ZDF-Herzkino: Stuerme ueber Ruegen",
            "Relevant Film", "ZDF", "TV-Reihe (90 Min.)", "20:15 Primetime", "Hauptrolle",
            "2026-11-19", "2026-11-25", 4, "Ruegen / Stralsund", 185000, "MW",
            "e_casting", "2026-11-16", "", "", ""
        ),
        (
            "inq-02", "cl-01", "2026-11-03", "Anja Dihrberg Casting", "Tatort Berlin: Stille Wasser",
            "rbb / ARD Degeto", "ARD/Degeto", "TV-Reihe (90 Min.)", "20:15 Primetime", "Episodenhauptrolle",
            "2026-11-04", "2026-11-18", 8, "Berlin", 185000, "MW",
            "live_casting", "2026-10-25", "2026-10-29", "Berlin", "https://www.dropbox.com/scl/fo/zta-clients/Vereinbarungen/Vertrag_Mara_Lindqvist_Tatort_2026.pdf"
        ),
        (
            "inq-03", "cl-01", "2026-10-20", "Suse Marquardt Casting", "Arthouse-Drama 'Herbstnebel'",
            "Komplizen Film", "Kino", "Kinofilm", "Kino", "Nebenrolle",
            "2026-11-01", "2026-11-08", 3, "Leipzig", 170000, "MW",
            "zeitanfrage", "", "", "", ""
        ),
        (
            "inq-04", "cl-02", "2026-11-10", "Emrah Ertem Casting", "Polizeiruf 110: Grenzgang",
            "Filmpool Fiction", "ARD/Degeto", "TV-Reihe (90 Min.)", "20:15 Primetime", "Hauptrolle",
            "2026-11-19", "2026-11-28", 5, "Frankfurt (Oder)", 210000, "MW",
            "live_casting", "2026-11-13", "2026-11-17", "Berlin Studio 3", ""
        ),
        (
            "inq-05", "cl-04", "2026-11-11", "Simone Kroll Casting", "Nord Nord Mord: Kalte Gischt",
            "Network Movie", "ZDF", "TV-Reihe (90 Min.)", "20:15 Primetime", "Episodenhauptrolle",
            "2026-11-18", "2026-11-26", 4, "Sylt / Hamburg", 150000, "MW",
            "e_casting", "2026-11-15", "", "", ""
        ),
        (
            "inq-06", "cl-05", "2026-11-01", "Liza Stutzky Casting", "Netflix-Serie 'Echoes' Staffel 2",
            "Gaumont Germany", "Streamer", "Streaming-Serie", "Streaming / Abruf", "Durchgehende Hauptrolle",
            "2026-11-08", "2026-11-24", 10, "Berlin / Prag", 220000, "MA",
            "live_casting", "2026-10-20", "2026-10-24", "Berlin", "https://www.dropbox.com/scl/fo/zta-clients/Vereinbarungen/Vertrag_Amina_Rahimi_Echoes_S2.pdf"
        ),
        (
            "inq-07", "cl-11", "2026-11-08", "Studio Hamburg Redaktion", "Regie-Anfrage 'Kaltfront' (Miniserie)",
            "Studio Hamburg", "ARD/Degeto", "Mehrteiler / Event", "20:15 Primetime", "Hauptrolle",
            "2026-11-03", "2026-11-28", 25, "Hamburg", 320000, "MW",
            "live_casting", "", "2026-10-28", "Hamburg", "https://www.dropbox.com/scl/fo/zta-clients/Vereinbarungen/Regievertrag_Clara_Vester_Kaltfront.pdf"
        ),
        (
            "inq-08", "cl-15", "2026-11-12", "Boesen & Martell Casting", "Young-Adult-Serie 'Neonstadt'",
            "Bilkis Film", "Streamer", "Streaming-Serie", "Streaming / Abruf", "Hauptrolle",
            "2026-11-22", "2026-11-30", 6, "Berlin", 125000, "MA",
            "e_casting", "2026-11-18", "", "", ""
        ),
    ]

    inquiries = {}
    for (
        iid, cid, rec_date, caster, proj, prod, sender, p_type, slot, r_size,
        dzr_s, dzr_e, s_days, s_loc, fee_c, variant, stage, e_dl, l_date, l_loc, dbx_url
    ) in raw_inquiries:
        base_doc = {
            "client_id": cid,
            "received_date": rec_date,
            "caster_name": caster,
            "contact_person": caster,
            "project_title": proj,
            "production_company": prod,
            "sender_platform": sender,
            "project_type": p_type,
            "time_slot": slot,
            "role_size": r_size,
            "dzr_start": dzr_s,
            "dzr_end": dzr_e,
            "start_date": dzr_s,
            "end_date": dzr_e,
            "shooting_days": s_days,
            "requested_shooting_days": s_days,
            "shooting_location": s_loc,
            "quoted_fee_cents": fee_c,
            "offered_gage_cents": fee_c * s_days,
            "fee_variant": variant,
            "pipeline_stage": stage,
            "e_casting_deadline": e_dl,
            "live_casting_date": l_date,
            "live_casting_location": l_loc,
            "contract_dropbox_url": dbx_url,
            "status": "open",
            "client_response": "pending",
            "tenant_id": tenant,
            "updated_at": now,
        }
        inquiries[iid] = evaluate_inquiry_v10(iid, base_doc, reference_date="2026-11-14")

    # 6 Castings & E-Castings
    raw_castings = [
        ("cast-01", "cl-01", "ZDF-Herzkino: Stuerme ueber Ruegen", "Hauptrolle: Maja Holm", "Nina Haun Casting", "e_casting", "2026-11-16", "open", "fits", "https://dropbox.zta-os.local/tapes/cast-01"),
        ("cast-02", "cl-04", "Nord Nord Mord: Kalte Gischt", "Kommissar Paul", "Simone Kroll Casting", "e_casting", "2026-11-15", "tape_uploaded", "fits", "https://dropbox.zta-os.local/tapes/cast-02"),
        ("cast-03", "cl-02", "Polizeiruf 110: Grenzgang", "Hauptrolle: Kommissar Demir", "Emrah Ertem Casting", "live_casting", "2026-11-17", "open", "pending", ""),
        ("cast-04", "cl-15", "Young-Adult-Serie 'Neonstadt'", "Hauptrolle Cleo", "Boesen & Martell Casting", "e_casting", "2026-11-18", "open", "question", "https://dropbox.zta-os.local/tapes/cast-04"),
        ("cast-05", "cl-17", "EU-Koproduktion 'Baltic Wind'", "Klara", "Boesen & Martell", "e_casting", "2026-11-20", "open", "fits", ""),
        ("cast-06", "cl-05", "Kinofilm 'Nordwind'", "Lead: Daria", "Anja Dihrberg Casting", "live_casting", "2026-11-17", "submitted", "fits", "https://dropbox.zta-os.local/tapes/cast-06"),
    ]

    castings = {}
    for cast_id, cid, proj, role_name, cd, c_type, dl_date, t_status, c_resp, link in raw_castings:
        sched = compute_casting_schedule(dl_date, reference_date="2026-11-14", tape_status=t_status)
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

    # Modul 3: Gagen-Spiegel (fee_matrix) pro Klient:in und Kategorie (Streamer, ARD/Degeto, ZDF, Kino, Kino/Streaming, International)
    raw_fees = [
        ("fee-cl01-zdf", "cl-01", "ZDF", "Tag", "EUR", 175000, 185000, 203500, "MW", "2025+2026", 200000, "fest", "MWF"),
        ("fee-cl01-ard", "cl-01", "ARD/Degeto", "Tag", "EUR", 180000, 185000, 203500, "MW", "2025+2026", 195000, "fest", ""),
        ("fee-cl01-str", "cl-01", "Streamer", "Tag", "EUR", 210000, 220000, 242000, "MA", "2026", 250000, "VB", ""),
        ("fee-cl01-kino", "cl-01", "Kino", "Tag", "EUR", 160000, 170000, 187000, "MW", "2025+2026", 185000, "VB", ""),
        ("fee-cl01-ks", "cl-01", "Kino/Streaming", "Tag", "EUR", 190000, 200000, 220000, "MA", "2026", 220000, "VB", ""),
        ("fee-cl01-int", "cl-01", "International", "Woche", "GBP", 680000, 750000, 825000, "MA", "2026", 850000, "VB", ""),
        ("fee-cl02-ard", "cl-02", "ARD/Degeto", "Tag", "EUR", 200000, 210000, 231000, "MW", "2025+2026", 230000, "fest", ""),
        ("fee-cl02-zdf", "cl-02", "ZDF", "Tag", "EUR", 195000, 210000, 231000, "MW", "2026", 225000, "fest", "MW60"),
        ("fee-cl02-str", "cl-02", "Streamer", "Tag", "EUR", 240000, 250000, 275000, "MA", "2026", 280000, "VB", ""),
        ("fee-cl02-int", "cl-02", "International", "Woche", "EUR", 820000, 880000, 968000, "MA", "2026", 950000, "VB", ""),
        ("fee-cl03-zdf", "cl-03", "ZDF", "Tag", "EUR", 230000, 240000, 264000, "MW", "2025+2026", 260000, "fest", "MWF"),
        ("fee-cl03-str", "cl-03", "Streamer", "Tag", "EUR", 260000, 280000, 308000, "MA", "2026", 300000, "fest", ""),
        ("fee-cl04-zdf", "cl-04", "ZDF", "Tag", "EUR", 140000, 150000, 165000, "MW", "2026", 165000, "VB", "MWFA"),
        ("fee-cl05-str", "cl-05", "Streamer", "Tag", "EUR", 200000, 220000, 242000, "MA", "2026", 250000, "fest", ""),
        ("fee-cl11-ard", "cl-11", "ARD/Degeto", "Tag", "EUR", 300000, 320000, 352000, "MW", "2026", 350000, "fest", ""),
        ("fee-cl15-str", "cl-15", "Streamer", "Tag", "EUR", 115000, 125000, 137500, "MA", "2026", 145000, "TBA", ""),
    ]

    fee_matrix = {}
    for fid, cid, cat, unit, curr, last_c, guide_c, ma_c, var_def, yrs, next_c, st, zdf_m in raw_fees:
        fee_matrix[fid] = {
            "client_id": cid,
            "category": cat,
            "unit": unit,
            "currency": curr,
            "last_achieved_cents": last_c,
            "guideline_cents": guide_c,
            "guideline_ma_cents": ma_c,
            "variant_default": var_def,
            "valid_years": yrs,
            "target_next_year_cents": next_c,
            "fee_status": st,
            "zdf_model": zdf_m,
            "tenant_id": tenant,
            "updated_at": now,
        }

    # Interne Referenz-Deals (Feature 31 - STRIKT NUR TEAM ZTA, unsichtbar fuer Klient:innen!)
    reference_deals = {
        "ref-01": {
            "client_id": "cl-01",
            "project_name": "Nordic Crime Co-Production 'Stockholm Syndrome' (BBC / SVT)",
            "category": "International",
            "amount_cents": 720000,
            "currency": "GBP",
            "exchange_rate_note": "ca. 8.450,00 EUR / Woche",
            "unit": "pro Woche (Episoden-Pauschale)",
            "period": "Herbst 2025",
            "shooting_days": 18,
            "variant": "MA",
            "tenant_id": tenant,
        },
        "ref-02": {
            "client_id": "cl-01",
            "project_name": "Tatort Berlin: Stille Wasser (rbb)",
            "category": "ARD/Degeto",
            "amount_cents": 1480000,
            "currency": "EUR",
            "exchange_rate_note": "8 Drehtage a 1.850,00 EUR",
            "unit": "Zeitraum mit 8 Drehtagen",
            "period": "November 2026",
            "shooting_days": 8,
            "variant": "MW",
            "tenant_id": tenant,
        },
        "ref-03": {
            "client_id": "cl-02",
            "project_name": "Netflix-Eventserie 'Blackout Berlin' (6 Folgen)",
            "category": "Streamer",
            "amount_cents": 3600000,
            "currency": "EUR",
            "exchange_rate_note": "Pauschale fuer 6 Folgen (15 DT)",
            "unit": "Pauschale 6 Folgen",
            "period": "Fruehjahr 2026",
            "shooting_days": 15,
            "variant": "MA",
            "tenant_id": tenant,
        },
    }

    # Modul 4: Unterlagen-Checkliste & Produktions-Tracker (Features 4, 5, 8, 9, 50; loest P8-P12)
    documents = {
        "doc-01": {
            "client_id": "cl-01",
            "doc_type": "Personalausweis / Reisepass",
            "title": "Reisepass Schweden / DE",
            "status": "vorhanden",
            "expires_at": "2029-05-14",
            "dropbox_url": "https://www.dropbox.com/scl/fo/zta-clients/Stammblatt/Mara_Lindqvist_Pass.pdf",
            "shoot_already_running": False,
            "sv_days_in_contract": 8,
            "tenant_id": tenant,
        },
        "doc-02": {
            "client_id": "cl-01",
            "doc_type": "Geburtsurkunde Kind",
            "title": "Geburtsurkunde Kind (Pflichtanlage bei Eltern laut Regel P11)",
            "status": "vorhanden",
            "expires_at": "",
            "dropbox_url": "https://www.dropbox.com/scl/fo/zta-clients/Stammblatt/Mara_Lindqvist_Geburtsurkunde_Kind.pdf",
            "shoot_already_running": False,
            "sv_days_in_contract": 8,
            "tenant_id": tenant,
        },
        "doc-03": {
            "client_id": "cl-01",
            "doc_type": "Personalstammblatt Produktion",
            "title": "Personalstammblatt 'Tatort Berlin: Stille Wasser' (rbb)",
            "status": "unterschrieben",
            "expires_at": "2026-11-04",
            "dropbox_url": "https://www.dropbox.com/scl/fo/zta-clients/Stammblatt/Stammblatt_Tatort_Signed.pdf",
            "shoot_already_running": True,
            "sv_days_in_contract": 8,
            "tenant_id": tenant,
        },
        "doc-04": {
            "client_id": "cl-02",
            "doc_type": "PKV-/KV-Bescheinigung",
            "title": "PKV-Beitragsbescheinigung (Stand Vorjahr - abgelaufen, siehe P10!)",
            "status": "abgelaufen",
            "expires_at": "2025-12-31",
            "dropbox_url": "https://www.dropbox.com/scl/fo/zta-clients/Stammblatt/Tarik_PKV_2025.pdf",
            "shoot_already_running": False,
            "sv_days_in_contract": 7,
            "tenant_id": tenant,
        },
        "doc-05": {
            "client_id": "cl-03",
            "doc_type": "Geburtsurkunde Kind",
            "title": "Geburtsurkunde Kind (FEHLT - bei Eltern immer mitreichen, siehe P11!)",
            "status": "fehlt",
            "expires_at": "2026-11-15",
            "dropbox_url": "",
            "shoot_already_running": True,
            "sv_days_in_contract": 5,
            "tenant_id": tenant,
        },
        "doc-06": {
            "client_id": "cl-15",
            "doc_type": "Immatrikulationsbescheinigung",
            "title": "Immatrikulationsbescheinigung UdK Berlin (Wintersemester)",
            "status": "vorhanden",
            "expires_at": "2027-03-31",
            "dropbox_url": "https://www.dropbox.com/scl/fo/zta-clients/Stammblatt/Lilli_Immatrikulation.pdf",
            "shoot_already_running": False,
            "sv_days_in_contract": 7,
            "tenant_id": tenant,
        },
    }

    # Benachrichtigungen fuer Klient:innen (Feature 27)
    notifications = {
        "ntf-01": {
            "client_id": "cl-01",
            "category": "zeitanfrage",
            "title": "Neue Zeitanfrage: ZDF-Herzkino (Stuerme ueber Ruegen)",
            "message": "Nina Haun Casting hat deinen Zeitraum 19.11. bis 25.11.2026 (4 Drehtage) angefragt.",
            "read": False,
            "created_at": now,
            "tenant_id": tenant,
        },
        "ntf-02": {
            "client_id": "cl-01",
            "category": "casting",
            "title": "E-Casting-Frist eingetragen: 16.11.2026",
            "message": "Deine E-Casting-Frist fuer 'Stuerme ueber Ruegen' wurde in deinen Monatskalender synchronisiert.",
            "read": False,
            "created_at": now,
            "tenant_id": tenant,
        },
    }

    # 10 Vertraege (Kompatibilitaet fuer bestehende Finanz- & Auto-Offset-Tests)
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

    raw_time_logs = [
        ("tl-01", "cl-01", "Vertragsverhandlung & Dispo Tatort Berlin", "dispo", 180, "2026-11-02"),
        ("tl-02", "cl-01", "E-Casting Sichtung & Feedback 'Stuerme ueber Ruegen'", "casting", 75, "2026-11-08"),
        ("tl-03", "cl-02", "Drehplan-Abgleich 'Glut' & Optionen", "dispo", 150, "2026-11-04"),
        ("tl-04", "cl-03", "Reise- & Vertragsabrechnung Block 2", "vertrag", 210, "2026-10-28"),
        ("tl-05", "cl-04", "Terminkoordination SOKO + Kampnagel", "dispo", 120, "2026-11-06"),
        ("tl-06", "cl-05", "Buyout-Verhandlung Netflix 'Echoes'", "vertrag", 160, "2026-11-05"),
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

    feedback_items = {
        "FB-001": {
            "title": "Sperrtermin-Rechner mit ZTA Light Pink (#F2D2C7) Hervorhebung im Monatsraster",
            "description": "Im Monatskalender soll der angefragte DZR direkt in #F2D2C7 hinterlegt werden.",
            "category": "wunsch",
            "status": "erledigt",
            "reported_by_role": "inhaberin",
            "reported_by_name": "Zetha",
            "view_context": "kalender",
            "element_selector": "#sperrtermin-rechner",
            "device_hint": "Desktop / iPhone",
            "app_version": "10.0.0",
            "created_at": now,
            "updated_at": now,
            "tenant_id": tenant,
        }
    }

    settings = {
        "agency_profile": {
            "agency_name": "ZTA Management Berlin",
            "spec_version": "V10 (2026-11-13)",
            "default_tenant_id": tenant,
            "primary_color": "#0A1AE4",
            "accent_pink": "#F2D2C7",
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
        "fee_matrix": fee_matrix,
        "reference_deals": reference_deals,
        "documents": documents,
        "notifications": notifications,
        "time_logs": time_logs,
        "feedback_items": feedback_items,
        "hub_questions": {},
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
        f"[ZTA OS V10 Seeding] {len(dataset['clients'])} Klient:innen in 5 Departments, "
        f"{len(dataset['calendar_events'])} Termine, {len(dataset['inquiries'])} Zeitanfragen, "
        f"{len(dataset['fee_matrix'])} Gagen-Spiegel-Eintraege und {len(dataset['documents'])} Dokumente "
        f"in '{cfg.data_path}' gespeichert (Revision {state['meta']['revision']})."
    )


if __name__ == "__main__":
    main()
