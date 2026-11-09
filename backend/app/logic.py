"""Reine, deterministische Domain-Logik fuer ZTA OS (Zero-Error Cent-Mathematik, Kalender, Auto-Offset)."""
from __future__ import annotations

import calendar
import csv
import io
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from .models import utc_now_iso

HARD_BLOCK_TYPES = {"sperr", "dt", "nachsyn", "aufnahme"}
PARTIAL_TYPES = {"dzr", "casting"}
OPTION_TYPES = {"option"}

EVENT_TYPE_LABELS = {
    "sperr": "Sperrtermin",
    "option": "Option",
    "dzr": "Drehzeitraum (DZR)",
    "dt": "Drehtag (DT)",
    "nachsyn": "Nachsynchron",
    "aufnahme": "Sprach-/Tonaufnahme",
    "casting": "Casting / E-Casting",
}

DIVISION_LABELS = {
    "schauspiel": "Schauspiel",
    "regie_drehbuch": "Regie & Drehbuch",
    "nxt": "NXT (Nachwuchs)",
    "pr_commercial": "PR & Commercial",
}


def round_cents_decimal(val: Decimal) -> int:
    """Rundet einen Decimal-Cent-Wert kaufmaennisch exakt auf ganze Cent (int)."""
    return int(val.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_eur_from_cents(cents: int) -> str:
    """Formatiert ganze Cent (int) deterministisch als deutschen Euro-Betrag (z. B. 1.250,50 EUR)."""
    sign = "-" if cents < 0 else ""
    abs_cents = abs(int(cents))
    euros = abs_cents // 100
    rem_cents = abs_cents % 100
    euro_str = f"{euros:,}".replace(",", ".")
    return f"{sign}{euro_str},{rem_cents:02d} EUR"


def parse_eur_to_cents(raw_val: Any) -> int:
    """Parst einen Euro-Betrag (String, int, Decimal) fehlertolerant und ohne Float-Ungenauigkeit in Cent."""
    if raw_val is None or raw_val == "":
        return 0
    if isinstance(raw_val, int):
        return raw_val
    s = str(raw_val).strip()
    s = re.sub(r"[EUR€\s]", "", s, flags=re.IGNORECASE)
    if not s:
        return 0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    dec = Decimal(s)
    return round_cents_decimal(dec * Decimal("100"))


def parse_iso_date(d_str: str) -> date:
    """Parst YYYY-MM-DD in ein date-Objekt."""
    clean = str(d_str).strip()[:10]
    return date.fromisoformat(clean)


def ranges_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """Prueft, ob zwei inklusive Datumsbereiche [start_a, end_a] und [start_b, end_b] ueberlappen."""
    da1, da2 = parse_iso_date(start_a), parse_iso_date(end_a)
    db1, db2 = parse_iso_date(start_b), parse_iso_date(end_b)
    if da1 > da2:
        da1, da2 = da2, da1
    if db1 > db2:
        db1, db2 = db2, db1
    return da1 <= db2 and db1 <= da2


def iter_dates_inclusive(start_str: str, end_str: str) -> List[str]:
    d1, d2 = parse_iso_date(start_str), parse_iso_date(end_str)
    if d1 > d2:
        d1, d2 = d2, d1
    days: List[str] = []
    cur = d1
    while cur <= d2:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def classify_event_severity(ev: Dict[str, Any]) -> str:
    """Klassifiziert einen Kalendereintrag in 'belegt', 'teilweise' oder 'option'."""
    ev_type = str(ev.get("event_type") or ev.get("type") or "sperr").lower()
    all_day = bool(ev.get("all_day", True))
    if ev_type in OPTION_TYPES:
        return "option"
    if ev_type in PARTIAL_TYPES:
        return "teilweise"
    if ev_type in HARD_BLOCK_TYPES:
        return "belegt" if all_day else "teilweise"
    return "belegt"


def check_client_availability(
    client_id: str,
    start_date: str,
    end_date: str,
    calendar_events: Dict[str, Dict[str, Any]],
    ignore_event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Prueft die Verfuegbarkeit einer Klient:in im Zeitraum [start_date, end_date]."""
    overlapping: List[Dict[str, Any]] = []
    hard_conflicts: List[Dict[str, Any]] = []
    options: List[Dict[str, Any]] = []
    partial_items: List[Dict[str, Any]] = []

    for ev_id, ev in calendar_events.items():
        if ignore_event_id and ev_id == ignore_event_id:
            continue
        if ev.get("client_id") != client_id:
            continue
        if ev.get("status") == "cancelled":
            continue
        ev_start = str(ev.get("start_date") or "")
        ev_end = str(ev.get("end_date") or ev_start)
        if not ev_start:
            continue
        if ranges_overlap(start_date, end_date, ev_start, ev_end):
            item = dict(ev)
            item["id"] = ev_id
            sev = classify_event_severity(item)
            item["severity"] = sev
            overlapping.append(item)
            if sev == "belegt":
                hard_conflicts.append(item)
            elif sev == "option":
                options.append(item)
            else:
                partial_items.append(item)

    overlapping.sort(key=lambda x: (str(x.get("start_date", "")), str(x.get("title", ""))))

    # Tagesgenaue Aufschluesselung im angefragten Zeitraum
    days = iter_dates_inclusive(start_date, end_date)
    day_status_map: Dict[str, str] = {}
    free_days: List[str] = []
    blocked_days: List[str] = []

    rank_order = {"frei": 0, "option": 1, "teilweise": 2, "belegt": 3}

    for d_iso in days:
        cur_status = "frei"
        for item in overlapping:
            if ranges_overlap(d_iso, d_iso, item["start_date"], item.get("end_date") or item["start_date"]):
                sev = item["severity"]
                if rank_order[sev] > rank_order[cur_status]:
                    cur_status = sev
        day_status_map[d_iso] = cur_status
        if cur_status == "belegt":
            blocked_days.append(d_iso)
        else:
            free_days.append(d_iso)

    if hard_conflicts:
        overall = "belegt" if len(blocked_days) == len(days) else "teilweise"
    elif partial_items:
        overall = "teilweise"
    elif options:
        overall = "option"
    else:
        overall = "frei"

    next_option_rank = 1
    if options:
        existing_ranks = [int(o.get("option_rank") or 1) for o in options]
        next_option_rank = max(existing_ranks) + 1

    return {
        "client_id": client_id,
        "start_date": start_date,
        "end_date": end_date,
        "overall_status": overall,
        "total_days": len(days),
        "free_days_count": len(free_days),
        "blocked_days_count": len(blocked_days),
        "free_days": free_days,
        "blocked_days": blocked_days,
        "day_status_map": day_status_map,
        "overlapping_events": overlapping,
        "hard_conflicts": hard_conflicts,
        "options": options,
        "partial_items": partial_items,
        "recommended_option_rank": next_option_rank,
    }


def find_free_clients(
    clients: Dict[str, Dict[str, Any]],
    calendar_events: Dict[str, Dict[str, Any]],
    start_date: str,
    end_date: str,
    division: Optional[str] = None,
    include_options: bool = True,
) -> List[Dict[str, Any]]:
    """Filtert alle Klient:innen nach Verfuegbarkeit im Zeitraum ('Wer ist frei?')."""
    results: List[Dict[str, Any]] = []
    for cid, cdoc in clients.items():
        if cdoc.get("status") == "archived":
            continue
        if division and division != "all" and cdoc.get("division") != division:
            continue
        avail = check_client_availability(cid, start_date, end_date, calendar_events)
        allowed_statuses = {"frei", "teilweise"}
        if include_options:
            allowed_statuses.add("option")
        results.append(
            {
                "client_id": cid,
                "name": cdoc.get("name", cid),
                "division": cdoc.get("division", "schauspiel"),
                "location": cdoc.get("location", "Berlin"),
                "overall_status": avail["overall_status"],
                "is_available": avail["overall_status"] in allowed_statuses,
                "free_days_count": avail["free_days_count"],
                "blocked_days_count": avail["blocked_days_count"],
                "recommended_option_rank": avail["recommended_option_rank"],
                "conflicts_summary": [
                    f"{EVENT_TYPE_LABELS.get(e.get('event_type', 'sperr'), 'Termin')}: {e.get('title', '')} ({e.get('start_date')} bis {e.get('end_date')})"
                    for e in avail["overlapping_events"]
                ],
            }
        )
    order_priority = {"frei": 0, "option": 1, "teilweise": 2, "belegt": 3}
    results.sort(key=lambda r: (order_priority.get(r["overall_status"], 9), r["name"]))
    return results


def build_month_grid(
    clients: Dict[str, Dict[str, Any]],
    calendar_events: Dict[str, Dict[str, Any]],
    year: int,
    month: int,
    division: Optional[str] = None,
) -> Dict[str, Any]:
    """Erstellt die Monats-Verfuegbarkeits-Matrix fuer alle aktiven Klient:innen."""
    _, num_days = calendar.monthrange(year, month)
    start_str = f"{year:04d}-{month:02d}-01"
    end_str = f"{year:04d}-{month:02d}-{num_days:02d}"
    days_list = [f"{year:04d}-{month:02d}-{d:02d}" for d in range(1, num_days + 1)]

    rows: List[Dict[str, Any]] = []
    for cid, cdoc in sorted(clients.items(), key=lambda item: str(item[1].get("name", ""))):
        if cdoc.get("status") == "archived":
            continue
        if division and division != "all" and cdoc.get("division") != division:
            continue
        avail = check_client_availability(cid, start_str, end_str, calendar_events)
        rows.append(
            {
                "client_id": cid,
                "name": cdoc.get("name", cid),
                "division": cdoc.get("division", "schauspiel"),
                "days": avail["day_status_map"],
                "events_count": len(avail["overlapping_events"]),
            }
        )

    return {
        "year": year,
        "month": month,
        "start_date": start_str,
        "end_date": end_str,
        "days": days_list,
        "rows": rows,
    }


def generate_inquiry_reply(
    client: Dict[str, Any],
    inquiry: Dict[str, Any],
    availability: Dict[str, Any],
) -> str:
    """Erzeugt eine kopierfertige, professionelle Agentur-Antwortvorlage ohne Gedankenstriche."""
    client_name = client.get("name", "Klient:in")
    project_title = inquiry.get("project_title", "das angefragte Projekt")
    production = inquiry.get("production_company", "")
    contact = inquiry.get("contact_person", "Liebes Team")
    start_d = inquiry.get("start_date", "")
    end_d = inquiry.get("end_date", start_d)
    requested_days = inquiry.get("requested_shooting_days", 1)
    gage_cents = int(inquiry.get("offered_gage_cents") or client.get("default_daily_fee_cents") or 0)

    greeting = f"Hallo {contact}," if contact and not contact.lower().startswith("hallo") else "Guten Tag,"
    prod_hint = f" ({production})" if production else ""

    status = availability["overall_status"]
    hard = availability["hard_conflicts"]
    opts = availability["options"]
    partials = availability["partial_items"]
    next_rank = availability["recommended_option_rank"]

    lines = [
        greeting,
        "",
        f"vielen Dank fuer die Zeitanfrage fuer {client_name} zum Projekt \"{project_title}\"{prod_hint} im Zeitraum {start_d} bis {end_d} ({requested_days} Drehtag(e)).",
        "",
    ]

    if status == "frei":
        lines.append(
            f"Verfuegbarkeit: {client_name} ist im angefragten Zeitraum komplett frei. Wir koennen gerne eine 1. Option eintragen."
        )
    elif status == "option":
        opt_desc = ", ".join(
            f"{o.get('title', 'Projekt')} ({o.get('start_date')} bis {o.get('end_date')}, {o.get('option_rank', 1)}. Option)"
            for o in opts
        )
        lines.append(
            f"Verfuegbarkeit: Im Zeitraum liegt bereits folgende Option vor: {opt_desc}. Wir koennen fuer \"{project_title}\" gerne eine {next_rank}. Option vermerken."
        )
    elif status == "teilweise":
        block_desc = ", ".join(
            f"{EVENT_TYPE_LABELS.get(e.get('event_type', 'sperr'), 'Termin')} am {e.get('start_date')} bis {e.get('end_date')}"
            for e in (hard + partials)
        )
        lines.append(
            f"Verfuegbarkeit: {client_name} ist im Zeitraum eingeschraenkt verfuegbar ({availability['free_days_count']} von {availability['total_days']} Tagen frei). Bereits belegt bzw. disponiert: {block_desc}."
        )
        if opts:
            opt_desc = ", ".join(f"{o.get('title')} ({o.get('start_date')} bis {o.get('end_date')})" for o in opts)
            lines.append(f"Zusaetzlich bestehende Optionen: {opt_desc}.")
        lines.append(
            f"An den uebrigen Tagen ({len(availability['free_days'])} Tage) koennen wir gerne eine {next_rank}. Option setzen."
        )
    else:
        block_desc = ", ".join(
            f"{EVENT_TYPE_LABELS.get(e.get('event_type', 'sperr'), 'Termin')} ({e.get('start_date')} bis {e.get('end_date')})"
            for e in hard
        )
        lines.append(
            f"Verfuegbarkeit: Leider ist {client_name} im angefragten Zeitraum durchgaengig belegt ({block_desc}). Sollte sich die Disposition verschieben, gebt uns gerne kurz Bescheid."
        )

    if gage_cents > 0:
        lines.append("")
        lines.append(
            f"Konditionen / Gagen-Richtwert: {format_eur_from_cents(gage_cents)} zzgl. Agenturprovision ({int(client.get('commission_rate_bp', 1000)) / 100:.0f} %) und gesetzlicher USt."
        )

    lines.extend(
        [
            "",
            "Herzliche Gruesse",
            "ZTA Management Berlin",
        ]
    )
    return "\n".join(lines)


def compute_casting_schedule(
    deadline_date: str,
    reference_date: Optional[str] = None,
    tape_status: str = "open",
) -> Dict[str, Any]:
    """Berechnet den internen ZTA-Sichtungstermin (2 Tage vor Deadline) und die Dringlichkeitsstufe."""
    dl = parse_iso_date(deadline_date)
    internal_review = dl - timedelta(days=2)
    ref = parse_iso_date(reference_date) if reference_date else date.today()
    days_until_deadline = (dl - ref).days
    days_until_review = (internal_review - ref).days

    if tape_status in ("submitted", "completed", "feedback_received"):
        urgency = "done"
        label = "Abgeschlossen / Eingereicht"
    elif days_until_deadline < 0:
        urgency = "overdue"
        label = f"Frist abgelaufen ({abs(days_until_deadline)} Tag(e) ueberfaellig)"
    elif days_until_review <= 0:
        urgency = "critical"
        label = f"Sichtung faellig! Deadline in {days_until_deadline} Tag(en)"
    elif days_until_review <= 2:
        urgency = "soon"
        label = f"Sichtung in {days_until_review} Tag(en) (Deadline {dl.isoformat()})"
    else:
        urgency = "ok"
        label = f"Planmaessig ({days_until_deadline} Tage bis Deadline)"

    return {
        "deadline_date": dl.isoformat(),
        "internal_review_date": internal_review.isoformat(),
        "days_until_deadline": days_until_deadline,
        "days_until_review": days_until_review,
        "urgency": urgency,
        "countdown_label": label,
    }


def calculate_contract_financials(
    division: str,
    gage_cents: int,
    buyout_cents: int = 0,
    commission_rate_bp: int = 1000,
    engagement_days: int = 1,
    vat_rate_bp: int = 1900,
) -> Dict[str, Any]:
    """
    Berechnet alle Vertrags-, Provisions- und Auszahlungswerte exakt in Cent (Prinzip 3.1 Zero-Error-Policy).
    Prueft zudem die gesetzliche Obergrenze nach Vermittler-Verguetungsverordnung (14 % bis 7 Tage, 18 % ab 8 Tage).
    """
    if gage_cents < 0 or buyout_cents < 0:
        raise ValueError("Gage und Buyout duerfen nicht negativ sein.")
    if commission_rate_bp < 0 or commission_rate_bp > 5000:
        raise ValueError("Provisionssatz muss zwischen 0 und 5000 Basispunkten (0 % bis 50 %) liegen.")

    gross_dec = Decimal(int(gage_cents) + int(buyout_cents))
    rate_dec = Decimal(int(commission_rate_bp)) / Decimal("10000")
    vat_dec = Decimal(int(vat_rate_bp)) / Decimal("10000")

    commission_cents = round_cents_decimal(gross_dec * rate_dec)
    agency_vat_cents = round_cents_decimal(Decimal(commission_cents) * vat_dec)
    agency_gross_invoice_cents = commission_cents + agency_vat_cents
    total_gross_cents = int(gage_cents) + int(buyout_cents)
    client_payout_cents = total_gross_cents - commission_cents

    # Gesetzliche Pruefung nach Vermittler-Verguetungsverordnung (Schauspiel/Regie/NXT)
    if division == "pr_commercial":
        legal_cap_bp = 3000  # Commercial / Werbe-Buyout unterliegt freier Vereinbarung (ueblich 20 % bis 25 %)
    else:
        legal_cap_bp = 1400 if int(engagement_days) <= 7 else 1800

    exceeds_legal_cap = int(commission_rate_bp) > legal_cap_bp
    legal_warning = ""
    if exceeds_legal_cap:
        legal_warning = (
            f"Hinweis Vermittler-Verguetungsverordnung: Der gewaehlte Satz ({commission_rate_bp / 100:.2f} %) "
            f"uebersteigt den gesetzlichen Richtwert von {legal_cap_bp / 100:.0f} % "
            f"fuer Engagements mit {engagement_days} Tag(en) in der Sparte {DIVISION_LABELS.get(division, division)}."
        )

    return {
        "division": division,
        "gage_cents": int(gage_cents),
        "buyout_cents": int(buyout_cents),
        "total_gross_cents": total_gross_cents,
        "commission_rate_bp": int(commission_rate_bp),
        "commission_rate_percent": float(Decimal(int(commission_rate_bp)) / Decimal("100")),
        "commission_cents": commission_cents,
        "agency_vat_cents": agency_vat_cents,
        "agency_gross_invoice_cents": agency_gross_invoice_cents,
        "client_payout_cents": client_payout_cents,
        "engagement_days": int(engagement_days),
        "legal_cap_bp": legal_cap_bp,
        "exceeds_legal_cap": exceeds_legal_cap,
        "legal_warning": legal_warning,
        "payout_schedule_rule": "end_of_month",
        "payout_schedule_note": "Auszahlung an Klient:in erfolgt gesammelt zum Monatsende nach Zahlungseingang.",
        "formatted": {
            "total_gross": format_eur_from_cents(total_gross_cents),
            "commission": format_eur_from_cents(commission_cents),
            "client_payout": format_eur_from_cents(client_payout_cents),
        },
    }


def build_liquidity_timeline(
    contracts: Dict[str, Dict[str, Any]],
    clients: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Erstellt die monatliche Liquiditaets- und Provisionsvorschau aus finalisierten Vertraegen."""
    months_map: Dict[str, Dict[str, Any]] = {}
    total_confirmed_commission_cents = 0
    total_paid_commission_cents = 0
    total_open_receivables_cents = 0
    total_pending_client_payout_cents = 0

    for cid, cdoc in contracts.items():
        status = cdoc.get("status", "draft")
        if status in ("draft", "cancelled"):
            continue
        month_key = str(cdoc.get("payout_month") or cdoc.get("expected_payment_month") or "2026-11")[:7]
        bucket = months_map.setdefault(
            month_key,
            {
                "month": month_key,
                "gross_volume_cents": 0,
                "confirmed_commission_cents": 0,
                "paid_commission_cents": 0,
                "open_commission_cents": 0,
                "client_payout_end_of_month_cents": 0,
                "contracts_count": 0,
                "items": [],
            },
        )

        gross = int(cdoc.get("total_gross_cents") or cdoc.get("gage_cents") or 0)
        comm = int(cdoc.get("commission_cents") or 0)
        payout = int(cdoc.get("client_payout_cents") or (gross - comm))
        client_name = clients.get(cdoc.get("client_id", ""), {}).get("name", cdoc.get("client_id", "Unbekannt"))

        bucket["gross_volume_cents"] += gross
        bucket["contracts_count"] += 1

        if status in ("final_signed", "invoiced", "paid"):
            bucket["confirmed_commission_cents"] += comm
            bucket["client_payout_end_of_month_cents"] += payout
            total_confirmed_commission_cents += comm

        if status == "paid":
            bucket["paid_commission_cents"] += comm
            total_paid_commission_cents += comm
        elif status in ("final_signed", "invoiced"):
            bucket["open_commission_cents"] += comm
            total_open_receivables_cents += comm
            total_pending_client_payout_cents += payout

        bucket["items"].append(
            {
                "contract_id": cid,
                "project_title": cdoc.get("project_title", ""),
                "client_name": client_name,
                "status": status,
                "total_gross_cents": gross,
                "commission_cents": comm,
                "client_payout_cents": payout,
            }
        )

    timeline = [months_map[k] for k in sorted(months_map.keys())]
    return {
        "total_confirmed_commission_cents": total_confirmed_commission_cents,
        "total_paid_commission_cents": total_paid_commission_cents,
        "total_open_receivables_cents": total_open_receivables_cents,
        "total_pending_client_payout_cents": total_pending_client_payout_cents,
        "timeline": timeline,
    }


def build_effort_vs_commission_report(
    clients: Dict[str, Dict[str, Any]],
    contracts: Dict[str, Dict[str, Any]],
    time_logs: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Berechnet Aufwand (Minuten/Stunden) gegenueber erwirtschafteter Provision (Cent) pro Klient:in."""
    report: List[Dict[str, Any]] = []
    for client_id, cdoc in clients.items():
        if cdoc.get("status") == "archived":
            continue
        minutes = sum(
            int(t.get("duration_minutes") or 0)
            for t in time_logs.values()
            if t.get("client_id") == client_id
        )
        comm_cents = sum(
            int(c.get("commission_cents") or 0)
            for c in contracts.values()
            if c.get("client_id") == client_id and c.get("status") in ("final_signed", "invoiced", "paid")
        )
        hours_dec = Decimal(minutes) / Decimal("60") if minutes > 0 else Decimal("0")
        cents_per_hour = (
            round_cents_decimal(Decimal(comm_cents) / hours_dec) if hours_dec > Decimal("0") else 0
        )
        report.append(
            {
                "client_id": client_id,
                "name": cdoc.get("name", client_id),
                "division": cdoc.get("division", "schauspiel"),
                "logged_minutes": minutes,
                "logged_hours": float(hours_dec.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
                "commission_cents": comm_cents,
                "commission_cents_per_hour": cents_per_hour,
                "formatted_commission": format_eur_from_cents(comm_cents),
                "formatted_hourly_yield": format_eur_from_cents(cents_per_hour) + "/Std.",
            }
        )
    report.sort(key=lambda r: (-r["commission_cents"], -r["logged_minutes"], r["name"]))
    return report


def apply_inquiry_decision(
    collections: Dict[str, Dict[str, Dict[str, Any]]],
    inquiry_id: str,
    decision: str,
    option_rank: int = 1,
    option_expires_at: Optional[str] = None,
    create_contract_draft: bool = True,
) -> Dict[str, Any]:
    """
    Auto-Offset / Subsystem-Verknuepfung (Prinzip 4.2):
    Uebernimmt eine Zeitanfrage als Option, Festbuchung (DZR) oder Absage und aktualisiert
    automatisch Kalender sowie optional den Vertragsentwurf.
    """
    inquiries = collections.setdefault("inquiries", {})
    if inquiry_id not in inquiries:
        raise ValueError(f"Zeitanfrage '{inquiry_id}' nicht gefunden.")

    inq = dict(inquiries[inquiry_id])
    client_id = inq.get("client_id", "")
    clients = collections.get("clients", {})
    client = clients.get(client_id, {})
    tenant_id = inq.get("tenant_id", "zta-berlin")

    created_event_id: Optional[str] = None
    created_contract_id: Optional[str] = None

    if decision == "decline":
        inq["status"] = "declined"
        inq["updated_at"] = utc_now_iso()
        inquiries[inquiry_id] = inq
    elif decision in ("option", "confirm"):
        ev_type = "option" if decision == "option" else "dzr"
        inq["status"] = "optioned" if decision == "option" else "confirmed"
        inq["updated_at"] = utc_now_iso()

        created_event_id = inq.get("linked_event_id") or f"ev-{uuid.uuid4().hex[:8]}"
        collections.setdefault("calendar_events", {})[created_event_id] = {
            "client_id": client_id,
            "event_type": ev_type,
            "title": inq.get("project_title", "Projektbuchung"),
            "production_company": inq.get("production_company", ""),
            "start_date": inq.get("start_date"),
            "end_date": inq.get("end_date") or inq.get("start_date"),
            "all_day": True,
            "option_rank": int(option_rank) if decision == "option" else 0,
            "expires_at": option_expires_at or "",
            "status": "tentative" if decision == "option" else "confirmed",
            "source_inquiry_id": inquiry_id,
            "tenant_id": tenant_id,
            "updated_at": utc_now_iso(),
        }
        inq["linked_event_id"] = created_event_id

        if create_contract_draft:
            created_contract_id = inq.get("linked_contract_id") or f"con-{uuid.uuid4().hex[:8]}"
            division = client.get("division", "schauspiel")
            rate_bp = int(client.get("commission_rate_bp", 1000))
            gage_cents = int(inq.get("offered_gage_cents") or client.get("default_daily_fee_cents") or 120000)
            days = int(inq.get("requested_shooting_days") or 1)
            calc = calculate_contract_financials(
                division=division,
                gage_cents=gage_cents,
                buyout_cents=0,
                commission_rate_bp=rate_bp,
                engagement_days=days,
            )
            payout_month = str(inq.get("end_date") or inq.get("start_date") or "2026-11")[:7]
            collections.setdefault("contracts", {})[created_contract_id] = {
                "client_id": client_id,
                "project_title": inq.get("project_title", "Projekt"),
                "production_company": inq.get("production_company", ""),
                "division": division,
                "status": "draft" if decision == "option" else "negotiation",
                "engagement_days": days,
                "gage_cents": calc["gage_cents"],
                "buyout_cents": calc["buyout_cents"],
                "total_gross_cents": calc["total_gross_cents"],
                "commission_rate_bp": calc["commission_rate_bp"],
                "commission_cents": calc["commission_cents"],
                "agency_vat_cents": calc["agency_vat_cents"],
                "client_payout_cents": calc["client_payout_cents"],
                "outstanding_cents": calc["commission_cents"],
                "paid_amount_cents": 0,
                "payout_month": payout_month,
                "client_payout_status": "geplant_zum_monatsende",
                "source_inquiry_id": inquiry_id,
                "tenant_id": tenant_id,
                "updated_at": utc_now_iso(),
            }
            inq["linked_contract_id"] = created_contract_id

        inquiries[inquiry_id] = inq
    else:
        raise ValueError(f"Unbekannte Entscheidung: {decision}")

    return {
        "inquiry_id": inquiry_id,
        "new_status": inq["status"],
        "created_event_id": created_event_id,
        "created_contract_id": created_contract_id,
    }


def apply_contract_status_with_auto_offset(
    collections: Dict[str, Dict[str, Dict[str, Any]]],
    contract_id: str,
    new_status: str,
    paid_amount_cents: Optional[int] = None,
    paid_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Auto-Offset fuer Vertraege & Zahlungseingaenge (Prinzip 4.2):
    Aktualisiert den Vertragsstatus, berechnet Cent-Betraege deterministisch nach und
    gleicht bei Zahlungseingang ('paid') offene Forderungen automatisch aus.
    """
    contracts = collections.setdefault("contracts", {})
    if contract_id not in contracts:
        raise ValueError(f"Vertrag '{contract_id}' nicht gefunden.")

    con = dict(contracts[contract_id])
    calc = calculate_contract_financials(
        division=con.get("division", "schauspiel"),
        gage_cents=int(con.get("gage_cents") or 0),
        buyout_cents=int(con.get("buyout_cents") or 0),
        commission_rate_bp=int(con.get("commission_rate_bp") or 1000),
        engagement_days=int(con.get("engagement_days") or 1),
    )
    con.update(
        {
            "total_gross_cents": calc["total_gross_cents"],
            "commission_cents": calc["commission_cents"],
            "agency_vat_cents": calc["agency_vat_cents"],
            "client_payout_cents": calc["client_payout_cents"],
            "status": new_status,
            "updated_at": utc_now_iso(),
        }
    )

    if new_status == "paid":
        settled = int(paid_amount_cents) if paid_amount_cents is not None else calc["commission_cents"]
        con["paid_amount_cents"] = settled
        con["outstanding_cents"] = max(0, calc["commission_cents"] - settled)
        con["paid_at"] = paid_at or utc_now_iso()
        con["client_payout_status"] = "freigegeben_zum_monatsende"
    elif new_status in ("final_signed", "invoiced"):
        already_paid = int(con.get("paid_amount_cents") or 0)
        con["outstanding_cents"] = max(0, calc["commission_cents"] - already_paid)
        con["client_payout_status"] = "in_abrechnung_monatsende"
    elif new_status == "cancelled":
        con["outstanding_cents"] = 0
        con["client_payout_status"] = "storniert"

    contracts[contract_id] = con
    return {
        "contract_id": contract_id,
        "status": con["status"],
        "commission_cents": con["commission_cents"],
        "outstanding_cents": con.get("outstanding_cents", 0),
        "client_payout_cents": con["client_payout_cents"],
        "client_payout_status": con.get("client_payout_status", ""),
    }


def generate_client_ical(
    client_id: str,
    client: Dict[str, Any],
    calendar_events: Dict[str, Dict[str, Any]],
) -> str:
    """Erzeugt einen RFC-5545-konformen iCal-Feed (.ics) fuer eine Klient:in."""
    client_name = client.get("name", client_id)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ZTA Management Berlin//ZTA OS v1.0//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:ZTA Management ({client_name})",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for ev_id, ev in sorted(calendar_events.items()):
        if ev.get("client_id") != client_id or ev.get("status") == "cancelled":
            continue
        start_str = str(ev.get("start_date") or "")
        end_str = str(ev.get("end_date") or start_str)
        if not start_str:
            continue
        d_start = parse_iso_date(start_str)
        # Bei Ganztagsterminen ist DTEND in iCal exklusiv (+1 Tag)
        d_end_excl = parse_iso_date(end_str) + timedelta(days=1)
        ev_type = EVENT_TYPE_LABELS.get(ev.get("event_type", "sperr"), "Termin")
        summary = f"[{ev_type}] {ev.get('title', 'Termin')}"
        desc = ev.get("notes") or ev.get("production_company") or ""

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{ev_id}@zta-os.local",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{d_start.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{d_end_excl.strftime('%Y%m%d')}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{desc}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def parse_import_payload(
    fmt: str,
    target_collection: str,
    raw_content: str,
    tenant_id: str = "zta-berlin",
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Fehlertoleranter Parser fuer CSV- und JSON-Importe (Prinzip 5.2).
    Gibt (valid_records, warnings) zurueck, ohne bei Einzelzeilen-Fehlern abzustuerzen.
    """
    valid: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    if not raw_content or not raw_content.strip():
        return {}, ["Leerer Import-Inhalt uebergeben."]

    rows: List[Dict[str, Any]] = []
    if fmt == "json":
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                rows = [r for r in parsed if isinstance(r, dict)]
            elif isinstance(parsed, dict):
                rows = [parsed]
            else:
                return {}, ["JSON-Inhalt muss ein Objekt oder eine Liste von Objekten sein."]
        except Exception as exc:
            return {}, [f"Ungueltiges JSON-Format: {exc}"]
    else:
        reader = csv.DictReader(io.StringIO(raw_content.strip()), delimiter=";" if ";" in raw_content.splitlines()[0] else ",")
        for r in reader:
            if isinstance(r, dict):
                rows.append({str(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()})

    for idx, row in enumerate(rows, start=1):
        try:
            doc_id = str(row.get("id") or f"imp-{uuid.uuid4().hex[:8]}")
            if target_collection == "calendar_events":
                client_id = str(row.get("client_id") or "").strip()
                start_d = str(row.get("start_date") or "").strip()
                end_d = str(row.get("end_date") or start_d).strip()
                if not client_id or not start_d:
                    warnings.append(f"Zeile {idx}: Pflichtfelder 'client_id' oder 'start_date' fehlen.")
                    continue
                _ = parse_iso_date(start_d)
                _ = parse_iso_date(end_d)
                valid[doc_id] = {
                    "client_id": client_id,
                    "event_type": str(row.get("event_type") or "sperr").lower(),
                    "title": str(row.get("title") or "Importierter Termin"),
                    "start_date": start_d,
                    "end_date": end_d,
                    "all_day": True,
                    "status": "confirmed",
                    "tenant_id": tenant_id,
                    "updated_at": utc_now_iso(),
                }
            elif target_collection == "inquiries":
                client_id = str(row.get("client_id") or "").strip()
                project_title = str(row.get("project_title") or "").strip()
                start_d = str(row.get("start_date") or "").strip()
                end_d = str(row.get("end_date") or start_d).strip()
                if not client_id or not project_title or not start_d:
                    warnings.append(f"Zeile {idx}: Pflichtfelder ('client_id', 'project_title', 'start_date') fehlen.")
                    continue
                _ = parse_iso_date(start_d)
                _ = parse_iso_date(end_d)
                gage_cents = parse_eur_to_cents(row.get("offered_gage_eur") or row.get("offered_gage_cents") or 0)
                valid[doc_id] = {
                    "client_id": client_id,
                    "project_title": project_title,
                    "production_company": str(row.get("production_company") or ""),
                    "contact_person": str(row.get("contact_person") or ""),
                    "start_date": start_d,
                    "end_date": end_d,
                    "requested_shooting_days": int(row.get("requested_shooting_days") or 1),
                    "offered_gage_cents": gage_cents,
                    "status": "open",
                    "client_response": "pending",
                    "tenant_id": tenant_id,
                    "updated_at": utc_now_iso(),
                }
            elif target_collection == "clients":
                name = str(row.get("name") or "").strip()
                if not name:
                    warnings.append(f"Zeile {idx}: Pflichtfeld 'name' fehlt.")
                    continue
                valid[doc_id] = {
                    "name": name,
                    "division": str(row.get("division") or "schauspiel"),
                    "location": str(row.get("location") or "Berlin"),
                    "commission_rate_bp": int(row.get("commission_rate_bp") or 1000),
                    "status": "active",
                    "tenant_id": tenant_id,
                    "updated_at": utc_now_iso(),
                }
        except Exception as row_exc:
            warnings.append(f"Zeile {idx} uebersprungen: {row_exc}")

    return valid, warnings
