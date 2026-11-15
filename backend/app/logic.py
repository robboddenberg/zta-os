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
        "warning_code": "WARNING_COMMISSION_CAP_EXCEEDED" if exceeds_legal_cap else "",
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



# ==============================================================================
# V10 MASTER-PROMPT & 50-FEATURE LOGIK-ENGINE (STAND 2026-11-13)
# ==============================================================================

DEPARTMENT_LABELS = {
    "actors": "Actors",
    "directors_writers": "Directors + Writers",
    "nxt": "NXT",
    "pr_commercial": "PR & Commercial",
    "consulting": "Consulting",
}

ZDF_GVR_MODELS = {
    "MWF": {
        "code": "MWF",
        "label": "MWF (Produktionen ab 90 Min. / Mitwirkende mit Wiederholungshonoraranspruch)",
        "cap_cents": 1990000,
        "daily_cap_cents": 250000,
        "rates_note": "ZDF-Hauptprogramm (18-24 Uhr) 10 %, Nachmittag 7,5 %, Vormittag 5 %, Nacht 2,5 %, 3sat 4 %, ZDFneo/info 1,4 %, Online 4,5 % (5 J.)",
    },
    "MW60": {
        "code": "MW60",
        "label": "MW 60-minuetige Formate (Krimi & 60-Min.-Reihen)",
        "cap_cents": 1390000,
        "daily_cap_cents": 250000,
        "rates_note": "Wiederholungshonorar ab 1. Wiederholung (10 % Hauptprogramm), Deckel 13.900 EUR (Krimi) bzw. 17.100 EUR (sonstige 60 Min.)",
    },
    "MWFA": {
        "code": "MWFA",
        "label": "MWFA (Punkte-Modell fuer Serien <= 45 Min. / Teil-Abgeltung 15 Punkte)",
        "cap_cents": 1390000,
        "daily_cap_cents": 250000,
        "rates_note": "15 Nutzungspunkte in Erstverguetung enthalten; ab 16. Punkt +20 % fuer 6 Punkte, ab 22. Punkt +18 %",
    },
}


def validate_sperrtermin_v10(
    level: str,
    location: str,
    start_date: str = "2026-11-18",
    end_date: str = "2026-11-18",
    raise_on_error: bool = False,
) -> Dict[str, Any]:
    """
    Validiert einen Sperrtermin nach den festen V10-Regeln (Features 17, 18, 24, 25, 26):
    - Stufe 'rot' erfordert zwingend einen Ort (wegen Anreise-/Fahrtzeiten am Vor- oder Folgetag).
    """
    clean_level = str(level or "rot").lower().strip()
    if clean_level not in ("rot", "orange"):
        msg = "Sperrtermin-Stufe muss 'rot' oder 'orange' sein."
        if raise_on_error:
            raise ValueError(msg)
        return {"valid": False, "error": msg, "level": clean_level, "location": "", "color_hex": "#DC2626"}
    clean_loc = str(location or "").strip()
    if clean_level == "rot" and not clean_loc:
        msg = "Pflichtfeld Ort fehlt: Bei einem verbindlichen roten Sperrtermin muss der Ort angegeben werden (wegen Fahrtzeiten am Vor- und Folgetag)."
        if raise_on_error:
            raise ValueError(msg)
        return {"valid": False, "error": msg, "level": clean_level, "location": "", "color_hex": "#DC2626"}
    _ = parse_iso_date(start_date or "2026-11-18")
    _ = parse_iso_date(end_date or start_date or "2026-11-18")
    return {
        "valid": True,
        "error": "",
        "level": clean_level,
        "location": clean_loc,
        "start_date": start_date or "2026-11-18",
        "end_date": end_date or start_date or "2026-11-18",
        "color_hex": "#DC2626" if clean_level == "rot" else "#EA580C",
    }


def evaluate_inquiry_v10(
    inq_id_or_dict: Any,
    inq: Optional[Dict[str, Any]] = None,
    reference_date: str = "2026-11-14",
) -> Dict[str, Any]:
    """
    Leitet den Status einer Zeitanfrage automatisch nach V10-Regeln ab (Features 36, 44, 46, 50).
    Akzeptiert sowohl evaluate_inquiry_v10(inq_dict, reference_date=...) als auch evaluate_inquiry_v10(inq_id, inq_dict, reference_date=...).
    """
    if isinstance(inq_id_or_dict, dict):
        doc = dict(inq_id_or_dict)
        inq_id = str(doc.get("id") or "inq-temp")
    else:
        inq_id = str(inq_id_or_dict or "inq-temp")
        doc = dict(inq or {})

    doc.pop("synopsis", None)
    doc.pop("script_longtext", None)

    dzr_start = str(doc.get("dzr_start") or doc.get("start_date") or "2026-11-20")[:10]
    dzr_end = str(doc.get("dzr_end") or doc.get("end_date") or dzr_start)[:10]
    dropbox_url = str(doc.get("contract_dropbox_url") or "").strip()
    is_booked = bool(dropbox_url)

    try:
        ref_d = parse_iso_date(reference_date)
        start_d = parse_iso_date(dzr_start)
        dzr_started = start_d <= ref_d
    except Exception:
        dzr_started = False

    is_expired_without_booking = bool(dzr_started and not is_booked)
    stage = str(doc.get("pipeline_stage") or "zeitanfrage")

    if is_booked:
        derived_status = "gebucht"
        derived_label = "Gebucht (Vertrag in Dropbox)"
    elif is_expired_without_booking:
        derived_status = "ohne_buchung_verfallen"
        derived_label = "DZR begonnen (ohne Buchung / erledigt)"
    else:
        derived_status = stage
        stage_labels = {
            "zeitanfrage": "Zeitanfrage offen",
            "e_casting": "E-Casting aktiv",
            "live_casting": "Live-Casting aktiv",
        }
        derived_label = stage_labels.get(stage, "Aktiv")

    doc["id"] = inq_id
    doc["project_name"] = doc.get("project_name") or doc.get("project_title") or "Projekt"
    doc["project_title"] = doc.get("project_title") or doc["project_name"]
    doc["dzr_start"] = dzr_start
    doc["dzr_end"] = dzr_end
    doc["is_booked"] = is_booked
    doc["is_expired_without_booking"] = is_expired_without_booking
    doc["is_grayed_out"] = is_expired_without_booking
    doc["derived_status"] = derived_status
    doc["derived_label"] = derived_label
    return doc


