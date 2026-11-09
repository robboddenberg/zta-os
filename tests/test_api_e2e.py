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
