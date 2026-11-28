"""End-to-End API Tests fuer ZTA OS."""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.config import AppConfig
from backend.app.main import create_app
from backend.app.storage import StorageEngine
from scripts.build_initial_data import build_synthetic_dataset


def _make_test_client(tmp_path: Path) -> TestClient:
    data_path = tmp_path / "data.json"
    cfg = AppConfig(
        app_name="ZTA OS Test",
        app_version="1.0.0",
        root_dir=Path(__file__).resolve().parents[1],
        data_path=data_path,
        frontend_dir=Path(__file__).resolve().parents[1] / "frontend",
        port=8010,
        default_tenant_id="zta-berlin",
        webhook_secret="test-secret",
        gemini_api_key="",
        gemini_model="gemini-2.5-flash",
    )
    storage = StorageEngine(data_path)
    storage.write_new_state(build_synthetic_dataset())
    app = create_app(cfg)
    return TestClient(app)


def test_health_and_initial_20_synthetic_profiles(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)

    h = client.get("/api/health")
    assert h.status_code == 200
    h_json = h.json()
    assert h_json["status"] == "ok"
    assert h_json["has_data"] is True

    st = client.get("/api/state")
    assert st.status_code == 200
    st_json = st.json()
    assert len(st_json["collections"]["clients"]) == 20
    assert "liquidity" in st_json["computed"]
    assert "effort_vs_commission" in st_json["computed"]


def test_availability_matrix_and_free_clients_api(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)

    grid = client.get("/api/availability/month-grid?year=2026&month=11&division=schauspiel")
    assert grid.status_code == 200
    grid_data = grid.json()
    assert len(grid_data["rows"]) == 10
    assert len(grid_data["days"]) == 30

    free_resp = client.post(
        "/api/availability/free-clients",
        json={"start_date": "2026-11-16", "end_date": "2026-11-20", "division": "all", "include_options": True},
    )
    assert free_resp.status_code == 200
    assert len(free_resp.json()["results"]) == 20


def test_inquiry_decision_and_auto_offset_flow(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)

    # 1. Antwortvorlage abrufen
    tpl = client.get("/api/inquiries/inq-01/reply-template")
    assert tpl.status_code == 200
    assert "ZTA Management Berlin" in tpl.json()["reply_template"]

    # 2. Anfrage als Option buchen + Vertragsentwurf erzeugen
    dec = client.post(
        "/api/inquiries/decision",
        json={"inquiry_id": "inq-01", "decision": "option", "option_rank": 1, "create_contract_draft": True},
    )
    assert dec.status_code == 200
    outcome = dec.json()["outcome"]
    assert outcome["new_status"] == "optioned"
    con_id = outcome["created_contract_id"]
    assert con_id is not None

    # 3. Vertrag auf 'paid' setzen und Auto-Offset pruefen
    paid = client.post(
        "/api/contracts/status",
        json={"contract_id": con_id, "new_status": "paid"},
    )
    assert paid.status_code == 200
    assert paid.json()["outcome"]["outstanding_cents"] == 0
    assert paid.json()["outcome"]["client_payout_status"] == "freigegeben_zum_monatsende"


