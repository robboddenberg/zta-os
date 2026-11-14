"""FastAPI Hauptanwendung fuer ZTA OS (Stand V10 Master-Prompt & 50 Features)."""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from .ai import run_ai_assist
from .config import AppConfig, load_config
from .logic import (
    ZDF_GVR_MODELS,
    apply_contract_status_with_auto_offset,
    apply_inquiry_decision,
    build_client_rbac_view,
    build_effort_vs_commission_report,
    build_liquidity_timeline,
    build_month_grid,
    calculate_contract_financials,
    check_client_availability,
    compute_casting_schedule,
    compute_industry_interest_indicators,
    compute_sperrtermin_rechner,
    evaluate_inquiry_v10,
    find_free_clients,
    generate_client_ical,
    generate_inquiry_reply,
    parse_eur_to_cents,
    parse_import_payload,
    upsert_fee_entry_v10,
    validate_master_data_plausibility,
    validate_sperrtermin_v10,
)
from .models import (
    AiAssistRequest,
    ClientFilterQuery,
    ClientPortalBlockerRequest,
    ClientPortalResponseRequest,
    ContractCalculateRequest,
    ContractStatusUpdateRequest,
    CsvOrJsonImportRequest,
    FeedbackCreateRequest,
    FeeEntryUpsertRequest,
    InquiryDecisionRequest,
    InquiryV10CreateRequest,
    MasterDataFieldUpdateRequest,
    MutateRequest,
    PipelineUpdateRequest,
    SperrterminCalculatorRequest,
    SperrterminCreateRequest,
    StateWriteRequest,
    WebhookIngestRequest,
    utc_now_iso,
)
from .storage import RevisionConflictError, StorageCorruptedError, StorageEngine


