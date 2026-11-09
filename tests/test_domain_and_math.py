"""Unit-Tests fuer Zero-Error Cent-Mathematik, Konflikt-Engine, Auto-Offset und Parser (Prinzip 3, 4, 5)."""
from __future__ import annotations

import pytest

from backend.app.logic import (
    apply_contract_status_with_auto_offset,
    apply_inquiry_decision,
    build_effort_vs_commission_report,
    build_liquidity_timeline,
    calculate_contract_financials,
    check_client_availability,
    compute_casting_schedule,
    find_free_clients,
    format_eur_from_cents,
    generate_inquiry_reply,
    parse_eur_to_cents,
    parse_import_payload,
)


def test_zero_error_cent_calculations_and_legal_caps() -> None:
    # 1. Standard Schauspiel (12 % = 1200 bp, 5 Tage <= 7 Tage -> Cap 14 %)
    res = calculate_contract_financials(
        division="schauspiel",
        gage_cents=185000,
        buyout_cents=15000,
        commission_rate_bp=1200,
        engagement_days=5,
    )
    assert res["total_gross_cents"] == 200000
    assert res["commission_cents"] == 24000
    assert res["agency_vat_cents"] == 4560
    assert res["client_payout_cents"] == 176000
    assert res["exceeds_legal_cap"] is False

    # 2. Gesetzliche Obergrenze ueberschritten (16 % bei 4 Tagen Schauspiel -> Cap ist 14 %)
    warn_res = calculate_contract_financials(
        division="schauspiel",
        gage_cents=100000,
        buyout_cents=0,
        commission_rate_bp=1600,
        engagement_days=4,
    )
    assert warn_res["exceeds_legal_cap"] is True
    assert warn_res["legal_cap_bp"] == 1400
    assert "Vermittler-Verguetungsverordnung" in warn_res["legal_warning"]

    # 3. PR & Commercial (25 % = 2500 bp erlaubt ohne Warnung)
    pr_res = calculate_contract_financials(
        division="pr_commercial",
        gage_cents=400000,
        buyout_cents=600000,
        commission_rate_bp=2500,
        engagement_days=2,
    )
    assert pr_res["total_gross_cents"] == 1000000
    assert pr_res["commission_cents"] == 250000
    assert pr_res["client_payout_cents"] == 750000
    assert pr_res["exceeds_legal_cap"] is False

    # 4. Grenzfall 0 Cent und ungerade Cent-Rundung (ROUND_HALF_UP)
    zero_res = calculate_contract_financials("nxt", gage_cents=0, buyout_cents=0, commission_rate_bp=1000)
    assert zero_res["commission_cents"] == 0
    assert zero_res["client_payout_cents"] == 0

    odd_res = calculate_contract_financials("schauspiel", gage_cents=33333, buyout_cents=0, commission_rate_bp=1250)
    # 33333 * 0.125 = 4166.625 -> 4167 Cent
    assert odd_res["commission_cents"] == 4167
    assert odd_res["client_payout_cents"] == 33333 - 4167


def test_parse_and_format_eur_cents() -> None:
    assert parse_eur_to_cents("1.850,50 EUR") == 185050
    assert parse_eur_to_cents("2400") == 240000
    assert parse_eur_to_cents(12500) == 12500
    assert format_eur_from_cents(185050) == "1.850,50 EUR"


def test_availability_and_conflict_engine() -> None:
    events = {
        "ev-1": {
            "client_id": "cl-01",
            "event_type": "option",
            "title": "Tatort (1. Option)",
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "all_day": True,
            "option_rank": 1,
            "status": "tentative",
        },
        "ev-2": {
            "client_id": "cl-01",
            "event_type": "sperr",
            "title": "Theaterabend",
            "start_date": "2026-11-15",
            "end_date": "2026-11-15",
            "all_day": True,
            "status": "confirmed",
        },
    }

    avail_opt = check_client_availability("cl-01", "2026-11-10", "2026-11-12", events)
    assert avail_opt["overall_status"] == "option"
    assert avail_opt["recommended_option_rank"] == 2

    avail_part = check_client_availability("cl-01", "2026-11-14", "2026-11-16", events)
    assert avail_part["overall_status"] == "teilweise"
    assert avail_part["free_days_count"] == 2
    assert avail_part["blocked_days_count"] == 1

    # Antwortvorlage darf keine Gedankenstriche enthalten
    reply = generate_inquiry_reply(
        client={"name": "Mara Lindqvist", "commission_rate_bp": 1200},
        inquiry={
            "project_title": "Nordwind",
            "production_company": "UFA",
            "contact_person": "Katja",
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "requested_shooting_days": 2,
            "offered_gage_cents": 370000,
        },
        availability=avail_opt,
    )
    assert "2. Option" in reply
    assert "\u2013" not in reply
    assert "\u2014" not in reply


def test_casting_2_day_internal_review_schedule() -> None:
    sched = compute_casting_schedule("2026-11-15", reference_date="2026-11-09", tape_status="open")
    assert sched["internal_review_date"] == "2026-11-13"
    assert sched["days_until_deadline"] == 6
    assert sched["days_until_review"] == 4


def test_auto_offset_inquiry_and_contract_settlement() -> None:
    collections = {
        "clients": {
            "cl-01": {"name": "Mara Lindqvist", "division": "schauspiel", "commission_rate_bp": 1200}
        },
        "calendar_events": {},
        "inquiries": {
            "inq-01": {
                "client_id": "cl-01",
                "project_title": "Spreewaldkrimi",
                "production_company": "Aspekt Telefilm",
                "start_date": "2026-11-20",
                "end_date": "2026-11-23",
                "requested_shooting_days": 3,
                "offered_gage_cents": 600000,
                "status": "open",
            }
        },
        "contracts": {},
    }

    decision_res = apply_inquiry_decision(
        collections=collections,
        inquiry_id="inq-01",
        decision="option",
        option_rank=1,
        create_contract_draft=True,
    )
    assert decision_res["new_status"] == "optioned"
    ev_id = decision_res["created_event_id"]
    con_id = decision_res["created_contract_id"]
    assert ev_id in collections["calendar_events"]
    assert con_id in collections["contracts"]
    assert collections["contracts"][con_id]["commission_cents"] == 72000
    assert collections["contracts"][con_id]["outstanding_cents"] == 72000

    # Jetzt Auto-Offset Zahlungseingang verbuchen
    offset_res = apply_contract_status_with_auto_offset(
        collections=collections,
        contract_id=con_id,
        new_status="paid",
    )
    assert offset_res["outstanding_cents"] == 0
    assert offset_res["client_payout_status"] == "freigegeben_zum_monatsende"


def test_fault_tolerant_csv_parser() -> None:
    raw_csv = "\n".join(
        [
            "client_id,event_type,title,start_date,end_date",
            "cl-01,sperr,Urlaub,2026-12-01,2026-12-05",
            ",sperr,Fehlende Client ID,2026-12-01,2026-12-02",
            "cl-02,option,Ungueltiges Datum,kein-datum,2026-12-02",
        ]
    )
    valid, warnings = parse_import_payload("csv", "calendar_events", raw_csv)
    assert len(valid) == 1
    assert len(warnings) == 2