def compute_sperrtermin_rechner(
    client_id: str,
    dzr_start: str,
    dzr_end: str,
    sender_category: str = "ARD/Degeto",
    clients: Optional[Dict[str, Dict[str, Any]]] = None,
    calendar_events: Optional[Dict[str, Dict[str, Any]]] = None,
    inquiries: Optional[Dict[str, Dict[str, Any]]] = None,
    castings: Optional[Dict[str, Dict[str, Any]]] = None,
    fee_matrix: Optional[Dict[str, Dict[str, Any]]] = None,
    include_adjacent_days: bool = True,
    client_name: str = "",
    project_name: str = "",
) -> Dict[str, Any]:
    """
    Modul 1 Kernstueck: Sperrtermin-Rechner fuer Team ZTA (Feature 49, F35).
    """
    clients = clients or {}
    calendar_events = calendar_events or {}
    inquiries = inquiries or {}
    castings = castings or {}
    fee_matrix = fee_matrix or {}

    client = clients.get(client_id, {"name": client_name or client_id})
    resolved_client_name = client_name or client.get("name", client_id)

    sperr_hits: List[Dict[str, Any]] = []
    zta_hits: List[Dict[str, Any]] = []
    casting_hits: List[Dict[str, Any]] = []
    adjacent_hits: List[Dict[str, Any]] = []

    d_start = parse_iso_date(dzr_start)
    d_end = parse_iso_date(dzr_end)
    if d_start > d_end:
        d_start, d_end = d_end, d_start
    total_days = (d_end - d_start).days + 1
    dzr_start_iso = d_start.isoformat()
    dzr_end_iso = d_end.isoformat()
    day_before_iso = (d_start - timedelta(days=1)).isoformat()
    day_after_iso = (d_end + timedelta(days=1)).isoformat()

    for ev_id, ev in calendar_events.items():
        if ev.get("client_id") != client_id or ev.get("status") == "cancelled":
            continue
        ev_s = str(ev.get("start_date") or "")[:10]
        ev_e = str(ev.get("end_date") or ev_s)[:10]
        if not ev_s:
            continue
        ev_type = str(ev.get("event_type") or "sperr").lower()
        ev_cat = str(ev.get("category") or ("sperrtermin" if ev_type in ("sperr", "sperrtermin") else "zta_termin"))
        level = str(ev.get("level") or ev.get("sperr_level") or ("rot" if ev_type in ("sperr", "sperrtermin") else "zta")).lower()
        loc = str(ev.get("location") or "Berlin")

        item = {
            "id": ev_id,
            "title": ev.get("title", "Termin"),
            "event_type": ev_type,
            "category": ev_cat,
            "level": level,
            "sperr_level": level,
            "location": loc,
            "start_date": ev_s,
            "end_date": ev_e,
        }

        if ranges_overlap(dzr_start_iso, dzr_end_iso, ev_s, ev_e):
            if ev_cat == "sperrtermin" or ev_type in ("sperr", "sperrtermin"):
                sperr_hits.append(item)
            elif ev_cat == "casting" or ev_type == "casting":
                casting_hits.append(item)
            else:
                zta_hits.append(item)
        elif include_adjacent_days and (
            ranges_overlap(day_before_iso, day_before_iso, ev_s, ev_e)
            or ranges_overlap(day_after_iso, day_after_iso, ev_s, ev_e)
        ):
            adjacent_hits.append(item)

    for inq_id, inq in inquiries.items():
        if inq.get("client_id") != client_id:
            continue
        for c_field, c_label in (
            ("e_casting_deadline", "E-Casting-Frist"),
            ("live_casting_date", "Live-Casting"),
        ):
            c_date = str(inq.get(c_field) or "")[:10]
            if c_date and ranges_overlap(dzr_start_iso, dzr_end_iso, c_date, c_date):
                casting_hits.append(
                    {
                        "id": f"{inq_id}-{c_field}",
                        "title": f"{c_label}: {inq.get('project_title') or inq.get('project_name') or 'Projekt'}",
                        "event_type": "casting",
                        "category": "casting",
                        "level": "casting",
                        "location": str(inq.get("live_casting_location") or inq.get("shooting_location") or "Berlin"),
                        "start_date": c_date,
                        "end_date": c_date,
                    }
                )

    for cast_id, cast in castings.items():
        if cast.get("client_id") != client_id:
            continue
        dl = str(cast.get("deadline_date") or "")[:10]
        if dl and ranges_overlap(dzr_start_iso, dzr_end_iso, dl, dl):
            casting_hits.append(
                {
                    "id": cast_id,
                    "title": f"Casting-Frist: {cast.get('project_title', 'Casting')}",
                    "event_type": "casting",
                    "category": "casting",
                    "level": "casting",
                    "location": "Berlin / E-Casting",
                    "start_date": dl,
                    "end_date": dl,
                }
            )

    sperr_hits.sort(key=lambda x: x["start_date"])
    zta_hits.sort(key=lambda x: x["start_date"])
    casting_hits.sort(key=lambda x: x["start_date"])

    matched_fee: Optional[Dict[str, Any]] = None
    for fid, fdoc in fee_matrix.items():
        if fdoc.get("client_id") == client_id and str(fdoc.get("category") or "").lower() == sender_category.lower():
            matched_fee = dict(fdoc)
            matched_fee["id"] = fid
            matched_fee["guideline_eur"] = format_eur_from_cents(int(matched_fee.get("guideline_cents") or 0))
            matched_fee.setdefault("unit", "Tag")
            break

    red_blockers = [s for s in sperr_hits if s["level"] == "rot"]
    orange_blockers = [s for s in sperr_hits if s["level"] == "orange"]

    proj_part = f" zum Projekt '{project_name}'" if project_name else ""
    reply_lines = [
        "Guten Tag,",
        "",
        f"vielen Dank für die Zeitanfrage für {resolved_client_name}{proj_part} im Drehzeitraum (DZR) {dzr_start_iso} bis {dzr_end_iso}.",
    ]
    if not red_blockers and not orange_blockers and not zta_hits:
        reply_lines.append(
            f"Im angefragten DZR liegen aktuell keine Sperrtermine für {resolved_client_name} vor."
        )
    else:
        if red_blockers:
            red_str = "; ".join(
                f"{b['start_date']} bis {b['end_date']} (verbindlich gesperrt, Ort: {b['location'] or 'Berlin'})"
                for b in red_blockers
            )
            reply_lines.append(f"Verbindliche Sperrtermine im DZR (bitte bei der Dispo aussparen): {red_str}.")
        if orange_blockers:
            org_str = "; ".join(
                f"{b['start_date']} bis {b['end_date']} (Option/Vorbehalt, Ort: {b['location'] or 'Berlin'})"
                for b in orange_blockers
            )
            reply_lines.append(f"Termine unter Vorbehalt (nach Rücksprache ggf. schiebbar): {org_str}.")
        if zta_hits:
            zta_str = "; ".join(
                f"{z['title']} ({z['start_date']} bis {z['end_date']})" for z in zta_hits
            )
            reply_lines.append(f"Bereits disponierte ZTA-Termine im Zeitraum: {zta_str}.")

    if adjacent_hits:
        adj_str = "; ".join(
            f"{a['start_date']} ({a['title']}, Ort: {a['location']})" for a in adjacent_hits
        )
        reply_lines.append(f"Hinweis zu Randtagen (An-/Abreise): {adj_str}.")

    if matched_fee:
        unit_label = "Wochengage" if matched_fee.get("unit") == "Woche" else "Tagesgage"
        gw_cents = int(matched_fee.get("guideline_cents") or 0)
        ma_cents = int(matched_fee.get("guideline_ma_cents") or 0)
        fee_line = f"Gagen-Richtwert ({sender_category}, {unit_label}): {format_eur_from_cents(gw_cents)} (MW)"
        if ma_cents > 0:
            fee_line += f" bzw. {format_eur_from_cents(ma_cents)} (MA / Buyout)"
        fee_line += " zzgl. Agenturprovision und USt."
        reply_lines.append("")
        reply_lines.append(fee_line)

    reply_lines.extend(["", "Herzliche Grüße", "ZTA Management Berlin"])
    reply_text = "\n".join(reply_lines)

    return {
        "client_id": client_id,
        "client_name": resolved_client_name,
        "dzr_start": dzr_start_iso,
        "dzr_end": dzr_end_iso,
        "total_days": total_days,
        "highlight_color": "#F2D2C7",
        "sender_category": sender_category,
        "sperrtermine": sperr_hits,
        "sperrtermine_rot": red_blockers,
        "sperrtermine_orange": orange_blockers,
        "red_count": len(red_blockers),
        "orange_count": len(orange_blockers),
        "zta_termine": zta_hits,
        "castings_in_dzr": casting_hits,
        "adjacent_day_warnings": adjacent_hits,
        "adjacent_travel_warnings": adjacent_hits,
        "matched_fee": matched_fee,
        "matched_fee_guideline": matched_fee,
        "reply_text": reply_text,
        "copyable_reply_text": reply_text,
    }