def create_app(custom_config: Optional[AppConfig] = None) -> FastAPI:
    cfg = custom_config or load_config()
    storage = StorageEngine(cfg.data_path)
    storage.ensure_dirs()

    app = FastAPI(
        title="ZTA OS API (V10)",
        version="10.0.0",
        description="ZTA Management Talent- & PR-Agentur Betriebssystem (Stand V10 / 50 Features)",
    )
    app.state.config = cfg
    app.state.storage = storage

    @app.exception_handler(StorageCorruptedError)
    async def handle_corrupted(_request: Request, exc: StorageCorruptedError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": "storage_corrupted",
                "message": exc.message,
                "latest_backup": exc.latest_backup,
            },
        )

    @app.exception_handler(RevisionConflictError)
    async def handle_conflict(_request: Request, exc: RevisionConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": "revision_conflict",
                "message": str(exc),
                "expected_revision": exc.expected_revision,
                "current_revision": exc.current_state["meta"]["revision"],
                "current_state": exc.current_state,
            },
        )

    def _enrich_state(state: Dict[str, Any]) -> Dict[str, Any]:
        cols = state["collections"]
        clients = cols.get("clients", {})
        cal_events = cols.get("calendar_events", {})
        inquiries = cols.get("inquiries", {})
        castings = cols.get("castings", {})
        contracts = cols.get("contracts", {})
        time_logs = cols.get("time_logs", {})

        for cid, cdoc in castings.items():
            dl = cdoc.get("deadline_date")
            if dl:
                sched = compute_casting_schedule(
                    deadline_date=str(dl),
                    tape_status=str(cdoc.get("tape_status") or "open"),
                )
                cdoc["internal_review_date"] = sched["internal_review_date"]
                cdoc["urgency"] = sched["urgency"]
                cdoc["countdown_label"] = sched["countdown_label"]
                cdoc["days_until_deadline"] = sched["days_until_deadline"]

        for iid, idoc in inquiries.items():
            v10_eval = evaluate_inquiry_v10(iid, idoc)
            idoc.update(v10_eval)
            client_id = str(idoc.get("client_id") or "")
            start_d = str(idoc.get("dzr_start") or idoc.get("start_date") or "")
            end_d = str(idoc.get("dzr_end") or idoc.get("end_date") or start_d)
            if client_id and start_d:
                avail = check_client_availability(
                    client_id=client_id,
                    start_date=start_d,
                    end_date=end_d,
                    calendar_events=cal_events,
                    ignore_event_id=idoc.get("linked_event_id"),
                )
                idoc["availability_status"] = avail["overall_status"]
                idoc["free_days_count"] = avail["free_days_count"]
                idoc["blocked_days_count"] = avail["blocked_days_count"]
                idoc["recommended_option_rank"] = avail["recommended_option_rank"]
                idoc["conflicts_count"] = len(avail["hard_conflicts"]) + len(avail["partial_items"])
                client_doc = clients.get(client_id, {"name": client_id})
                idoc["reply_template"] = generate_inquiry_reply(client_doc, idoc, avail)

        indicators_by_client: Dict[str, Any] = {}
        plausibility_by_client: Dict[str, Any] = {}
        for cid, cdoc in clients.items():
            indicators_by_client[cid] = compute_industry_interest_indicators(cid, inquiries, castings)
            plausibility_by_client[cid] = validate_master_data_plausibility(cdoc)

        liquidity = build_liquidity_timeline(contracts, clients)
        effort_report = build_effort_vs_commission_report(clients, contracts, time_logs)

        state["computed"] = {
            "liquidity": liquidity,
            "effort_vs_commission": effort_report,
            "indicators_by_client": indicators_by_client,
            "plausibility_by_client": plausibility_by_client,
            "zdf_gvr_models": ZDF_GVR_MODELS,
            "sync_conflicts": storage.detect_sync_conflicts(),
            "backups": storage.list_backups(),
        }
        return state

    @app.get("/api/health")
    async def get_health() -> Dict[str, Any]:
        state = storage.read_state()
        return {
            "status": "ok",
            "app": cfg.app_name,
            "version": "10.0.0",
            "revision": state["meta"]["revision"],
            "updated_at": state["meta"]["updated_at"],
            "has_data": storage.has_any_data(),
            "data_file": str(storage.data_path),
            "backups_count": len(storage.list_backups()),
            "sync_conflicts": storage.detect_sync_conflicts(),
        }

    @app.get("/api/state")
    async def get_state() -> Dict[str, Any]:
        state = storage.read_state()
        return _enrich_state(state)

    @app.post("/api/state")
    async def post_state(req: StateWriteRequest) -> Dict[str, Any]:
        written = storage.write_new_state(req.collections, if_revision=req.if_revision)
        return _enrich_state(written)

    @app.post("/api/mutate")
    async def post_mutate(req: MutateRequest) -> Dict[str, Any]:
        try:
            written = storage.mutate_document(
                collection=req.collection,
                doc_id=req.doc_id,
                op=req.op,
                data=req.data,
                if_revision=req.if_revision,
                actor_role=req.actor_role,
                actor_id=req.actor_id,
            )
            return _enrich_state(written)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ==========================================================================
    # V10 MASTER-PROMPT SPEZIFISCHE ENDPUNKTE
    # ==========================================================================

    @app.post("/api/v10/sperrtermin")
    async def api_v10_create_sperrtermin(req: SperrterminCreateRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        try:
            validated = validate_sperrtermin_v10(
                level=req.level,
                location=req.location,
                start_date=req.start_date,
                end_date=req.end_date,
                raise_on_error=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        cols = state["collections"]
        ev_id = f"ev-sperr-{uuid.uuid4().hex[:8]}"
        cols.setdefault("calendar_events", {})[ev_id] = {
            "client_id": req.client_id,
            "category": "sperrtermin",
            "event_type": "sperr",
            "level": validated["level"],
            "sperr_level": validated["level"],
            "location": validated["location"],
            "title": req.title.strip() or ("Sperrtermin (Rot)" if validated["level"] == "rot" else "Sperrtermin (Orange)"),
            "start_date": validated["start_date"],
            "end_date": validated["end_date"],
            "would_cancel_shoot_day": req.would_cancel_shoot_day,
            "created_by_role": req.created_by_role,
            "all_day": True,
            "status": "confirmed",
            "tenant_id": cfg.default_tenant_id,
            "updated_at": utc_now_iso(),
        }

        written = storage.write_new_state(cols, if_revision=cur_rev)
        ev_doc = dict(cols["calendar_events"][ev_id], id=ev_id)
        return {
            "event_id": ev_id,
            "event": ev_doc,
            "sperrtermin": ev_doc,
            "state": _enrich_state(written),
        }

    @app.post("/api/v10/sperrtermin-rechner")
    async def api_v10_sperrtermin_rechner(req: SperrterminCalculatorRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cols = state["collections"]
        return compute_sperrtermin_rechner(
            client_id=req.client_id,
            dzr_start=req.dzr_start,
            dzr_end=req.dzr_end,
            sender_category=req.sender_category,
            clients=cols.get("clients", {}),
            calendar_events=cols.get("calendar_events", {}),
            inquiries=cols.get("inquiries", {}),
            castings=cols.get("castings", {}),
            fee_matrix=cols.get("fee_matrix", {}),
            include_adjacent_days=req.include_adjacent_days,
            project_name=req.project_name,
        )

    @app.post("/api/v10/inquiries")
    async def api_v10_create_inquiry(req: InquiryV10CreateRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        inq_id = f"inq-{uuid.uuid4().hex[:8]}"
        resolved_title = (req.project_title or req.project_name or "Neues Projekt").strip()
        resolved_sender = (req.sender_category or req.sender_platform or "ZDF").strip()

        # Richtwert aus Gagen-Spiegel vorschlagen, falls keine Gage uebergeben wurde (Feature 28)
        quoted_cents = req.quoted_fee_cents
        if quoted_cents is None:
            quoted_cents = 0
            for fdoc in cols.get("fee_matrix", {}).values():
                if fdoc.get("client_id") == req.client_id and str(fdoc.get("category") or "").lower() == resolved_sender.lower():
                    quoted_cents = int(
                        fdoc.get("guideline_ma_cents")
                        if req.fee_variant == "MA"
                        else fdoc.get("guideline_cents") or 0
                    )
                    break

        record = {
            "client_id": req.client_id,
            "received_date": req.received_date,
            "caster_name": req.caster_name.strip(),
            "contact_person": req.caster_name.strip(),
            "project_title": resolved_title,
            "project_name": resolved_title,
            "production_company": req.production_company.strip(),
            "sender_platform": resolved_sender,
            "sender_category": resolved_sender,
            "project_type": req.project_type,
            "time_slot": req.time_slot,
            "role_size": req.role_size,
            "dzr_start": req.dzr_start,
            "dzr_end": req.dzr_end,
            "start_date": req.dzr_start,
            "end_date": req.dzr_end,
            "shooting_days": req.shooting_days,
            "requested_shooting_days": req.shooting_days,
            "shooting_location": req.shooting_location.strip() or "Berlin",
            "quoted_fee_cents": int(quoted_cents),
            "suggested_guideline_cents": int(quoted_cents),
            "offered_gage_cents": int(quoted_cents),
            "fee_variant": req.fee_variant,
            "pipeline_stage": req.pipeline_stage,
            "e_casting_deadline": req.e_casting_deadline,
            "live_casting_date": req.live_casting_date,
            "live_casting_location": req.live_casting_location,
            "contract_dropbox_url": req.contract_dropbox_url.strip(),
            "status": "open",
            "tenant_id": cfg.default_tenant_id,
            "updated_at": utc_now_iso(),
        }
        cols.setdefault("inquiries", {})[inq_id] = evaluate_inquiry_v10(inq_id, record)

        # Automatische Kalender-Synchronisation fuer Casting-Fristen/-Termine (Feature 48)
        if req.e_casting_deadline:
            cols.setdefault("calendar_events", {})[f"ev-ecast-{inq_id}"] = {
                "client_id": req.client_id,
                "category": "casting",
                "event_type": "casting",
                "casting_subtype": "e_casting",
                "title": f"E-Casting-Frist: {resolved_title}",
                "location": "E-Casting Upload",
                "start_date": req.e_casting_deadline,
                "end_date": req.e_casting_deadline,
                "source_inquiry_id": inq_id,
                "all_day": True,
                "status": "confirmed",
                "tenant_id": cfg.default_tenant_id,
                "updated_at": utc_now_iso(),
            }
        if req.live_casting_date:
            cols.setdefault("calendar_events", {})[f"ev-lcast-{inq_id}"] = {
                "client_id": req.client_id,
                "category": "casting",
                "event_type": "casting",
                "casting_subtype": "live_casting",
                "title": f"Live-Casting: {resolved_title}",
                "location": req.live_casting_location or req.shooting_location or "Berlin",
                "start_date": req.live_casting_date,
                "end_date": req.live_casting_date,
                "source_inquiry_id": inq_id,
                "all_day": True,
                "status": "confirmed",
                "tenant_id": cfg.default_tenant_id,
                "updated_at": utc_now_iso(),
            }

        # Benachrichtigung fuer Klient:in erzeugen (Feature 27)
        notif_id = f"ntf-{uuid.uuid4().hex[:8]}"
        cols.setdefault("notifications", {})[notif_id] = {
            "client_id": req.client_id,
            "category": "zeitanfrage",
            "title": f"Neue Zeitanfrage: {resolved_title}",
            "message": f"Caster:in {req.caster_name.strip()} hat fuer {resolved_title} (DZR {req.dzr_start} bis {req.dzr_end}) angefragt.",
            "read": False,
            "created_at": utc_now_iso(),
            "tenant_id": cfg.default_tenant_id,
        }

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "inquiry_id": inq_id,
            "inquiry": cols["inquiries"][inq_id],
            "state": _enrich_state(written),
        }

    @app.post("/api/v10/pipeline")
    async def api_v10_update_pipeline(req: PipelineUpdateRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        inquiries = cols.setdefault("inquiries", {})
        if req.inquiry_id not in inquiries:
            raise HTTPException(status_code=404, detail=f"Zeitanfrage '{req.inquiry_id}' nicht gefunden.")

        doc = dict(inquiries[req.inquiry_id])
        if req.pipeline_stage is not None:
            doc["pipeline_stage"] = req.pipeline_stage
        if req.e_casting_deadline is not None:
            doc["e_casting_deadline"] = req.e_casting_deadline
        if req.live_casting_date is not None:
            doc["live_casting_date"] = req.live_casting_date
        if req.live_casting_location is not None:
            doc["live_casting_location"] = req.live_casting_location
        if req.contract_dropbox_url is not None:
            doc["contract_dropbox_url"] = req.contract_dropbox_url.strip()

        doc["updated_at"] = utc_now_iso()
        evaluated = evaluate_inquiry_v10(req.inquiry_id, doc)
        inquiries[req.inquiry_id] = evaluated

        client_id = str(doc.get("client_id") or "")
        proj_title = str(doc.get("project_title") or "Projekt")
        cal = cols.setdefault("calendar_events", {})

        # Synchronisiere E-Casting & Live-Casting Termine in den Monatskalender (Feature 48)
        if doc.get("e_casting_deadline"):
            cal[f"ev-ecast-{req.inquiry_id}"] = {
                "client_id": client_id,
                "category": "casting",
                "event_type": "casting",
                "casting_subtype": "e_casting",
                "title": f"E-Casting-Frist: {proj_title}",
                "location": "E-Casting Upload",
                "start_date": doc["e_casting_deadline"],
                "end_date": doc["e_casting_deadline"],
                "source_inquiry_id": req.inquiry_id,
                "all_day": True,
                "status": "confirmed",
                "tenant_id": cfg.default_tenant_id,
                "updated_at": utc_now_iso(),
            }
        if doc.get("live_casting_date"):
            cal[f"ev-lcast-{req.inquiry_id}"] = {
                "client_id": client_id,
                "category": "casting",
                "event_type": "casting",
                "casting_subtype": "live_casting",
                "title": f"Live-Casting: {proj_title}",
                "location": doc.get("live_casting_location") or doc.get("shooting_location") or "Berlin",
                "start_date": doc["live_casting_date"],
                "end_date": doc["live_casting_date"],
                "source_inquiry_id": req.inquiry_id,
                "all_day": True,
                "status": "confirmed",
                "tenant_id": cfg.default_tenant_id,
                "updated_at": utc_now_iso(),
            }

        # Wenn ein Vertrag in Dropbox hinterlegt wurde -> Buchung im Kalender als ZTA-Termin sichern (Feature 50)
        if evaluated["is_booked"]:
            cal[f"ev-book-{req.inquiry_id}"] = {
                "client_id": client_id,
                "category": "zta_termin",
                "event_type": "dzr",
                "zta_type_label": "Drehzeitraum (Gebucht)",
                "title": f"GEBUCHT: {proj_title}",
                "location": doc.get("shooting_location") or "Berlin",
                "start_date": evaluated["dzr_start"],
                "end_date": evaluated["dzr_end"],
                "contract_dropbox_url": doc.get("contract_dropbox_url"),
                "source_inquiry_id": req.inquiry_id,
                "all_day": True,
                "status": "confirmed",
                "tenant_id": cfg.default_tenant_id,
                "updated_at": utc_now_iso(),
            }

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "inquiry": evaluated,
            "state": _enrich_state(written),
        }

    @app.post("/api/v10/fees")
    async def api_v10_upsert_fee(req: FeeEntryUpsertRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        resolved_achieved = (
            parse_eur_to_cents(req.last_achieved_eur)
            if req.last_achieved_eur is not None
            else req.last_achieved_cents
        )
        resolved_guideline = (
            parse_eur_to_cents(req.guideline_eur)
            if req.guideline_eur is not None
            else req.guideline_cents
        )
        resolved_variant = req.settlement_model or req.variant_default or "MW"
        resolved_status = req.status or req.fee_status or "fest"
        resolved_zdf = req.zdf_length_model if req.zdf_length_model is not None else req.zdf_model

        try:
            outcome = upsert_fee_entry_v10(
                collections=cols,
                client_id=req.client_id,
                category=req.category,
                last_achieved_cents=resolved_achieved,
                guideline_cents=resolved_guideline,
                unit=req.unit,
                currency=req.currency,
                guideline_ma_cents=req.guideline_ma_cents,
                variant_default=resolved_variant,
                settlement_model=resolved_variant,
                valid_years=req.valid_years,
                target_next_year_cents=req.target_next_year_cents,
                fee_status=resolved_status,
                status=resolved_status,
                zdf_model=resolved_zdf,
                zdf_length_model=resolved_zdf,
                auto_raise_guideline=req.auto_raise_guideline,
                entry_id=req.entry_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "outcome": outcome,
            "entry": outcome.get("entry") or outcome.get("record"),
            "state": _enrich_state(written),
        }

    @app.post("/api/v10/master-data/update-field")
    async def api_v10_update_master_field(req: MasterDataFieldUpdateRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        clients = cols.setdefault("clients", {})
        if req.client_id not in clients:
            raise HTTPException(status_code=404, detail=f"Klient:in '{req.client_id}' nicht gefunden.")

        field_key = (req.field_key or req.field_name or "legal_name").strip()
        cdoc = dict(clients[req.client_id])
        md = dict(cdoc.get("master_data") or {})
        existing_entry = md.get(field_key)
        old_val_str = ""
        if isinstance(existing_entry, dict):
            old_val_str = str(existing_entry.get("value") or "")
        elif existing_entry is not None:
            old_val_str = str(existing_entry)

        md[field_key] = req.new_value.strip()
        cdoc["master_data"] = md

        hist_list = list(cdoc.get("master_data_history") or [])
        if old_val_str != req.new_value.strip():
            hist_list.insert(
                0,
                {
                    "field_name": field_key,
                    "old_value": old_val_str,
                    "new_value": req.new_value.strip(),
                    "valid_from": req.valid_from,
                    "verified_by": req.verified_by or req.confirmed_by,
                    "updated_at": utc_now_iso(),
                },
            )
        cdoc["master_data_history"] = hist_list
        cdoc["updated_at"] = utc_now_iso()
        clients[req.client_id] = cdoc

        issues = validate_master_data_plausibility(cdoc)
        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "client_id": req.client_id,
            "field_key": field_key,
            "plausibility_issues": issues,
            "plausibility": {
                "issues": issues,
                "warnings": [i["message"] for i in issues],
            },
            "state": _enrich_state(written),
        }

    @app.get("/api/v10/indicators/{client_id}")
    async def api_v10_indicators(client_id: str) -> Dict[str, Any]:
        state = storage.read_state()
        cols = state["collections"]
        if client_id not in cols.get("clients", {}):
            raise HTTPException(status_code=404, detail=f"Klient:in '{client_id}' nicht gefunden.")
        return compute_industry_interest_indicators(
            client_id=client_id,
            inquiries=cols.get("inquiries", {}),
            castings=cols.get("castings", {}),
        )

    @app.get("/api/v10/client-view/{client_id}")
    async def api_v10_client_view(client_id: str) -> Dict[str, Any]:
        state = storage.read_state()
        try:
            return build_client_rbac_view(state, client_id=client_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/api/v10/reset")
    async def api_v10_reset() -> Dict[str, Any]:
        from scripts.build_initial_data import build_synthetic_dataset

        dataset = build_synthetic_dataset()
        written = storage.write_new_state(dataset)
        return _enrich_state(written)

    # ==========================================================================
    # BESTEHENDE KOMPATIBILITAETS-ENDPUNKTE
    # ==========================================================================

    @app.get("/api/availability/check")
    async def api_check_availability(
        client_id: str = Query(...),
        start_date: str = Query(...),
        end_date: str = Query(...),
    ) -> Dict[str, Any]:
        state = storage.read_state()
        cal_events = state["collections"].get("calendar_events", {})
        return check_client_availability(client_id, start_date, end_date, cal_events)

    @app.post("/api/availability/free-clients")
    async def api_free_clients(req: ClientFilterQuery) -> Dict[str, Any]:
        state = storage.read_state()
        cols = state["collections"]
        results = find_free_clients(
            clients=cols.get("clients", {}),
            calendar_events=cols.get("calendar_events", {}),
            start_date=req.start_date,
            end_date=req.end_date,
            division=req.division,
            include_options=req.include_options,
        )
        return {
            "start_date": req.start_date,
            "end_date": req.end_date,
            "division": req.division or "all",
            "results": results,
        }

    @app.get("/api/availability/month-grid")
    async def api_month_grid(
        year: int = Query(2026, ge=2020, le=2035),
        month: int = Query(11, ge=1, le=12),
        division: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        state = storage.read_state()
        cols = state["collections"]
        return build_month_grid(
            clients=cols.get("clients", {}),
            calendar_events=cols.get("calendar_events", {}),
            year=year,
            month=month,
            division=division,
        )

    @app.get("/api/inquiries/{inquiry_id}/reply-template")
    async def api_inquiry_reply_template(inquiry_id: str) -> Dict[str, Any]:
        state = storage.read_state()
        cols = state["collections"]
        inq = cols.get("inquiries", {}).get(inquiry_id)
        if not inq:
            raise HTTPException(status_code=404, detail=f"Zeitanfrage '{inquiry_id}' nicht gefunden.")
        client_id = str(inq.get("client_id") or "")
        client_doc = cols.get("clients", {}).get(client_id, {"name": client_id})
        avail = check_client_availability(
            client_id=client_id,
            start_date=str(inq.get("start_date") or inq.get("dzr_start")),
            end_date=str(inq.get("end_date") or inq.get("dzr_end") or inq.get("start_date")),
            calendar_events=cols.get("calendar_events", {}),
            ignore_event_id=inq.get("linked_event_id"),
        )
        text = generate_inquiry_reply(client_doc, inq, avail)
        return {
            "inquiry_id": inquiry_id,
            "client_id": client_id,
            "availability": avail,
            "reply_template": text,
        }

    @app.post("/api/inquiries/decision")
    async def api_inquiry_decision(req: InquiryDecisionRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        try:
            outcome = apply_inquiry_decision(
                collections=cols,
                inquiry_id=req.inquiry_id,
                decision=req.decision,
                option_rank=req.option_rank,
                option_expires_at=req.option_expires_at,
                create_contract_draft=req.create_contract_draft,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "outcome": outcome,
            "state": _enrich_state(written),
        }

    @app.post("/api/portal/blocker")
    async def api_portal_blocker(req: ClientPortalBlockerRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        if req.client_id not in cols.get("clients", {}):
            raise HTTPException(status_code=404, detail=f"Klient:in '{req.client_id}' nicht gefunden.")

        try:
            validated = validate_sperrtermin_v10(
                level=req.level,
                location=req.location,
                start_date=req.start_date,
                end_date=req.end_date,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        prior_avail = check_client_availability(
            client_id=req.client_id,
            start_date=req.start_date,
            end_date=req.end_date,
            calendar_events=cols.get("calendar_events", {}),
        )
        warnings = [
            f"Konflikt mit '{ev.get('title', 'Termin')}' ({ev.get('event_type')}, {ev.get('start_date')} bis {ev.get('end_date')})"
            for ev in prior_avail["overlapping_events"]
            if ev.get("event_type") != "sperr"
        ]

        new_ev_id = f"ev-sperr-{uuid.uuid4().hex[:8]}"
        cols.setdefault("calendar_events", {})[new_ev_id] = {
            "client_id": req.client_id,
            "category": "sperrtermin",
            "event_type": "sperr",
            "level": validated["level"],
            "location": validated["location"],
            "title": req.title.strip() or "Sperrtermin",
            "start_date": validated["start_date"],
            "end_date": validated["end_date"],
            "would_cancel_shoot_day": req.would_cancel_shoot_day,
            "all_day": req.all_day,
            "time_label": req.time_label,
            "notes": req.notes,
            "status": "confirmed",
            "created_via": "client_portal",
            "has_agency_conflict": bool(warnings),
            "conflict_warnings": warnings,
            "tenant_id": cfg.default_tenant_id,
            "updated_at": utc_now_iso(),
        }

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "event_id": new_ev_id,
            "has_conflict": bool(warnings),
            "conflict_warnings": warnings,
            "state": _enrich_state(written),
        }

    @app.post("/api/portal/respond")
    async def api_portal_respond(req: ClientPortalResponseRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        col_name = "inquiries" if req.target_type == "inquiry" else "castings"
        target_col = cols.setdefault(col_name, {})
        if req.target_id not in target_col:
            raise HTTPException(status_code=404, detail=f"Eintrag '{req.target_id}' in {col_name} nicht gefunden.")

        doc = dict(target_col[req.target_id])
        doc["client_response"] = req.response
        doc["client_comment"] = req.comment.strip()
        doc["client_responded_at"] = utc_now_iso()
        doc["updated_at"] = utc_now_iso()
        target_col[req.target_id] = doc

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "target_type": req.target_type,
            "target_id": req.target_id,
            "client_response": req.response,
            "state": _enrich_state(written),
        }

    @app.post("/api/contracts/calculate")
    async def api_calculate_contract(req: ContractCalculateRequest) -> Dict[str, Any]:
        try:
            return calculate_contract_financials(
                division=req.division,
                gage_cents=req.gage_cents,
                buyout_cents=req.buyout_cents,
                commission_rate_bp=req.commission_rate_bp,
                engagement_days=req.engagement_days,
                vat_rate_bp=req.vat_rate_bp,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/contracts/status")
    async def api_update_contract_status(req: ContractStatusUpdateRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        try:
            outcome = apply_contract_status_with_auto_offset(
                collections=cols,
                contract_id=req.contract_id,
                new_status=req.new_status,
                paid_amount_cents=req.paid_amount_cents,
                paid_at=req.paid_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "outcome": outcome,
            "state": _enrich_state(written),
        }

    @app.get("/api/analytics/liquidity")
    async def api_liquidity() -> Dict[str, Any]:
        state = storage.read_state()
        cols = state["collections"]
        return build_liquidity_timeline(cols.get("contracts", {}), cols.get("clients", {}))

    @app.get("/api/analytics/effort-vs-commission")
    async def api_effort_vs_commission() -> Dict[str, Any]:
        state = storage.read_state()
        cols = state["collections"]
        return {
            "items": build_effort_vs_commission_report(
                cols.get("clients", {}),
                cols.get("contracts", {}),
                cols.get("time_logs", {}),
            )
        }

    @app.get("/api/ical/{client_id}.ics")
    async def api_client_ical(client_id: str, token: Optional[str] = Query(None)) -> Response:
        state = storage.read_state()
        cols = state["collections"]
        client = cols.get("clients", {}).get(client_id)
        if not client:
            raise HTTPException(status_code=404, detail=f"Klient:in '{client_id}' nicht gefunden.")
        expected_token = client.get("ical_token")
        if expected_token and token and token != expected_token:
            raise HTTPException(status_code=403, detail="Ungueltiger iCal-Token.")
        ics_body = generate_client_ical(client_id, client, cols.get("calendar_events", {}))
        return Response(
            content=ics_body,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{client_id}.ics"'},
        )

    @app.post("/api/feedback/report")
    async def api_feedback_report(req: FeedbackCreateRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        cols = state["collections"]
        fb_id = f"FB-{len(cols.get('feedback_items', {})) + 101:03d}"
        cols.setdefault("feedback_items", {})[fb_id] = {
            "title": req.title.strip(),
            "description": req.description.strip(),
            "category": req.category,
            "status": "neu",
            "reported_by_role": req.reported_by_role,
            "reported_by_name": req.reported_by_name,
            "view_context": req.view_context,
            "element_selector": req.element_selector,
            "device_hint": req.device_hint,
            "app_version": "10.0.0",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "tenant_id": cfg.default_tenant_id,
        }

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "feedback_id": fb_id,
            "state": _enrich_state(written),
        }

    @app.post("/api/webhooks/ingest")
    async def api_webhook_ingest(req: WebhookIngestRequest, request: Request) -> Dict[str, Any]:
        header_secret = request.headers.get("X-Webhook-Secret", "")
        if header_secret and header_secret != cfg.webhook_secret:
            raise HTTPException(status_code=403, detail="Ungueltiges X-Webhook-Secret.")

        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        cols = state["collections"]
        payload = req.payload or {}
        action_summary: Dict[str, Any] = {"event_type": req.event_type, "source": req.source}

        if req.event_type == "inquiry.received":
            inq_id = str(payload.get("id") or f"inq-wh-{uuid.uuid4().hex[:6]}")
            gage_cents = parse_eur_to_cents(payload.get("offered_gage_cents") or payload.get("offered_gage_eur") or 0)
            start_d = str(payload.get("dzr_start") or payload.get("start_date") or "2026-11-20")
            end_d = str(payload.get("dzr_end") or payload.get("end_date") or start_d)
            cols.setdefault("inquiries", {})[inq_id] = {
                "client_id": str(payload.get("client_id") or "cl-01"),
                "received_date": "2026-11-14",
                "caster_name": str(payload.get("caster_name") or payload.get("contact_person") or "Casting Berlin"),
                "contact_person": str(payload.get("contact_person") or ""),
                "project_title": str(payload.get("project_title") or "Eingehende n8n-Anfrage"),
                "production_company": str(payload.get("production_company") or ""),
                "sender_platform": str(payload.get("sender_platform") or "ZDF"),
                "project_type": str(payload.get("project_type") or "TV-Reihe (90 Min.)"),
                "time_slot": str(payload.get("time_slot") or "20:15 Primetime"),
                "role_size": str(payload.get("role_size") or "Hauptrolle"),
                "dzr_start": start_d,
                "dzr_end": end_d,
                "start_date": start_d,
                "end_date": end_d,
                "shooting_days": int(payload.get("requested_shooting_days") or 1),
                "requested_shooting_days": int(payload.get("requested_shooting_days") or 1),
                "offered_gage_cents": gage_cents,
                "quoted_fee_cents": gage_cents,
                "pipeline_stage": "zeitanfrage",
                "status": "open",
                "client_response": "pending",
                "ingested_via": req.source,
                "tenant_id": req.tenant_id,
                "updated_at": utc_now_iso(),
            }
            action_summary["created_inquiry_id"] = inq_id

        elif req.event_type == "payment.settled":
            contract_id = str(payload.get("contract_id") or "")
            if contract_id not in cols.get("contracts", {}):
                raise HTTPException(status_code=404, detail=f"Vertrag '{contract_id}' fuer Auto-Offset nicht gefunden.")
            settled_cents = payload.get("paid_amount_cents")
            if settled_cents is not None:
                settled_cents = int(settled_cents)
            outcome = apply_contract_status_with_auto_offset(
                collections=cols,
                contract_id=contract_id,
                new_status="paid",
                paid_amount_cents=settled_cents,
                paid_at=utc_now_iso(),
            )
            action_summary["auto_offset"] = outcome

        elif req.event_type == "calendar.blocker":
            ev_id = str(payload.get("id") or f"ev-wh-{uuid.uuid4().hex[:6]}")
            cols.setdefault("calendar_events", {})[ev_id] = {
                "client_id": str(payload.get("client_id") or "cl-01"),
                "category": "sperrtermin",
                "event_type": "sperr",
                "level": str(payload.get("level") or "rot"),
                "location": str(payload.get("location") or "Berlin"),
                "title": str(payload.get("title") or "Sperrtermin (Webhook)"),
                "start_date": str(payload.get("start_date") or "2026-11-18"),
                "end_date": str(payload.get("end_date") or payload.get("start_date") or "2026-11-18"),
                "all_day": True,
                "status": "confirmed",
                "ingested_via": req.source,
                "tenant_id": req.tenant_id,
                "updated_at": utc_now_iso(),
            }
            action_summary["created_event_id"] = ev_id

        elif req.event_type == "casting.invited":
            cast_id = str(payload.get("id") or f"cast-wh-{uuid.uuid4().hex[:6]}")
            dl = str(payload.get("deadline_date") or "2026-11-16")
            sched = compute_casting_schedule(dl)
            cols.setdefault("castings", {})[cast_id] = {
                "client_id": str(payload.get("client_id") or "cl-01"),
                "project_title": str(payload.get("project_title") or "E-Casting Einladung"),
                "role_name": str(payload.get("role_name") or "Hauptrolle"),
                "casting_director": str(payload.get("casting_director") or ""),
                "casting_type": str(payload.get("casting_type") or "e_casting"),
                "deadline_date": sched["deadline_date"],
                "internal_review_date": sched["internal_review_date"],
                "tape_status": "open",
                "client_response": "pending",
                "ingested_via": req.source,
                "tenant_id": req.tenant_id,
                "updated_at": utc_now_iso(),
            }
            action_summary["created_casting_id"] = cast_id

        written = storage.write_new_state(cols, if_revision=cur_rev)
        return {
            "status": "processed",
            "summary": action_summary,
            "revision": written["meta"]["revision"],
        }

    @app.post("/api/import/parse")
    async def api_import_parse(req: CsvOrJsonImportRequest) -> Dict[str, Any]:
        state = storage.read_state()
        cur_rev = state["meta"]["revision"]
        if req.if_revision is not None and req.if_revision != cur_rev:
            raise RevisionConflictError(req.if_revision, state)

        valid_docs, warnings = parse_import_payload(
            fmt=req.format,
            target_collection=req.target_collection,
            raw_content=req.raw_content,
            tenant_id=req.tenant_id,
        )
        cols = state["collections"]
        target = cols.setdefault(req.target_collection, {})
        for doc_id, doc in valid_docs.items():
            target[doc_id] = doc

        written = storage.write_new_state(cols, if_revision=cur_rev) if valid_docs else state
        return {
            "imported_count": len(valid_docs),
            "warnings": warnings,
            "state": _enrich_state(written),
        }

    @app.get("/api/backup/export")
    async def api_backup_export() -> Response:
        state = storage.read_state()
        payload = json.dumps(state, ensure_ascii=False, indent=2)
        filename = f"zta-os-v10-backup-rev{state['meta']['revision']}.json"
        return Response(
            content=payload,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/ai/assist")
    async def api_ai_assist(req: AiAssistRequest) -> Dict[str, Any]:
        return run_ai_assist(
            mode=req.mode,
            context=req.context,
            api_key=cfg.gemini_api_key,
            model_name=cfg.gemini_model,
        )

    @app.get("/manifest.json")
    async def serve_manifest() -> Response:
        manifest_file = cfg.frontend_dir / "manifest.json"
        if manifest_file.exists():
            return FileResponse(manifest_file, media_type="application/manifest+json")
        return JSONResponse({"name": "ZTA OS", "short_name": "ZTA OS"})

    @app.get("/shim.js")
    async def serve_shim() -> Response:
        shim_file = cfg.frontend_dir / "shim.js"
        if shim_file.exists():
            return FileResponse(shim_file, media_type="application/javascript")
        return PlainTextResponse("// ZTA OS shim", media_type="application/javascript")

    @app.get("/")
    async def serve_index() -> Response:
        index_file = cfg.frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html; charset=utf-8")
        return PlainTextResponse("ZTA OS Frontend noch nicht erstellt.", status_code=404)

    return app


app = create_app()