def test_mobile_portal_blocker_conflict_detection_and_response(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)

    # cl-01 hat am 2026-11-10 bis 2026-11-12 bereits Tatort Drehtage -> muss Konfliktwarnung liefern
    blk = client.post(
        "/api/portal/blocker",
        json={
            "client_id": "cl-01",
            "start_date": "2026-11-11",
            "end_date": "2026-11-12",
            "title": "Privater Termin",
            "all_day": True,
        },
    )
    assert blk.status_code == 200
    blk_data = blk.json()
    assert blk_data["has_conflict"] is True
    assert len(blk_data["conflict_warnings"]) >= 1

    # Klienten-Antwort auf Anfrage senden
    resp = client.post(
        "/api/portal/respond",
        json={
            "client_id": "cl-01",
            "target_type": "inquiry",
            "target_id": "inq-01",
            "response": "fits",
            "comment": "Passt super!",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["client_response"] == "fits"


def test_webhook_ingest_ical_feedback_and_pwa_routes(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)

    # n8n Webhook Ingest
    wh = client.post(
        "/api/webhooks/ingest",
        headers={"X-Webhook-Secret": "test-secret"},
        json={
            "event_type": "inquiry.received",
            "source": "n8n",
            "payload": {
                "client_id": "cl-02",
                "project_title": "n8n Test-Serie",
                "start_date": "2026-12-01",
                "end_date": "2026-12-04",
                "offered_gage_eur": "4.500,00 EUR",
            },
        },
    )
    assert wh.status_code == 200
    assert wh.json()["status"] == "processed"

    # iCal Feed
    ics = client.get("/api/ical/cl-01.ics?token=tok-cl-01-zta2026")
    assert ics.status_code == 200
    assert "BEGIN:VCALENDAR" in ics.text

    # In-App Feedback Melden
    fb = client.post(
        "/api/feedback/report",
        json={
            "title": "Test-Wunsch aus E2E",
            "description": "Schnelltest",
            "category": "wunsch",
            "reported_by_role": "inhaberin",
            "reported_by_name": "Zetha",
            "view_context": "cockpit",
        },
    )
    assert fb.status_code == 200
    assert fb.json()["feedback_id"].startswith("FB-")

    # PWA Frontend & Backup Export
    idx = client.get("/")
    assert idx.status_code == 200
    assert "ZTA OS Berlin" in idx.text

    bak = client.get("/api/backup/export")
    assert bak.status_code == 200
    assert "collections" in bak.text


def test_v10_endpoints_sperrtermin_pipeline_fees_and_strict_client_rbac(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)

    # 1. Roter Sperrtermin ohne Ort -> 400 Bad Request
    bad_sperr = client.post(
        "/api/v10/sperrtermin",
        json={
            "client_id": "cl-01",
            "title": "Unvollstaendiger Termin",
            "start_date": "2026-11-18",
            "end_date": "2026-11-19",
            "level": "rot",
            "location": "",
            "created_by_role": "klient",
        },
    )
    assert bad_sperr.status_code == 400

    # 2. Roter Sperrtermin mit Ort -> 200 OK
    ok_sperr = client.post(
        "/api/v10/sperrtermin",
        json={
            "client_id": "cl-01",
            "title": "Gastspiel Burgtheater",
            "start_date": "2026-11-18",
            "end_date": "2026-11-19",
            "level": "rot",
            "location": "Wien",
            "created_by_role": "klient",
        },
    )
    assert ok_sperr.status_code == 200
    assert ok_sperr.json()["event"]["location"] == "Wien"

    # 3. Sperrtermin-Rechner liefert #F2D2C7 DZR und kopierbaren Textbaustein
    calc_res = client.post(
        "/api/v10/sperrtermin-rechner",
        json={
            "client_id": "cl-01",
            "dzr_start": "2026-11-15",
            "dzr_end": "2026-11-25",
            "project_name": "Tatort Berlin",
            "sender_category": "ARD/Degeto",
        },
    )
    assert calc_res.status_code == 200
    assert calc_res.json()["highlight_color"] == "#F2D2C7"
    assert "Wien" in calc_res.json()["copyable_reply_text"]

    # 4. Casting-Pipeline mit Dropbox-Vertragslink setzt Status auf Gebucht
    pipe_res = client.post(
        "/api/v10/pipeline",
        json={
            "inquiry_id": "inq-01",
            "pipeline_stage": "live_casting",
            "e_casting_deadline": "2026-11-12",
            "live_casting_date": "2026-11-16",
            "contract_dropbox_url": "https://www.dropbox.com/scl/fi/vertrag_mara.pdf",
        },
    )
    assert pipe_res.status_code == 200
    assert pipe_res.json()["inquiry"]["derived_status"] == "gebucht"

    # 5. Gagen-Spiegel Auto-Upgrade bei hoeherem Abschluss
    fee_res = client.post(
        "/api/v10/fees",
        json={
            "client_id": "cl-01",
            "category": "Streamer",
            "last_achieved_eur": "5.200,00 EUR",
            "guideline_eur": "4.500,00 EUR",
            "settlement_model": "MA",
            "status": "fest",
        },
    )
    assert fee_res.status_code == 200
    assert fee_res.json()["entry"]["guideline_cents"] == 520000
    assert fee_res.json()["entry"]["guideline_auto_upgraded"] is True

    # 6. Branchen-Interesse-Indikatoren (4 Kacheln auf #F2D2C7)
    ind_res = client.get("/api/v10/indicators/cl-01")
    assert ind_res.status_code == 200
    assert "kpi_tiles_pink" in ind_res.json()

    # 7. Strikte Negative Constraints fuer Rolle Klient:in
    rbac_res = client.get("/api/v10/client-view/cl-01")
    assert rbac_res.status_code == 200
    rbac_data = rbac_res.json()
    assert rbac_data["role"] == "klient"
    assert "reference_deals" not in rbac_data
    assert "industry_indicators" not in rbac_data
    for fg in rbac_data["my_fee_guidelines"]:
        assert "guideline_cents" in fg
        assert "last_achieved_cents" not in fg

    # Consulting-Klient:innen haben keinen App-Zugang (Feature 42)
    cons_res = client.get("/api/v10/client-view/cl-19")
    assert cons_res.status_code == 403



def test_v10_2_team_tasks_and_multi_talent_dzr(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)
    reset_res = client.post("/api/v10/reset")
    assert reset_res.status_code == 200

    # 1. WhatsApp-Schnelleingabe mit Auto-Parsing (Sarah + #dringend + Mara Lindqvist)
    create_res = client.post(
        "/api/v10/team-tasks",
        json={
            "raw_input": "Sarah: Bitte ZDF Vertrag fuer Mara Lindqvist pruefen! #dringend",
            "created_by": "zetha",
        },
    )
    assert create_res.status_code == 200
    created_task = create_res.json()["task"]
    assert created_task["assignee"] == "sarah"
    assert created_task["priority"] == "p1_urgent"
    assert created_task["client_id"] == "cl-01"
    assert created_task["push_active"] is True
    task_id = created_task["id"]

    # 2. Prio-sortierte Liste fuer Sarah abrufen
    list_res = client.get("/api/v10/team-tasks?assignee=sarah")
    assert list_res.status_code == 200
    tasks = list_res.json()["tasks"]
    assert len(tasks) >= 2
    assert tasks[0]["priority"] == "p1_urgent"

    # 3. Push-Reminder ausloesen (erhoeht reminder_count)
    ping_res = client.post(
        "/api/v10/team-tasks/ping",
        json={"task_id": task_id, "triggered_by": "zetha"},
    )
    assert ping_res.status_code == 200
    assert ping_res.json()["task"]["reminder_count"] == 2
    assert "deep_link" in ping_res.json()

    # 4. Abhaken stoppt push_active
    toggle_res = client.post(
        "/api/v10/team-tasks/toggle",
        json={"task_id": task_id, "completed_by": "sarah"},
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["task"]["completed"] is True
    assert toggle_res.json()["task"]["push_active"] is False

    # 5. Strict Negative Constraint: Rolle Klient:in sieht keine Team-Aufgaben
    rbac_res = client.get("/api/v10/client-view/cl-01")
    assert rbac_res.status_code == 200
    assert "team_tasks" not in rbac_res.json()

    # 6. FK 1: Multi-Talent Verfuegbarkeits-Check im Department 'actors'
    multi_res = client.post(
        "/api/v10/sperrtermin-rechner/multi",
        json={
            "dzr_start": "2026-11-18",
            "dzr_end": "2026-11-26",
            "department": "actors",
            "sender_category": "ZDF",
            "project_name": "Krimi Berlin",
        },
    )
    assert multi_res.status_code == 200
    multi_data = multi_res.json()
    assert multi_data["total_checked"] == 10
    assert "free_green" in multi_data
    assert "copyable_reply_text" in multi_data


def test_v10_3_security_auth_and_idor_guards(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)

    # 1. iCal Token darf ohne oder mit falschem Token niemals ausgeliefert werden
    assert client.get("/api/ical/cl-01.ics").status_code == 403
    assert client.get("/api/ical/cl-01.ics?token=falsch").status_code == 403
    ok_ics = client.get("/api/ical/cl-01.ics?token=tok-cl-01-zta2026")
    assert ok_ics.status_code == 200
    assert "PRODID:-//ZTA Management Berlin//ZTA OS v10.3//DE" in ok_ics.text

    # 2. Webhook Secret darf ohne Header nicht umgangen werden
    wh_payload = {"event_type": "calendar.blocker", "source": "n8n", "payload": {"client_id": "cl-01"}}
    assert client.post("/api/webhooks/ingest", json=wh_payload).status_code == 403
    assert client.post("/api/webhooks/ingest", headers={"X-Webhook-Secret": "wrong"}, json=wh_payload).status_code == 403
    assert client.post("/api/webhooks/ingest", headers={"X-Webhook-Secret": "test-secret"}, json=wh_payload).status_code == 200

    # 3. IDOR-Schutz in /api/portal/respond (inq-01 gehoert cl-01, nicht cl-02)
    idor_res = client.post(
        "/api/portal/respond",
        json={
            "client_id": "cl-02",
            "target_type": "inquiry",
            "target_id": "inq-01",
            "response": "fits",
            "comment": "Fremdzugriff",
        },
    )
    assert idor_res.status_code == 403

    # 4. Roter Portal-Sperrtermin ohne Ort liefert 400 (kein 500 KeyError)
    bad_blk = client.post(
        "/api/portal/blocker",
        json={
            "client_id": "cl-01",
            "start_date": "2026-11-22",
            "end_date": "2026-11-23",
            "level": "rot",
            "location": "",
        },
    )
    assert bad_blk.status_code == 400

    # 5. javascript: URLs im Dropbox-Link werden abgewiesen
    xss_pipe = client.post(
        "/api/v10/pipeline",
        json={"inquiry_id": "inq-01", "contract_dropbox_url": "javascript:alert(1)"},
    )
    assert xss_pipe.status_code == 400

    # 6. Ungueltiger Euro-Betrag liefert 400, deutscher Tausenderpunkt "1.850 EUR" -> 185000 Cent
    bad_fee = client.post(
        "/api/v10/fees",
        json={"client_id": "cl-01", "category": "ZDF", "last_achieved_eur": "auf Anfrage"},
    )
    assert bad_fee.status_code == 400

    good_fee = client.post(
        "/api/v10/fees",
        json={"client_id": "cl-01", "category": "ZDF", "last_achieved_eur": "1.850 EUR", "guideline_eur": "1.850 EUR"},
    )
    assert good_fee.status_code == 200
    assert good_fee.json()["entry"]["last_achieved_cents"] == 185000


def test_v10_3_calendar_event_and_team_tasks_edit_delete_and_409(tmp_path: Path) -> None:
    client = _make_test_client(tmp_path)
    rev = client.get("/api/state").json()["meta"]["revision"]

    # 1. ZTA-Termin anlegen via POST /api/calendar/event + 409 Schutz
    stale_ev = client.post(
        "/api/calendar/event",
        json={
            "client_id": "cl-01",
            "title": "Stale Termin",
            "start_date": "2026-11-24",
            "end_date": "2026-11-24",
            "if_revision": rev - 1,
        },
    )
    assert stale_ev.status_code == 409

    ok_ev = client.post(
        "/api/calendar/event",
        json={
            "client_id": "cl-01",
            "title": "Reisetag nach Wien",
            "start_date": "2026-11-24",
            "end_date": "2026-11-24",
            "location": "Wien",
            "if_revision": rev,
        },
    )
    assert ok_ev.status_code == 200
    ev_id = ok_ev.json()["event_id"]
    rev = ok_ev.json()["state"]["meta"]["revision"]
    assert ev_id in ok_ev.json()["state"]["collections"]["calendar_events"]

    # 2. Team-Aufgabe anlegen, bearbeiten, 409 pruefen und loeschen
    created = client.post(
        "/api/v10/team-tasks",
        json={"raw_input": "Sarah: Audio mp3 senden!", "if_revision": rev},
    )
    assert created.status_code == 200
    task = created.json()["task"]
    assert task["priority"] == "p2_important"
    task_id = task["id"]
    rev = created.json()["state"]["meta"]["revision"]

    # Stale Update -> 409
    assert client.post(
        "/api/v10/team-tasks/update",
        json={"task_id": task_id, "title": "Neu", "if_revision": rev - 1},
    ).status_code == 409

    # Gueltiges Update -> 200
    upd = client.post(
        "/api/v10/team-tasks/update",
        json={
            "task_id": task_id,
            "title": "ZDF Vertrag freigeben",
            "assignee": "elias",
            "priority": "p1_urgent",
            "due_date": "2026-12-01",
            "if_revision": rev,
        },
    )
    assert upd.status_code == 200
    assert upd.json()["task"]["assignee"] == "elias"
    assert upd.json()["task"]["priority"] == "p1_urgent"
    rev = upd.json()["state"]["meta"]["revision"]

    # Stale Delete -> 409, dann gueltiges Delete -> 200, danach 404
    assert client.delete(f"/api/v10/team-tasks/{task_id}?if_revision={rev - 1}").status_code == 409
    del_res = client.delete(f"/api/v10/team-tasks/{task_id}?if_revision={rev}")
    assert del_res.status_code == 200
    assert task_id not in del_res.json()["state"]["collections"]["team_tasks"]
    assert client.delete(f"/api/v10/team-tasks/{task_id}").status_code == 404