def upsert_fee_entry_v10(
    collections: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    client_id: str = "cl-01",
    category: str = "ARD/Degeto",
    last_achieved_cents: int = 0,
    guideline_cents: int = 0,
    unit: str = "Tag",
    currency: str = "EUR",
    guideline_ma_cents: Optional[int] = None,
    variant_default: str = "MW",
    settlement_model: str = "MW",
    valid_years: str = "2025+2026",
    target_next_year_cents: int = 0,
    fee_status: str = "fest",
    status: str = "fest",
    zdf_model: str = "",
    zdf_length_model: str = "",
    auto_raise_guideline: bool = True,
    entry_id: Optional[str] = None,
    existing_entry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Pflegt einen Eintrag im Gagen-Spiegel nach den festen V10-Regeln (Features 22, 28-33, 37).
    """
    if category.lower() == "commercial":
        raise ValueError("Commercial-Gagen werden gemaess Regel F17/F19 nicht im Gagen-Spiegel gefuehrt.")
    resolved_unit = "Woche" if category == "International" else unit
    if resolved_unit == "Woche" and category != "International":
        raise ValueError("Wochengagen sind gemaess Regel F20 ausschliesslich bei der Kategorie 'International' zulaessig.")

    achieved = int(last_achieved_cents)
    base_guideline = int(guideline_cents or (existing_entry or {}).get("guideline_cents") or 0)
    guideline = base_guideline
    guideline_raised = False
    upgrade_suggested = achieved > guideline

    if upgrade_suggested and auto_raise_guideline:
        guideline = achieved
        guideline_raised = True

    if guideline_ma_cents is None or guideline_raised:
        ma_val = round_cents_decimal(Decimal(guideline) * Decimal("1.10"))
    else:
        ma_val = int(guideline_ma_cents)

    target_ny = int(target_next_year_cents) or round_cents_decimal(Decimal(guideline) * Decimal("1.08"))
    resolved_variant = settlement_model or variant_default or "MW"
    resolved_status = status or fee_status or "fest"
    resolved_zdf = (zdf_length_model or zdf_model) if category == "ZDF" else ""

    record = {
        "client_id": client_id,
        "category": category,
        "unit": resolved_unit,
        "currency": currency,
        "last_achieved_cents": achieved,
        "guideline_cents": guideline,
        "guideline_ma_cents": ma_val,
        "ma_buyout_cents": ma_val,
        "variant_default": resolved_variant,
        "settlement_model": resolved_variant,
        "valid_years": valid_years,
        "valid_year": 2026,
        "target_next_year_cents": target_ny,
        "fee_status": resolved_status,
        "status": resolved_status,
        "zdf_model": resolved_zdf,
        "zdf_length_model": resolved_zdf,
        "guideline_raised": guideline_raised,
        "guideline_auto_upgraded": guideline_raised,
        "upgrade_suggested": upgrade_suggested,
        "tenant_id": "zta-berlin",
        "updated_at": utc_now_iso(),
    }

    if collections is not None:
        fee_col = collections.setdefault("fee_matrix", {})
        target_id = entry_id
        if not target_id:
            for fid, fdoc in fee_col.items():
                if fdoc.get("client_id") == client_id and fdoc.get("category") == category:
                    target_id = fid
                    break
        if not target_id:
            target_id = f"fee-{client_id}-{category.lower().replace('/', '-')}"
        fee_col[target_id] = record
        record_with_id = dict(record, id=target_id, entry_id=target_id)
        return {"entry_id": target_id, "record": record_with_id, "entry": record_with_id, **record_with_id}

    return record


def validate_master_data_plausibility(profile: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Prueft Stammdaten auf Tipp-, Format- und Logikfehler (Features 2, 5, 7, 9, 14; loest P4, P5, P8, P11).
    """
    issues: List[Dict[str, str]] = []
    md = profile.get("master_data") if isinstance(profile.get("master_data"), dict) else profile

    def _val(key: str) -> str:
        raw = md.get(key, "")
        if isinstance(raw, dict):
            return str(raw.get("value") or "").strip()
        return str(raw or "").strip()

    iban = _val("iban").replace(" ", "")
    if iban:
        if iban.upper().startswith("DE") and len(iban) != 22:
            issues.append({"field": "iban", "severity": "error", "message": f"Deutsche IBAN muss exakt 22 Zeichen lang sein (aktuell: {len(iban)})."})
        elif not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$", iban.upper()):
            issues.append({"field": "iban", "severity": "error", "message": "IBAN-Format oder Pruefziffer unplausibel."})

    bic = _val("bic").replace(" ", "")
    if bic and len(bic) not in (8, 11):
        issues.append({"field": "bic", "severity": "error", "message": f"BIC muss 8 oder 11 Zeichen haben (aktuell: {len(bic)} Zeichen, siehe P4)."})

    tax_id = _val("tax_id").replace(" ", "")
    if tax_id:
        if tax_id.upper().startswith("DE"):
            issues.append({"field": "tax_id", "severity": "error", "message": "Im Feld Steuer-ID steht eine USt-IdNr. ('DE...'). Bitte Felder nicht verwechseln (siehe P4)."})
        elif not re.match(r"^\d{11}$", tax_id):
            issues.append({"field": "tax_id", "severity": "error", "message": "Steuer-ID muss aus exakt 11 Ziffern bestehen."})

    sv_nr = _val("sv_number").replace(" ", "")
    if sv_nr and not re.match(r"^\d{8}[A-Z]\d{3}$", sv_nr.upper()):
        issues.append({"field": "sv_number", "severity": "error", "message": "SV-Nummer unvollstaendig oder fehlerhaft (erwartet: 12 Zeichen, Format TTMMJJ + Buchstabe + Pruefziffer, siehe P4)."})

    tax_class = _val("tax_class")
    if not tax_class:
        issues.append({"field": "tax_class", "severity": "warning", "message": "Steuerklasse ist leer (Risiko Abrechnung nach Steuerklasse 6, siehe P8)."})

    combined_notes = " ".join([_val("notes"), str(profile.get("bio") or "")]).lower()
    if any(tok in combined_notes for tok in ("pin:", "passwort:", "password:", "tan:")):
        issues.append({"field": "notes", "severity": "error", "message": "Sicherheitswarnung (Feature 14): Keine PINs oder Zugangsdaten in Profilfeldern speichern!"})

    return issues


def compute_industry_interest_indicators(
    client_id: str,
    inquiries: Dict[str, Dict[str, Any]],
    castings: Dict[str, Dict[str, Any]],
    reference_date: str = "2026-11-14",
) -> Dict[str, Any]:
    """
    Berechnet die 4 Branchen-Interesse-Indikatoren auf #F2D2C7 und die Jahresgespraechs-Auswertung
    (Features 35, 44, 45, 50 - STRIKT NUR FUER TEAM ZTA SICHTBAR!).
    """
    client_inqs = [
        evaluate_inquiry_v10(iid, idoc, reference_date=reference_date)
        for iid, idoc in inquiries.items()
        if idoc.get("client_id") == client_id
    ]
    client_casts = [cdoc for cdoc in castings.values() if cdoc.get("client_id") == client_id]

    inquiries_count = len(client_inqs)

    e_castings_count = sum(
        1
        for i in client_inqs
        if i.get("pipeline_stage") in ("e_casting", "live_casting") or bool(i.get("e_casting_deadline"))
    ) + sum(1 for c in client_casts if c.get("casting_type") == "e_casting")

    live_castings_count = sum(
        1
        for i in client_inqs
        if i.get("pipeline_stage") == "live_casting" or bool(i.get("live_casting_date"))
    ) + sum(1 for c in client_casts if c.get("casting_type") == "live_casting")

    bookings_count = sum(1 for i in client_inqs if i.get("is_booked"))

    total_castings = e_castings_count + live_castings_count

    hints: List[str] = []
    if inquiries_count == 0:
        hints.append("Kaum oder keine Zeitanfragen erfasst: Sichtbarkeits- und Material-Impuls bei Caster:innen prüfen.")
    elif total_castings == 0 and inquiries_count > 0:
        hints.append("Nur Zeitanfragen, bisher keine Castings: Rollenprofil und Demoband-Auswahl im Jahresgespräch abgleichen.")
    elif total_castings >= 2 and bookings_count == 0:
        hints.append("Viele Castings, aber noch keine Buchung: E-Casting-Inszenierung und Recall-Vorbereitung gemeinsam besprechen.")
    elif bookings_count > 0:
        hints.append(f"Positive Conversion: {bookings_count} Buchung(en) mit hinterlegtem Vertrag in Dropbox.")

    by_project_type: Dict[str, int] = {}
    by_time_slot: Dict[str, int] = {}
    by_role_size: Dict[str, int] = {}
    by_caster: Dict[str, int] = {}

    for inq in client_inqs:
        pt = str(inq.get("project_type") or "Sonstige")
        ts = str(inq.get("time_slot") or inq.get("sender_platform") or "Sonstige")
        rs = str(inq.get("role_size") or "Hauptrolle")
        ca = str(inq.get("caster_name") or inq.get("contact_person") or "Unbekannt")
        by_project_type[pt] = by_project_type.get(pt, 0) + 1
        by_time_slot[ts] = by_time_slot.get(ts, 0) + 1
        by_role_size[rs] = by_role_size.get(rs, 0) + 1
        by_caster[ca] = by_caster.get(ca, 0) + 1

    return {
        "client_id": client_id,
        "tiles": {
            "zeitanfragen": inquiries_count,
            "e_castings": e_castings_count,
            "live_castings": live_castings_count,
            "buchungen": bookings_count,
        },
        "kpi_tiles_pink": {
            "zeitanfragen": inquiries_count,
            "e_castings": e_castings_count,
            "live_castings": live_castings_count,
            "buchungen": bookings_count,
        },
        "conversation_hints": hints,
        "breakdown": {
            "by_project_type": by_project_type,
            "by_time_slot": by_time_slot,
            "by_role_size": by_role_size,
            "by_caster": by_caster,
        },
        "annual_review_breakdown": {
            "by_project_type": by_project_type,
            "by_time_slot": by_time_slot,
            "by_role_size": by_role_size,
            "by_caster": by_caster,
        },
    }


def build_client_rbac_view(
    state: Dict[str, Any],
    client_id: str,
    reference_date: str = "2026-11-14",
) -> Dict[str, Any]:
    """
    Erzeugt die strikt nach V10 RBAC (Abschnitt 2B) gefilterte Ansicht fuer eine Langzeit-Klient:in.
    """
    cols = state["collections"]
    client = cols.get("clients", {}).get(client_id)
    if not client:
        raise ValueError(f"Klient:in '{client_id}' nicht gefunden.")
    if not client.get("has_app_access", True):
        raise PermissionError(
            "Kein App-Zugang: Consulting- und projektbezogene PR-Klient:innen haben gemaess Regel 42 keinen eigenen App-Zugang."
        )

    own_events = [
        dict(ev, id=ev_id)
        for ev_id, ev in cols.get("calendar_events", {}).items()
        if ev.get("client_id") == client_id and ev.get("status") != "cancelled"
    ]

    own_inquiries_readonly = []
    for iid, inq in cols.get("inquiries", {}).items():
        if inq.get("client_id") != client_id:
            continue
        ev_inq = evaluate_inquiry_v10(iid, inq, reference_date=reference_date)
        own_inquiries_readonly.append(
            {
                "id": iid,
                "received_date": ev_inq.get("received_date") or ev_inq.get("start_date"),
                "caster_name": ev_inq.get("caster_name") or ev_inq.get("contact_person") or "",
                "project_title": ev_inq.get("project_title", ""),
                "production_company": ev_inq.get("production_company", ""),
                "sender_platform": ev_inq.get("sender_platform", ""),
                "project_type": ev_inq.get("project_type", ""),
                "time_slot": ev_inq.get("time_slot", ""),
                "role_size": ev_inq.get("role_size", ""),
                "dzr_start": ev_inq.get("dzr_start", ""),
                "dzr_end": ev_inq.get("dzr_end", ""),
                "shooting_days": ev_inq.get("shooting_days") or ev_inq.get("requested_shooting_days") or 1,
                "shooting_location": ev_inq.get("shooting_location", "Berlin"),
                "e_casting_deadline": ev_inq.get("e_casting_deadline", ""),
                "live_casting_date": ev_inq.get("live_casting_date", ""),
                "can_respond": False,
            }
        )

    own_guidelines_only = []
    for fid, fdoc in cols.get("fee_matrix", {}).items():
        if fdoc.get("client_id") != client_id:
            continue
        cat = str(fdoc.get("category") or "")
        if cat.lower() == "commercial":
            continue
        own_guidelines_only.append(
            {
                "id": fid,
                "category": cat,
                "unit": fdoc.get("unit", "Tag"),
                "currency": fdoc.get("currency", "EUR"),
                "guideline_cents": int(fdoc.get("guideline_cents") or 0),
                "formatted_guideline": format_eur_from_cents(int(fdoc.get("guideline_cents") or 0)),
                "valid_years": fdoc.get("valid_years", "2026"),
            }
        )

    own_notifications = [
        dict(n, id=nid)
        for nid, n in cols.get("notifications", {}).items()
        if n.get("client_id") == client_id
    ]

    return {
        "role": "klient",
        "client": {
            "id": client_id,
            "name": client.get("name"),
            "department": client.get("department", "actors"),
            "location": client.get("location", "Berlin"),
            "photo_url": client.get("photo_url", ""),
            "master_data_readonly": client.get("master_data", {}),
        },
        "calendar_events": own_events,
        "inquiries_readonly": own_inquiries_readonly,
        "my_fee_guidelines": own_guidelines_only,
        "notifications": own_notifications,
    }


# ============================================================================
# V10.2 EXECUTIVE AI CO-PILOT, 9 PLAYBOOKS (A-I) & ACCESS CONTROL GOVERNANCE
# ============================================================================

def build_confirmation_gate(
    operation: str,
    target_entity: str,
    impact: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Erzeugt das verpflichtende Destructive Action Confirmation Gate (Abschnitt 2.3 PDF-Spezifikation).
    """
    prompt_text = (
        "⚠ Action Confirmation Required\n"
        f"- Operation: {operation}\n"
        f"- Target Entity: {target_entity}\n"
        f"- Financial / Schedule Impact: {impact}\n"
        "Please reply with 'CONFIRM' to execute or 'CANCEL' to abort."
    )
    return {
        "requires_confirmation": True,
        "status": "confirmation_required",
        "operation": operation,
        "target_entity": target_entity,
        "impact": impact,
        "prompt": prompt_text,
        "pending_payload": payload or {},
    }


def resolve_client_fuzzy(
    clients: Dict[str, Dict[str, Any]],
    query: str,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Loest einen Klient:innen-Namen oder eine ID fehlertolerant ueber client_id, name, full_name
    und name_variants auf (Playbook C Schritt 1).
    """
    q = str(query or "").strip()
    if not q:
        for cid, cdoc in sorted(clients.items()):
            return cid, cdoc
        return None, None
    if q in clients:
        return q, clients[q]
    q_low = q.lower()
    for cid, cdoc in clients.items():
        name_low = str(cdoc.get("name") or "").lower()
        full_low = str(cdoc.get("full_name") or name_low).lower()
        variants = [str(v).lower() for v in (cdoc.get("name_variants") or [])]
        if q_low == name_low or q_low == full_low or q_low in variants:
            return cid, cdoc
    for cid, cdoc in clients.items():
        name_low = str(cdoc.get("name") or "").lower()
        variants = [str(v).lower() for v in (cdoc.get("name_variants") or [])]
        if q_low in name_low or any(q_low in v for v in variants):
            return cid, cdoc
    return None, None


def calculate_sperrtermin_dzr(
    client_id: str,
    dzr_start: str,
    dzr_end: str,
    sender_category: str = "ZDF",
    project_name: str = "",
    clients: Optional[Dict[str, Dict[str, Any]]] = None,
    calendar_events: Optional[Dict[str, Dict[str, Any]]] = None,
    fee_matrix: Optional[Dict[str, Dict[str, Any]]] = None,
    include_adjacent_days: bool = True,
    reference_date: str = "2026-11-14",
) -> Dict[str, Any]:
    """
    Wrapper um compute_sperrtermin_rechner mit harmonisierten Schluesseln fuer die Co-Pilot Playbooks.
    """
    res = compute_sperrtermin_rechner(
        client_id=client_id,
        dzr_start=dzr_start,
        dzr_end=dzr_end,
        sender_category=sender_category,
        clients=clients,
        calendar_events=calendar_events,
        fee_matrix=fee_matrix,
        include_adjacent_days=include_adjacent_days,
        project_name=project_name,
    )
    mf = res.get("matched_fee") or {}
    gw_cents = int(mf.get("guideline_cents") or 0)
    res["red_blockers"] = res.get("sperrtermine_rot", [])
    res["orange_blockers"] = res.get("sperrtermine_orange", [])
    res["guideline_fee_cents"] = gw_cents
    res["guideline_fee_formatted"] = format_eur_from_cents(gw_cents) if gw_cents else "TBA"
    res["copy_text_snippet"] = res.get("copyable_reply_text", "")
    return res


def validate_client_master_data(profile: Dict[str, Any]) -> List[Dict[str, str]]:
    return validate_master_data_plausibility(profile)


def build_weekly_briefing_feed(
    state: Dict[str, Any],
    reference_date: str = "2026-11-14",
) -> Dict[str, Any]:
    """
    Playbook A ("Was steht diese Woche an?") & GET /api/feed/weekly-briefing.
    Aggregiert alle 7-Tage-Termine, Castings (inkl. 48h interner Sichtungsfrist),
    offene Zeitanfragen und Liquiditaets-KPIs.
    """
    cols = state["collections"]
    clients = cols.get("clients", {})
    events = cols.get("calendar_events", {})
    inquiries = cols.get("inquiries", {})
    castings = cols.get("castings", {})
    contracts = cols.get("contracts", {})

    ref_d = parse_iso_date(reference_date)
    end_d = ref_d + timedelta(days=7)
    start_iso = ref_d.isoformat()
    end_iso = end_d.isoformat()

    # 1. Critical Deadlines (Next 48 Hours)
    critical_48h: List[Dict[str, Any]] = []
    for cid_cast, cdoc in castings.items():
        dl_str = str(cdoc.get("deadline_date") or "")
        if not dl_str:
            continue
        sched = compute_casting_schedule(dl_str, reference_date, str(cdoc.get("tape_status") or "open"))
        if sched["urgency"] in ("overdue", "critical", "soon") or 0 <= sched["days_until_deadline"] <= 7:
            cl_name = clients.get(str(cdoc.get("client_id")), {}).get("name", cdoc.get("client_id"))
            critical_48h.append({
                "id": cid_cast,
                "type": cdoc.get("casting_type", "e_casting"),
                "client_id": cdoc.get("client_id"),
                "client_name": cl_name,
                "project_title": cdoc.get("project_title", ""),
                "deadline_date": sched["deadline_date"],
                "internal_review_date": sched["internal_review_date"],
                "urgency": sched["urgency"],
                "countdown_label": sched["countdown_label"],
            })

    for iid, idoc in inquiries.items():
        ev_inq = evaluate_inquiry_v10(iid, idoc, reference_date=reference_date)
        dl_str = str(ev_inq.get("e_casting_deadline") or "")
        if dl_str:
            sched = compute_casting_schedule(dl_str, reference_date, "open")
            if sched["urgency"] in ("overdue", "critical", "soon"):
                cl_name = clients.get(str(ev_inq.get("client_id")), {}).get("name", ev_inq.get("client_id"))
                critical_48h.append({
                    "id": iid,
                    "type": "inquiry_e_casting",
                    "client_id": ev_inq.get("client_id"),
                    "client_name": cl_name,
                    "project_title": ev_inq.get("project_title", ""),
                    "deadline_date": sched["deadline_date"],
                    "internal_review_date": sched["internal_review_date"],
                    "urgency": sched["urgency"],
                    "countdown_label": sched["countdown_label"],
                })

    # 2. Confirmed Production Schedule (Drehtage, ADR, Store Openings, Festivals im 7-Tage-Fenster)
    production_schedule: List[Dict[str, Any]] = []
    blockouts_week: List[Dict[str, Any]] = []
    for ev_id, ev in events.items():
        if ev.get("status") == "cancelled":
            continue
        ev_s = str(ev.get("start_date") or "")
        ev_e = str(ev.get("end_date") or ev_s)
        if not ev_s or not ranges_overlap(start_iso, end_iso, ev_s, ev_e):
            continue
        cl_name = clients.get(str(ev.get("client_id")), {}).get("name", ev.get("client_id"))
        cat = str(ev.get("category") or "")
        ev_type = str(ev.get("event_type") or "")
        entry = {
            "id": ev_id,
            "client_id": ev.get("client_id"),
            "client_name": cl_name,
            "title": ev.get("title", ""),
            "start_date": ev_s,
            "end_date": ev_e,
            "category": cat,
            "event_type": ev_type,
            "location": ev.get("location", "Berlin"),
            "sperr_level": ev.get("sperr_level", ""),
        }
        if cat == "sperrtermin" or ev_type == "sperr":
            blockouts_week.append(entry)
        else:
            production_schedule.append(entry)

    production_schedule.sort(key=lambda x: x["start_date"])
    blockouts_week.sort(key=lambda x: x["start_date"])

    # 3. Open Time Requests (Action Required)
    open_time_requests: List[Dict[str, Any]] = []
    for iid, idoc in inquiries.items():
        ev_inq = evaluate_inquiry_v10(iid, idoc, reference_date=reference_date)
        if ev_inq.get("status") in ("open", "optioned") and not ev_inq.get("is_booked"):
            cl_id = str(ev_inq.get("client_id") or "")
            cl_name = clients.get(cl_id, {}).get("name", cl_id)
            calc = calculate_sperrtermin_dzr(
                client_id=cl_id,
                dzr_start=ev_inq["dzr_start"],
                dzr_end=ev_inq["dzr_end"],
                sender_category=ev_inq.get("sender_platform", "ZDF"),
                project_name=ev_inq.get("project_title", ""),
                clients=clients,
                calendar_events=events,
                fee_matrix=cols.get("fee_matrix", {}),
                include_adjacent_days=True,
                reference_date=reference_date,
            )
            open_time_requests.append({
                "id": iid,
                "client_id": cl_id,
                "client_name": cl_name,
                "caster_name": ev_inq.get("caster_name", ""),
                "project_title": ev_inq.get("project_title", ""),
                "sender_platform": ev_inq.get("sender_platform", ""),
                "dzr_start": ev_inq.get("dzr_start", ""),
                "dzr_end": ev_inq.get("dzr_end", ""),
                "shooting_days": ev_inq.get("shooting_days", 1),
                "pipeline_stage": ev_inq.get("pipeline_stage", "zeitanfrage"),
                "red_conflicts_count": len(calc["red_blockers"]),
                "orange_conflicts_count": len(calc["orange_blockers"]),
                "travel_warnings_count": len(calc["adjacent_travel_warnings"]),
            })

    # 4. Financial Snapshot
    liq = build_liquidity_timeline(contracts, clients)
    conf_c = int(liq.get("total_confirmed_commission_cents") or 0)
    paid_c = int(liq.get("total_paid_commission_cents") or 0)
    open_c = int(liq.get("total_open_receivables_cents") or 0)
    payout_c = int(liq.get("total_pending_client_payout_cents") or 0)
    fin_summary = {
        "confirmed_commission_cents": conf_c,
        "paid_commission_cents": paid_c,
        "open_receivables_cents": open_c,
        "pending_client_payout_cents": payout_c,
        "formatted": {
            "confirmed_commission": format_eur_from_cents(conf_c),
            "paid_commission": format_eur_from_cents(paid_c),
            "open_receivables": format_eur_from_cents(open_c),
            "pending_client_payout": format_eur_from_cents(payout_c),
        },
    }

    # Executive Markdown Report
    md_lines = [
        f"### Executive Weekly Briefing ({start_iso} bis {end_iso})",
        "",
        "#### 1. Kritische Fristen & E-Castings (Naechste 48h / 7 Tage)",
    ]
    if critical_48h:
        for c in critical_48h:
            md_lines.append(
                f"- **[{c['urgency'].upper()}] {c['client_name']}** · *{c['project_title']}* "
                f"(Interne ZTA-Sichtung: `{c['internal_review_date']}` | Caster-Deadline: `{c['deadline_date']}`) · {c['countdown_label']}"
            )
    else:
        md_lines.append("- Keine kritischen E-Casting-Deadlines in den naechsten 48 Stunden.")

    md_lines.extend(["", "#### 2. Bestaetigter Produktions- & Terminplan (ZTA Blue `#0A1AE4`)"])
    if production_schedule:
        for p in production_schedule:
            md_lines.append(
                f"- `{p['start_date']}` bis `{p['end_date']}` · **{p['client_name']}**: {p['title']} ({p['location']})"
            )
    else:
        md_lines.append("- Keine Drehtage im 7-Tage-Fenster eingetragen.")

    if blockouts_week:
        md_lines.extend(["", "#### 2b. Aktive Sperrtermine im 7-Tage-Fenster (Rot / Orange)"])
        for b in blockouts_week:
            lvl = "ROT (Verbindlich)" if b.get("sperr_level") == "rot" else "ORANGE (Vorbehalt)"
            md_lines.append(
                f"- `{b['start_date']}` bis `{b['end_date']}` · **{b['client_name']}** [{lvl}]: {b['title']} (Ort: {b['location']})"
            )

    md_lines.extend(["", "#### 3. Offene Zeitanfragen & DZR-Pruefung (Handlungsbedarf)"])
    for req in open_time_requests:
        conflict_tag = (
            f"ROT: {req['red_conflicts_count']} | ORANGE: {req['orange_conflicts_count']} | Reise-Warnung: {req['travel_warnings_count']}"
        )
        md_lines.append(
            f"- **{req['client_name']}** · *{req['project_title']}* ({req['sender_platform']}, Caster: {req['caster_name']}) · "
            f"DZR `{req['dzr_start']}` bis `{req['dzr_end']}` ({req['shooting_days']} DT) · Konflikte: [{conflict_tag}]"
        )

    md_lines.extend([
        "",
        "#### 4. Finanz- & Provisions-Snapshot (Zero-Error Integer Cents)",
        f"- **Bestaetigte Agenturprovision (Gesamt):** `{fin_summary['formatted']['confirmed_commission']}` (`{conf_c}` Cents)",
        f"- **Bereits bezahlte Provision:** `{fin_summary['formatted']['paid_commission']}` (`{paid_c}` Cents)",
        f"- **Offene Forderungen (Ausstehend):** `{fin_summary['formatted']['open_receivables']}` (`{open_c}` Cents)",
        f"- **Anstehende Klient:innen-Auszahlungen (Monatsende):** `{fin_summary['formatted']['pending_client_payout']}` (`{payout_c}` Cents)",
    ])

    return {
        "tenant_id": "zta-berlin",
        "reference_date": reference_date,
        "window_start": start_iso,
        "window_end": end_iso,
        "critical_deadlines_48h": critical_48h,
        "confirmed_production_schedule": production_schedule,
        "blockouts_in_window": blockouts_week,
        "open_time_requests": open_time_requests,
        "financial_snapshot": fin_summary,
        "markdown_report": "\n".join(md_lines),
    }


def build_news_triage_feed(
    state: Dict[str, Any],
    reference_date: str = "2026-11-14",
) -> Dict[str, Any]:
    """
    Playbook B ("Was sind Neuigkeiten / Notifications?") & GET /api/notifications + GET /api/news.
    Klassifiziert alle Ereignisse strikt in Level 1 (Red), Level 2 (Orange) und Level 3 (ZTA Blue).
    """
    cols = state["collections"]
    clients = cols.get("clients", {})
    notifications = cols.get("notifications", {})
    news = cols.get("news", {})
    inquiries = cols.get("inquiries", {})
    events = cols.get("calendar_events", {})

    level_1_red: List[Dict[str, Any]] = []
    level_2_orange: List[Dict[str, Any]] = []
    level_3_blue: List[Dict[str, Any]] = []

    # Pruefe rote Sperrtermine gegen offene DZR-Zeitanfragen
    for iid, idoc in inquiries.items():
        if idoc.get("status") not in ("open", "optioned"):
            continue
        cid = str(idoc.get("client_id") or "")
        cl_name = clients.get(cid, {}).get("name", cid)
        calc = calculate_sperrtermin_dzr(
            client_id=cid,
            dzr_start=str(idoc.get("dzr_start") or idoc.get("start_date") or reference_date),
            dzr_end=str(idoc.get("dzr_end") or idoc.get("end_date") or reference_date),
            sender_category=str(idoc.get("sender_platform") or "ZDF"),
            project_name=str(idoc.get("project_title") or ""),
            clients=clients,
            calendar_events=events,
            fee_matrix=cols.get("fee_matrix", {}),
            include_adjacent_days=True,
            reference_date=reference_date,
        )
        if calc["red_blockers"] or calc["adjacent_travel_warnings"]:
            level_1_red.append({
                "id": f"triage-red-{iid}",
                "priority_level": 1,
                "badge": "LEVEL 1 · ROT (SOFORT HANDELN)",
                "client_id": cid,
                "client_name": cl_name,
                "title": f"DZR-Kollision bei '{idoc.get('project_title', '')}' ({cl_name})",
                "message": (
                    f"{len(calc['red_blockers'])} verbindliche(r) roter Sperrtermin(e) und "
                    f"{len(calc['adjacent_travel_warnings'])} Anreise-/Nachbartag-Warnung(en) im DZR "
                    f"{calc['dzr_start']} bis {calc['dzr_end']}."
                ),
                "recommended_action": f"POST /api/availability/dzr-check fuer {cid} ausfuehren und Caster {idoc.get('caster_name', '')} mit Textbaustein informieren.",
            })
        elif calc["orange_blockers"]:
            level_2_orange.append({
                "id": f"triage-orange-{iid}",
                "priority_level": 2,
                "badge": "LEVEL 2 · ORANGE (FREIGABE / RUECKFRAGE)",
                "client_id": cid,
                "client_name": cl_name,
                "title": f"Oranger Sperrtermin im DZR '{idoc.get('project_title', '')}' ({cl_name})",
                "message": f"{len(calc['orange_blockers'])} weiche(r) Sperrtermin(e) unter Vorbehalt im Zeitraum {calc['dzr_start']} bis {calc['dzr_end']}.",
                "recommended_action": f"Ruecksprache mit {cl_name} halten, ob der Termin verschoben werden kann.",
            })

    # Notifications auswerten
    for nid, ndoc in sorted(notifications.items(), key=lambda x: str(x[1].get("created_at", "")), reverse=True):
        cid = str(ndoc.get("client_id") or "")
        cl_name = clients.get(cid, {}).get("name", cid)
        prio = int(ndoc.get("priority_level") or (2 if not ndoc.get("read") else 3))
        item = {
            "id": nid,
            "priority_level": prio,
            "client_id": cid,
            "client_name": cl_name,
            "title": f"System-Notification ({cl_name})",
            "message": ndoc.get("message", ""),
            "read": bool(ndoc.get("read", False)),
            "created_at": ndoc.get("created_at", ""),
            "recommended_action": f"POST /api/triage mit target_id='{nid}' und action='mark_read'",
        }
        if prio == 1:
            item["badge"] = "LEVEL 1 · ROT (SOFORT HANDELN)"
            level_1_red.append(item)
        elif prio == 2:
            item["badge"] = "LEVEL 2 · ORANGE (FREIGABE / RUECKFRAGE)"
            level_2_orange.append(item)
        else:
            item["badge"] = "LEVEL 3 · ZTA BLUE (INFO)"
            level_3_blue.append(item)

    # News auswerten
    for nwid, nwdoc in sorted(news.items(), key=lambda x: str(x[1].get("created_at", "")), reverse=True):
        cid = str(nwdoc.get("client_id") or "")
        cl_name = clients.get(cid, {}).get("name", cid)
        prio = int(nwdoc.get("priority_level") or 3)
        item = {
            "id": nwid,
            "priority_level": prio,
            "client_id": cid,
            "client_name": cl_name,
            "title": nwdoc.get("title", "Agentur-News"),
            "message": nwdoc.get("summary", ""),
            "created_at": nwdoc.get("created_at", ""),
            "recommended_action": nwdoc.get("action_endpoint", "GET /api/news"),
        }
        if prio == 1:
            item["badge"] = "LEVEL 1 · ROT (SOFORT HANDELN)"
            level_1_red.append(item)
        elif prio == 2:
            item["badge"] = "LEVEL 2 · ORANGE (FREIGABE / RUECKFRAGE)"
            level_2_orange.append(item)
        else:
            item["badge"] = "LEVEL 3 · ZTA BLUE (INFO)"
            level_3_blue.append(item)

    md_lines = [
        "### Executive Notification & News Triage",
        "",
        f"#### Level 1 · Immediate Action (Signal Red `#D92D20`) · {len(level_1_red)} Eintraege",
    ]
    for it in level_1_red:
        md_lines.append(f"- **{it['title']}**: {it['message']} -> *Aktion:* `{it['recommended_action']}`")
    if not level_1_red:
        md_lines.append("- Keine kritischen Level-1-Eskalationen.")

    md_lines.extend(["", f"#### Level 2 · Approval Pending (Signal Orange `#F59E0B`) · {len(level_2_orange)} Eintraege"])
    for it in level_2_orange:
        md_lines.append(f"- **{it['title']}**: {it['message']} -> *Aktion:* `{it['recommended_action']}`")

    md_lines.extend(["", f"#### Level 3 · Informational Updates (ZTA Blue `#0A1AE4`) · {len(level_3_blue)} Eintraege"])
    for it in level_3_blue:
        md_lines.append(f"- **{it['title']}**: {it['message']}")

    return {
        "tenant_id": "zta-berlin",
        "level_1_red": level_1_red,
        "level_2_orange": level_2_orange,
        "level_3_blue": level_3_blue,
        "total_unread_notifications": sum(1 for n in notifications.values() if not n.get("read")),
        "markdown_report": "\n".join(md_lines),
    }


def execute_auto_offset_workflow(
    collections: Dict[str, Dict[str, Any]],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Playbook D & POST /api/finance/auto-offset:
    Berechnet Vertrags-Finanzen exakt in Integer-Cents, prueft die gesetzliche VVV-Grenze (14% Cap),
    setzt den Vertrag auf 'final_signed', aktualisiert den Gagen-Spiegel (inkl. Auto-Raise der Richtgage)
    und synchronisiert den Drehtag in den Kalender.
    """
    clients = collections.setdefault("clients", {})
    contracts = collections.setdefault("contracts", {})
    inquiries = collections.setdefault("inquiries", {})
    events = collections.setdefault("calendar_events", {})
    fee_matrix = collections.setdefault("fee_matrix", {})

    contract_id = payload.get("contract_id")
    if contract_id and contract_id in contracts:
        cdoc = contracts[contract_id]
        client_id = str(cdoc.get("client_id") or payload.get("client_id") or "cl-01")
        division = str(cdoc.get("division") or clients.get(client_id, {}).get("division") or "schauspiel")
        gage_cents = int(payload.get("gage_cents") or cdoc.get("gage_cents") or 320000)
        buyout_cents = int(payload.get("buyout_cents") or cdoc.get("buyout_cents") or 0)
        engagement_days = int(payload.get("engagement_days") or cdoc.get("engagement_days") or 1)
        commission_rate_bp = int(payload.get("commission_rate_bp") or cdoc.get("commission_rate_bp") or 1000)
        vat_rate_bp = int(payload.get("vat_rate_bp") or cdoc.get("vat_rate_bp") or 1900)
        project_title = str(cdoc.get("project_title") or payload.get("project_title") or "Engagement")
    else:
        contract_id = str(payload.get("contract_id") or f"con-{uuid.uuid4().hex[:6]}")
        client_id = str(payload.get("client_id") or "cl-01")
        division = str(payload.get("division") or clients.get(client_id, {}).get("division") or "schauspiel")
        gage_cents = int(payload.get("gage_cents") or 320000)
        buyout_cents = int(payload.get("buyout_cents") or 0)
        engagement_days = int(payload.get("engagement_days") or 1)
        commission_rate_bp = int(payload.get("commission_rate_bp") or 1000)
        vat_rate_bp = int(payload.get("vat_rate_bp") or 1900)
        project_title = str(payload.get("project_title") or "Engagement")

    fin = calculate_contract_financials(
        division=division,
        gage_cents=gage_cents,
        buyout_cents=buyout_cents,
        commission_rate_bp=commission_rate_bp,
        engagement_days=engagement_days,
        vat_rate_bp=vat_rate_bp,
    )

    prev_version = int(contracts.get(contract_id, {}).get("version", 0))
    contract_doc = {
        "client_id": client_id,
        "inquiry_id": payload.get("inquiry_id") or contracts.get(contract_id, {}).get("inquiry_id"),
        "project_title": project_title,
        "production_company": str(payload.get("production_company") or contracts.get(contract_id, {}).get("production_company") or "Produktion"),
        "division": division,
        "status": "final_signed",
        "gage_cents": fin["gage_cents"],
        "buyout_cents": fin["buyout_cents"],
        "total_gross_cents": fin["total_gross_cents"],
        "commission_rate_bp": fin["commission_rate_bp"],
        "commission_cents": fin["commission_cents"],
        "agency_vat_cents": fin["agency_vat_cents"],
        "client_payout_cents": fin["client_payout_cents"],
        "paid_amount_cents": int(contracts.get(contract_id, {}).get("paid_amount_cents") or 0),
        "outstanding_cents": fin["total_gross_cents"] - int(contracts.get(contract_id, {}).get("paid_amount_cents") or 0),
        "engagement_days": fin["engagement_days"],
        "payout_month": str(payload.get("payout_month") or "2026-11"),
        "expected_payment_month": str(payload.get("expected_payment_month") or "2026-11"),
        "dropbox_contract_url": str(payload.get("dropbox_contract_url") or f"https://www.dropbox.com/scl/fi/{contract_id}/Vertrag_Final.pdf?dl=0"),
        "warning_code": fin["warning_code"],
        "legal_warning": fin["legal_warning"],
        "version": prev_version + 1,
        "tenant_id": "zta-berlin",
    }
    contracts[contract_id] = contract_doc

    # Falls eine Inquiry verknuepft ist, setze contract_dropbox_url (erzeugt Buchung in V10)
    inq_id = contract_doc.get("inquiry_id")
    if inq_id and inq_id in inquiries:
        inquiries[inq_id]["contract_dropbox_url"] = contract_doc["dropbox_contract_url"]
        inquiries[inq_id]["status"] = "confirmed"

    # Auto-Raise im Gagen-Spiegel pruefen (Feature 39)
    daily_achieved_cents = round_cents_decimal(Decimal(fin["gage_cents"]) / Decimal(max(1, fin["engagement_days"])))
    sender_cat = str(payload.get("sender_category") or "ZDF")
    updated_fee_entry = None
    for fid, fdoc in fee_matrix.items():
        if fdoc.get("client_id") == client_id and str(fdoc.get("category", "")).lower() == sender_cat.lower():
            fdoc["last_achieved_cents"] = daily_achieved_cents
            if daily_achieved_cents > int(fdoc.get("guideline_cents") or 0):
                fdoc["guideline_cents"] = daily_achieved_cents
                fdoc["guideline_ma_cents"] = round_cents_decimal(Decimal(daily_achieved_cents) * Decimal("1.10"))
            updated_fee_entry = dict(fdoc, id=fid)
            break

    # Kalender-Eintrag als bestaetigten Drehtag (ZTA Blue #0A1AE4) anlegen, falls Startdatum uebergeben
    shoot_date = str(payload.get("shoot_date") or "2026-11-24")
    ev_id = f"ev-auto-{contract_id}"
    events[ev_id] = {
        "client_id": client_id,
        "title": f"{project_title} (Drehtag gebucht)",
        "event_type": "dt",
        "category": "zta_event",
        "sub_type": "drehtag",
        "color_style": "blue_filled",
        "start_date": shoot_date,
        "end_date": str(payload.get("shoot_end_date") or shoot_date),
        "all_day": True,
        "location": str(payload.get("location") or "Berlin"),
        "status": "confirmed",
        "notes": f"Automatisch aus Auto-Offset Vertrag {contract_id} synchronisiert.",
        "tenant_id": "zta-berlin",
    }

    return {
        "contract_id": contract_id,
        "contract": contract_doc,
        "financials": fin,
        "updated_fee_entry": updated_fee_entry,
        "calendar_event_id": ev_id,
    }


def verify_access_login(
    collections: Dict[str, Dict[str, Any]],
    access_code: str,
) -> Dict[str, Any]:
    """
    Prueft einen persoenlichen Zugangscode (z. B. ZTA-ADMIN-2026 oder ZTA-CL01-2026)
    gegen die access_accounts Collection und erzwingt RBAC + Sperrstatus.
    """
    code_clean = str(access_code or "").strip().upper()
    accounts = collections.get("access_accounts", {})
    clients = collections.get("clients", {})

    for acc_id, acc in accounts.items():
        if str(acc.get("access_code") or "").strip().upper() == code_clean:
            if not acc.get("has_app_access", False) or acc.get("status") == "revoked":
                raise PermissionError(
                    f"Zugang gesperrt: Das Konto '{acc.get('display_name', acc_id)}' hat keinen aktiven App-Zugang (Regel 42 / Access Control)."
                )
            acc["last_login_at"] = utc_now_iso()
            cid = acc.get("client_id")
            client_doc = clients.get(cid) if cid else None
            return {
                "authenticated": True,
                "account_id": acc_id,
                "role": acc.get("role", "klient"),
                "ui_role": "team" if acc.get("role") in ("super_admin", "team_zta") else "klient",
                "is_locked_client_session": acc.get("role") == "klient",
                "client_id": cid,
                "display_name": acc.get("display_name", ""),
                "department": acc.get("department", ""),
                "scopes": acc.get("scopes", []),
                "bearer_token": acc.get("bearer_token", ""),
                "client_name": client_doc.get("name") if client_doc else None,
            }

    raise ValueError("Ungueltiger Zugangscode. Bitte pruefe den Code (z. B. ZTA-ADMIN-2026 oder ZTA-CL01-2026).")


def update_access_account(
    collections: Dict[str, Dict[str, Any]],
    account_id_or_client_id: str,
    has_app_access: Optional[bool] = None,
    role: Optional[str] = None,
    rotate_code: bool = False,
    actor: str = "Zetha (Super-Admin)",
) -> Dict[str, Any]:
    """
    Aktualisiert Zugangsrechte, Rolle oder Zugangscode in access_accounts UND synchronisiert
    clients[client_id]['has_app_access'] atomar.
    """
    accounts = collections.setdefault("access_accounts", {})
    clients = collections.setdefault("clients", {})
    audit_logs = collections.setdefault("audit_logs", {})

    target_acc_id = None
    if account_id_or_client_id in accounts:
        target_acc_id = account_id_or_client_id
    else:
        for aid, adoc in accounts.items():
            if adoc.get("client_id") == account_id_or_client_id:
                target_acc_id = aid
                break

    if not target_acc_id:
        raise ValueError(f"Konto oder Klient:in '{account_id_or_client_id}' nicht in access_accounts gefunden.")

    acc = accounts[target_acc_id]
    cid = acc.get("client_id")

    if has_app_access is not None:
        acc["has_app_access"] = bool(has_app_access)
        acc["status"] = "active" if has_app_access else "revoked"
        if cid and cid in clients:
            clients[cid]["has_app_access"] = bool(has_app_access)

    if role is not None:
        acc["role"] = role
        if role in ("super_admin", "team_zta"):
            acc["scopes"] = ["read:all", "write:all", "finance:execute"]
        else:
            acc["scopes"] = ["read:own_calendar", "write:own_blockouts", "read:own_guidelines"]

    if rotate_code:
        suffix = uuid.uuid4().hex[:4].upper()
        prefix = "ZTA-ADMIN" if acc.get("role") in ("super_admin", "team_zta") else f"ZTA-{str(cid or 'USER').upper().replace('-', '')}"
        new_code = f"{prefix}-{suffix}"
        acc["access_code"] = new_code
        if cid and cid in clients:
            clients[cid]["access_code"] = new_code

    acc["version"] = int(acc.get("version", 1)) + 1

    log_id = f"aud-acc-{uuid.uuid4().hex[:6]}"
    audit_logs[log_id] = {
        "timestamp": utc_now_iso(),
        "actor": actor,
        "action": "access_account.updated",
        "target_id": target_acc_id,
        "client_id": cid,
        "details": f"has_app_access={acc.get('has_app_access')}, role={acc.get('role')}, code={acc.get('access_code')}",
        "tenant_id": "zta-berlin",
    }

    return dict(acc, id=target_acc_id)


def run_copilot_playbook(
    playbook_id: str,
    params: Dict[str, Any],
    state: Dict[str, Any],
    confirm_gate: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fuehrt eines der 9 operativen ZTA-OS Executive Playbooks (A bis I) deterministisch aus.
    """
    cols = state["collections"]
    clients = cols.get("clients", {})
    events = cols.get("calendar_events", {})
    inquiries = cols.get("inquiries", {})
    castings = cols.get("castings", {})
    contracts = cols.get("contracts", {})
    fee_matrix = cols.get("fee_matrix", {})
    documents = cols.get("documents", {})
    reference_deals = cols.get("reference_deals", {})
    accounts = cols.get("access_accounts", {})
    ref_date = str(params.get("reference_date") or "2026-11-14")

    # PLAYBOOK A: Weekly Executive Briefing
    if playbook_id in ("A", "weekly_briefing"):
        feed = build_weekly_briefing_feed(state, reference_date=ref_date)
        return {
            "playbook_id": "weekly_briefing",
            "playbook_code": "Playbook A",
            "title": "Was steht diese Woche an? (Weekly Executive Briefing)",
            "data": feed,
            "markdown_report": feed["markdown_report"],
        }

    # PLAYBOOK B: Notification & News Triage
    if playbook_id in ("B", "news_triage"):
        triage = build_news_triage_feed(state, reference_date=ref_date)
        return {
            "playbook_id": "news_triage",
            "playbook_code": "Playbook B",
            "title": "Was sind Neuigkeiten / Notifications? (3-Stufen-Triage)",
            "data": triage,
            "markdown_report": triage["markdown_report"],
        }

    # PLAYBOOK C: Client Availability & Fee Verification
    if playbook_id in ("C", "dzr_fee_check"):
        query = str(params.get("client_id") or params.get("client_query") or "cl-01")
        cid, cdoc = resolve_client_fuzzy(clients, query)
        if not cid or not cdoc:
            raise ValueError(f"Klient:in '{query}' konnte nicht aufgeloest werden.")
        dzr_start = str(params.get("dzr_start") or "2026-11-18")
        dzr_end = str(params.get("dzr_end") or "2026-11-26")
        sender = str(params.get("sender_category") or "ZDF")
        project = str(params.get("project_name") or "Stuerme ueber Ruegen")

        calc = calculate_sperrtermin_dzr(
            client_id=cid,
            dzr_start=dzr_start,
            dzr_end=dzr_end,
            sender_category=sender,
            project_name=project,
            clients=clients,
            calendar_events=events,
            fee_matrix=fee_matrix,
            include_adjacent_days=True,
            reference_date=ref_date,
        )
        client_fees = [
            dict(f, id=fid)
            for fid, f in fee_matrix.items()
            if f.get("client_id") == cid
        ]
        md = [
            f"### Playbook C · DZR-Verfuegbarkeit & Gagen-Pruefung fuer **{cdoc.get('name')}**",
            f"- **Angefragter DZR:** `{dzr_start}` bis `{dzr_end}` · **Sender/Plattform:** `{sender}` · **Projekt:** *{project}*",
            f"- **Richtgage ({sender}):** `{calc['guideline_fee_formatted']}` (`{calc['guideline_fee_cents']}` Cents)",
            f"- **Rote Sperrtermine (Verbindlich):** `{len(calc['red_blockers'])}` | **Orange Sperrtermine (Vorbehalt):** `{len(calc['orange_blockers'])}` | **Reise-Warnungen (+/- 1 Tag):** `{len(calc['adjacent_travel_warnings'])}`",
            "",
            "#### Gagen-Spiegel (Team ZTA Intern)",
        ]
        for cf in client_fees:
            md.append(
                f"- **{cf.get('category')}** ({cf.get('unit', 'Tag')}, {cf.get('variant_default', 'MW')}): "
                f"Zuletzt erzielt `{format_eur_from_cents(int(cf.get('last_achieved_cents') or 0))}` | "
                f"Richtgage `{format_eur_from_cents(int(cf.get('guideline_cents') or 0))}` | "
                f"Ziel 2027 `{format_eur_from_cents(int(cf.get('target_next_year_cents') or 0))}`"
            )
        md.extend([
            "",
            "#### Kopierfertiger Antwort-Textbaustein fuer Caster:in",
            "```text",
            calc["copy_text_snippet"],
            "```",
        ])
        return {
            "playbook_id": "dzr_fee_check",
            "playbook_code": "Playbook C",
            "title": f"DZR & Gagen-Pruefung: {cdoc.get('name')}",
            "data": {"dzr_analysis": calc, "fee_entries": client_fees},
            "markdown_report": "\n".join(md),
        }

    # PLAYBOOK D: End-to-End Booking & Auto-Offset Execution (Mit Confirmation Gate!)
    if playbook_id in ("D", "booking_auto_offset"):
        query = str(params.get("client_id") or params.get("client_query") or "cl-01")
        cid, cdoc = resolve_client_fuzzy(clients, query)
        if not cid or not cdoc:
            cid, cdoc = "cl-01", clients.get("cl-01", {})
        gage_cents = int(params.get("gage_cents") or 340000)
        days = int(params.get("engagement_days") or 4)
        comm_bp = int(params.get("commission_rate_bp") or 1000)
        division = str(params.get("division") or cdoc.get("division") or "schauspiel")
        project_title = str(params.get("project_title") or "Stuerme ueber Ruegen (ZDF Primetime)")

        fin_preview = calculate_contract_financials(
            division=division,
            gage_cents=gage_cents,
            buyout_cents=int(params.get("buyout_cents") or 0),
            commission_rate_bp=comm_bp,
            engagement_days=days,
        )
        impact_str = (
            f"Brutto-Gesamt: {fin_preview['formatted']['total_gross']} ({fin_preview['total_gross_cents']} Cents) | "
            f"ZTA-Provision ({fin_preview['commission_rate_percent']:.1f}%): {fin_preview['formatted']['commission']} ({fin_preview['commission_cents']} Cents) | "
            f"Klient:innen-Auszahlung (Monatsende): {fin_preview['formatted']['client_payout']} ({fin_preview['client_payout_cents']} Cents)"
        )
        if fin_preview["warning_code"]:
            impact_str += f" | WARNUNG: {fin_preview['warning_code']}"

        if confirm_gate == "CANCEL":
            return {
                "playbook_id": "booking_auto_offset",
                "playbook_code": "Playbook D",
                "title": "End-to-End Booking & Auto-Offset (Abgebrochen)",
                "status": "cancelled",
                "markdown_report": "### Aktion abgebrochen (`CANCEL`)\nEs wurden keine Vertrags- oder Kalenderdaten veraendert.",
            }

        if confirm_gate != "CONFIRM":
            gate = build_confirmation_gate(
                operation="POST /api/finance/auto-offset & Contract Status -> final_signed",
                target_entity=f"{cdoc.get('name', cid)} · Projekt '{project_title}' ({days} Drehtage)",
                impact=impact_str,
                payload={
                    "client_id": cid,
                    "project_title": project_title,
                    "division": division,
                    "gage_cents": gage_cents,
                    "engagement_days": days,
                    "commission_rate_bp": comm_bp,
                },
            )
            md = [
                f"### Playbook D · Buchungs- & Auto-Offset-Vorschau fuer **{cdoc.get('name', cid)}**",
                "",
                "```text",
                gate["prompt"],
                "```",
                "",
                "#### Berechnete Cent-Buchungswerte (Zero-Error Integer Math)",
                f"- **Brutto-Gage:** `{fin_preview['formatted']['total_gross']}` (`{fin_preview['total_gross_cents']}` Cents)",
                f"- **Agenturprovision ({fin_preview['commission_rate_percent']:.1f} %):** `{fin_preview['formatted']['commission']}` (`{fin_preview['commission_cents']}` Cents)",
                f"- **USt. auf Provision (19 %):** `{format_eur_from_cents(fin_preview['agency_vat_cents'])}` (`{fin_preview['agency_vat_cents']}` Cents)",
                f"- **Netto-Auszahlung an {cdoc.get('name', cid)}:** `{fin_preview['formatted']['client_payout']}` (`{fin_preview['client_payout_cents']}` Cents)",
            ]
            if fin_preview["warning_code"]:
                md.append(f"- **Gesetzlicher Hinweis (`{fin_preview['warning_code']}`):** {fin_preview['legal_warning']}")
            return {
                "playbook_id": "booking_auto_offset",
                "playbook_code": "Playbook D",
                "title": "End-to-End Booking & Auto-Offset (Bestätigung erforderlich)",
                "confirmation_gate": gate,
                "data": fin_preview,
                "markdown_report": "\n".join(md),
            }

        # Bei CONFIRM: Ausfuehren!
        exec_res = execute_auto_offset_workflow(
            collections=cols,
            payload={
                "client_id": cid,
                "project_title": project_title,
                "division": division,
                "gage_cents": gage_cents,
                "engagement_days": days,
                "commission_rate_bp": comm_bp,
                "sender_category": params.get("sender_category", "ZDF"),
            },
        )
        md = [
            f"### Playbook D · Buchung & Auto-Offset erfolgreich ausgefuehrt (`CONFIRM`)",
            f"- **Vertrag-ID:** `{exec_res['contract_id']}` (Status: `final_signed`, Version: `{exec_res['contract']['version']}`)",
            f"- **Klient:in:** **{cdoc.get('name', cid)}** · Projekt: *{project_title}*",
            f"- **Brutto-Gage:** `{exec_res['financials']['formatted']['total_gross']}` | **ZTA-Provision:** `{exec_res['financials']['formatted']['commission']}` | **Auszahlung:** `{exec_res['financials']['formatted']['client_payout']}`",
            f"- **Kalender-Synchronisation:** Drehtag als ZTA Blue (`#0A1AE4`) unter ID `{exec_res['calendar_event_id']}` eingetragen.",
        ]
        return {
            "playbook_id": "booking_auto_offset",
            "playbook_code": "Playbook D",
            "title": "End-to-End Booking & Auto-Offset (Ausgefuehrt)",
            "mutated": True,
            "data": exec_res,
            "markdown_report": "\n".join(md),
        }

    # PLAYBOOK E: Stammblatt & Payroll Readiness Check (Steuerklasse 6 Schutz)
    if playbook_id in ("E", "payroll_readiness"):
        audit_rows: List[Dict[str, Any]] = []
        md = [
            "### Playbook E · Stammblatt & Payroll Readiness Check (Steuerklasse-6-Schutz)",
            "",
            "Prueft alle Klient:innen auf vollstaendige Abrechnungsdaten (P4: IBAN 22 Zeichen, BIC 8/11 Zeichen, 11-stellige Steuer-ID ohne USt-IdNr.-Verwechslung, 12-stellige SV-Nummer, P8: Steuerklasse, P9: Stammblatt-Signatur, P10: PKV-Bescheinigung, P11: Geburtsurkunde Kind).",
            "",
        ]
        for cid, cdoc in sorted(clients.items(), key=lambda x: str(x[1].get("name", ""))):
            issues = validate_client_master_data(cdoc)
            cl_docs = [d for d in documents.values() if d.get("client_id") == cid]
            missing_docs = [
                d.get("title", d.get("doc_type", "Dokument"))
                for d in cl_docs
                if d.get("status") != "vorhanden"
            ]
            ready = len(issues) == 0 and len(missing_docs) == 0
            audit_rows.append({
                "client_id": cid,
                "client_name": cdoc.get("name", cid),
                "department": cdoc.get("department", "actors"),
                "payroll_ready": ready,
                "field_issues": issues,
                "missing_documents": missing_docs,
            })
            if not ready:
                issue_str = "; ".join(i["message"] for i in issues) if issues else "Stammdaten-Felder formal OK"
                doc_str = ", ".join(missing_docs) if missing_docs else "Alle Pflichtdokumente vorhanden"
                md.append(f"- **⚠ {cdoc.get('name')} (`{cid}`)**: Felder: *{issue_str}* | Fehlende Dokumente: *{doc_str}*")
            else:
                md.append(f"- **✓ {cdoc.get('name')} (`{cid}`)**: 100 % Payroll-Ready (alle Felder & Dokumente geprueft).")

        return {
            "playbook_id": "payroll_readiness",
            "playbook_code": "Playbook E",
            "title": "Stammblatt & Payroll Readiness Check",
            "data": {"clients_audit": audit_rows},
            "markdown_report": "\n".join(md),
        }

    # PLAYBOOK F: 48h E-Casting & Recall Radar
    if playbook_id in ("F", "casting_radar_48h"):
        radar_items: List[Dict[str, Any]] = []
        for cid_cast, cdoc in castings.items():
            dl_str = str(cdoc.get("deadline_date") or "")
            if not dl_str:
                continue
            sched = compute_casting_schedule(dl_str, ref_date, str(cdoc.get("tape_status") or "open"))
            cl_name = clients.get(str(cdoc.get("client_id")), {}).get("name", cdoc.get("client_id"))
            radar_items.append({
                "id": cid_cast,
                "client_id": cdoc.get("client_id"),
                "client_name": cl_name,
                "project_title": cdoc.get("project_title", ""),
                "casting_type": cdoc.get("casting_type", "e_casting"),
                "caster_name": cdoc.get("casting_director", ""),
                "deadline_date": sched["deadline_date"],
                "internal_review_date": sched["internal_review_date"],
                "days_until_review": sched["days_until_review"],
                "days_until_deadline": sched["days_until_deadline"],
                "urgency": sched["urgency"],
                "countdown_label": sched["countdown_label"],
                "dropbox_tape_url": cdoc.get("dropbox_tape_url", ""),
            })
        radar_items.sort(key=lambda x: x["deadline_date"])
        md = [
            "### Playbook F · 48h E-Casting & Recall Radar (Interne ZTA-Sichtungsfrist = Deadline minus 2 Tage)",
            "",
        ]
        for r in radar_items:
            md.append(
                f"- **[{r['urgency'].upper()}] {r['client_name']}** · *{r['project_title']}* ({r['casting_type']}) · "
                f"Interne ZTA-Sichtung: `{r['internal_review_date']}` | Caster-Deadline: `{r['deadline_date']}` · {r['countdown_label']}"
            )
        return {
            "playbook_id": "casting_radar_48h",
            "playbook_code": "Playbook F",
            "title": "48h E-Casting & Recall Radar",
            "data": {"radar_items": radar_items},
            "markdown_report": "\n".join(md),
        }

    # PLAYBOOK G: Jahresgespraech & Gagen-Upgrade Dossier
    if playbook_id in ("G", "annual_review_dossier"):
        query = str(params.get("client_id") or params.get("client_query") or "cl-01")
        cid, cdoc = resolve_client_fuzzy(clients, query)
        if not cid or not cdoc:
            cid, cdoc = "cl-01", clients.get("cl-01", {})
        indicators = compute_industry_interest_indicators(cid, inquiries, castings, reference_date=ref_date)
        cl_fees = [dict(f, id=fid) for fid, f in fee_matrix.items() if f.get("client_id") == cid]
        dept = str(cdoc.get("department") or "actors")
        ref_deals = [dict(rd, id=rdid) for rdid, rd in reference_deals.items() if rd.get("department") == dept]

        tiles = indicators["tiles"]
        md = [
            f"### Playbook G · Jahresgespraech & Gagen-Upgrade Dossier fuer **{cdoc.get('name')}**",
            "",
            "#### 1. Branchen-Interesse-Indikatoren (`#F2D2C7` Executive KPIs)",
            f"- **Zeitanfragen:** `{tiles['zeitanfragen']}` | **E-Castings:** `{tiles['e_castings']}` | **Live-Castings:** `{tiles['live_castings']}` | **Buchungen (mit Vertrag):** `{tiles['buchungen']}`",
            "",
            "#### 2. Strategische Gespraechshinweise fuer Zetha",
        ]
        for h in indicators["conversation_hints"]:
            md.append(f"- {h}")
        md.extend(["", "#### 3. Gagen-Spiegel & Upgrade-Strategie 2027 (MW / MA & ZDF-Laengenformel)"])
        for f in cl_fees:
            zdf_tag = f" · ZDF-Modell: `{f.get('zdf_model')}`" if f.get("zdf_model") else ""
            md.append(
                f"- **{f.get('category')}** ({f.get('variant_default', 'MW')}{zdf_tag}): "
                f"Zuletzt erzielt `{format_eur_from_cents(int(f.get('last_achieved_cents') or 0))}` -> "
                f"Aktuelle Richtgage `{format_eur_from_cents(int(f.get('guideline_cents') or 0))}` (MA +10 %: `{format_eur_from_cents(int(f.get('guideline_ma_cents') or 0))}`) -> "
                f"**Empfohlenes Ziel 2027:** `{format_eur_from_cents(int(f.get('target_next_year_cents') or 0))}`"
            )
        if ref_deals:
            md.extend(["", "#### 4. Anonymisierte ZTA-Referenz-Deals zur Verhandlungsargumentation"])
            for rd in ref_deals:
                md.append(f"- **{rd.get('category')}** ({rd.get('role_or_scope')}): `{rd.get('fee_range_label')}` ({rd.get('year')}) · *{rd.get('notes', '')}*")

        return {
            "playbook_id": "annual_review_dossier",
            "playbook_code": "Playbook G",
            "title": f"Jahresgespraech & Gagen-Dossier: {cdoc.get('name')}",
            "data": {"indicators": indicators, "fees": cl_fees, "reference_deals": ref_deals},
            "markdown_report": "\n".join(md),
        }

    # PLAYBOOK H: Multi-Talent Besetzungs-Matcher (Freie Klient:innen im DZR)
    if playbook_id in ("H", "multi_talent_matcher"):
        dzr_start = str(params.get("dzr_start") or "2026-11-18")
        dzr_end = str(params.get("dzr_end") or "2026-11-26")
        dept = str(params.get("department") or "actors")
        sender = str(params.get("sender_category") or "ZDF")

        matches: List[Dict[str, Any]] = []
        for cid, cdoc in sorted(clients.items(), key=lambda x: str(x[1].get("name", ""))):
            if dept != "all" and cdoc.get("department") != dept:
                continue
            calc = calculate_sperrtermin_dzr(
                client_id=cid,
                dzr_start=dzr_start,
                dzr_end=dzr_end,
                sender_category=sender,
                project_name="Besetzungs-Pitch",
                clients=clients,
                calendar_events=events,
                fee_matrix=fee_matrix,
                include_adjacent_days=True,
                reference_date=ref_date,
            )
            if calc["red_blockers"]:
                avail_bucket = "blocked_red"
                avail_label = f"ROT BLOCKIERT ({len(calc['red_blockers'])} Sperrtermin)"
            elif calc["orange_blockers"]:
                avail_bucket = "option_orange"
                avail_label = f"ORANGE UNTER VORBEHALT ({len(calc['orange_blockers'])} Termin)"
            else:
                avail_bucket = "free_green"
                avail_label = "100 % FREI"

            matches.append({
                "client_id": cid,
                "client_name": cdoc.get("name", cid),
                "department": cdoc.get("department", "actors"),
                "location": cdoc.get("location", "Berlin"),
                "availability_bucket": avail_bucket,
                "availability_label": avail_label,
                "guideline_fee_cents": calc["guideline_fee_cents"],
                "guideline_fee_formatted": calc["guideline_fee_formatted"],
                "red_count": len(calc["red_blockers"]),
                "orange_count": len(calc["orange_blockers"]),
            })

        order_map = {"free_green": 0, "option_orange": 1, "blocked_red": 2}
        matches.sort(key=lambda x: (order_map.get(x["availability_bucket"], 9), x["client_name"]))

        md = [
            f"### Playbook H · Multi-Talent Besetzungs-Matcher (`{dzr_start}` bis `{dzr_end}` · Department: `{dept}` · Sender: `{sender}`)",
            "",
        ]
        for m in matches:
            md.append(
                f"- **[{m['availability_label']}] {m['client_name']}** ({m['location']}) · Richtgage {sender}: `{m['guideline_fee_formatted']}`"
            )
        return {
            "playbook_id": "multi_talent_matcher",
            "playbook_code": "Playbook H",
            "title": f"Multi-Talent Besetzungs-Matcher ({dzr_start} bis {dzr_end})",
            "data": {"matches": matches},
            "markdown_report": "\n".join(md),
        }

    # PLAYBOOK I: Zugangsrechte & Rollen-Governance (Access Control Manager)
    if playbook_id in ("I", "access_governance"):
        acc_list = [dict(a, id=aid) for aid, a in sorted(accounts.items(), key=lambda x: str(x[0]))]
        active_count = sum(1 for a in acc_list if a.get("has_app_access"))
        revoked_count = len(acc_list) - active_count
        md = [
            "### Playbook I · Zugangsrechte & Rollen-Governance (Access Control Matrix)",
            f"- **Gesamte Konten:** `{len(acc_list)}` | **Aktiv freigeschaltet:** `{active_count}` | **Kein App-Zugang (Consulting / PR-Projekt / Gesperrt):** `{revoked_count}`",
            "",
            "| Konto-ID | Name | Rolle | Department | Portal-Status | Persoenlicher Login-Code |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for a in acc_list:
            status_badge = "✓ AKTIV" if a.get("has_app_access") else "✗ GESPERRT (403)"
            md.append(
                f"| `{a['id']}` | **{a.get('display_name', '')}** | `{a.get('role', '')}` | `{a.get('department', '')}` | {status_badge} | `{a.get('access_code', '')}` |"
            )
        return {
            "playbook_id": "access_governance",
            "playbook_code": "Playbook I",
            "title": "Zugangsrechte & Rollen-Governance (Access Control Matrix)",
            "data": {"accounts": acc_list, "active_count": active_count, "revoked_count": revoked_count},
            "markdown_report": "\n".join(md),
        }

    raise ValueError(f"Unbekanntes Playbook '{playbook_id}'. Unterstuetzt werden A bis I.")


def get_copilot_master_system_prompt() -> str:
    """
    Liefert den offiziellen ZTA-OS Executive AI Co-Pilot System-Prompt fuer Claude Desktop / Projekte / API.
    """
    return (
        "# ZTA-OS EXECUTIVE AI CO-PILOT MASTER SYSTEM PROMPT (V10.2)\n"
        "Du bist der Executive AI Co-Pilot fuer ZTA Management Berlin (Inhaberin: Zetha).\n"
        "Du greifst direkt auf die ZTA-OS REST-API (Tenant: 'zta-berlin') oder den ZTA-OS MCP-Server zu.\n\n"
        "## STRIKTE GOVERNANCE-REGELN\n"
        "1. Zero-Error Monetary Math: Alle Geldbetraege werden in ganzen Euro-Cents (Integer) verarbeitet (z. B. 3.200,00 EUR = 320000).\n"
        "2. Multi-Tenancy Isolation: Sende bei jedem Aufruf den Header 'X-Tenant-ID: zta-berlin' oder 'tenant_id: zta-berlin'.\n"
        "3. Statutory Commission Cap (VVV): Ueberschreitet die Provision bei Schauspiel/Regie/NXT 14 % (1400 bp, bis 7 Drehtage) bzw. 18 % (ab 8 Tagen), weise explizit auf 'WARNING_COMMISSION_CAP_EXCEEDED' hin.\n"
        "4. Destructive Action Confirmation Gate: Vor jedem DELETE, Vertragsabschluss ('final_signed' / '/api/finance/auto-offset') oder Zugangs-Entzug ('/api/access/update') gib zwingend den Bestaetigungsblock '⚠ Action Confirmation Required' aus und warte auf 'CONFIRM'.\n"
        "5. Keine Gedankenstriche in deutschen Texten oder Antwortbausteinen verwenden.\n\n"
        "## VERFUEGBARE PLAYBOOKS (A BIS I UEBER POST /api/copilot/playbook)\n"
        "- Playbook A ('weekly_briefing'): Was steht diese Woche an? (48h Castings, Drehtage, offene Zeitanfragen, Liquiditaets-KPIs)\n"
        "- Playbook B ('news_triage'): Was sind Neuigkeiten / Notifications? (Level 1 Rot, Level 2 Orange, Level 3 ZTA Blue)\n"
        "- Playbook C ('dzr_fee_check'): Ist Klient:in im DZR frei + Gagen-Spiegel + Caster-Textbaustein\n"
        "- Playbook D ('booking_auto_offset'): End-to-End Buchung & Auto-Offset mit Confirmation Gate\n"
        "- Playbook E ('payroll_readiness'): Stammblatt & Payroll Readiness Check (Steuerklasse-6-Schutz)\n"
        "- Playbook F ('casting_radar_48h'): 48h E-Casting & Recall Radar (Deadline minus 2 Tage interne Sichtung)\n"
        "- Playbook G ('annual_review_dossier'): Jahresgespraech & Gagen-Upgrade Dossier 2027\n"
        "- Playbook H ('multi_talent_matcher'): Multi-Talent Besetzungs-Matcher (Wer ist frei im DZR?)\n"
        "- Playbook I ('access_governance'): Zugangsrechte & Rollen-Governance (Access Control Matrix fuer alle Accounts)\n"
    )
