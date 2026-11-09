"""FastAPI Hauptanwendung fuer ZTA OS."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from .ai import run_ai_assist
from .config import AppConfig, load_config
from .logic import (
    apply_contract_status_with_auto_offset,
    apply_inquiry_decision,
    build_effort_vs_commission_report,
    build_liquidity_timeline,
    build_month_grid,
    calculate_contract_financials,
    check_client_availability,
    compute_casting_schedule,
    find_free_clients,
    generate_client_ical,
    generate_inquiry_reply,
    parse_eur_to_cents,
    parse_import_payload,
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
    InquiryDecisionRequest,
    MutateRequest,
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
        title="ZTA OS API",
        version=cfg.app_version,
        description="Zentrales Talent- & Agentur-Betriebssystem (Canvas Standard & APP RULES v1.0)",
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

        # Castings mit Sichtungstermin (2 Tage vor Deadline) & Countdown anreichern
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

        # Zeitanfragen mit aktueller Verfuegbarkeitspruefung und Antwortvorlage anreichern
        for iid, idoc in inquiries.items():
            client_id = str(idoc.get("client_id") or "")
            start_d = str(idoc.get("start_date") or "")
            end_d = str(idoc.get("end_date") or start_d)
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

        liquidity = build_liquidity_timeline(contracts, clients)
        effort_report = build_effort_vs_commission_report(clients, contracts, time_logs)

        state["computed"] = {
            "liquidity": liquidity,
            "effort_vs_commission": effort_report,
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
            "version": cfg.app_version,
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
            start_date=str(inq.get("start_date")),
            end_date=str(inq.get("end_date") or inq.get("start_date")),
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

        cols.setdefault("audit_logs", {})[f"aud-{uuid.uuid4().hex[:10]}"] = {
            "timestamp": utc_now_iso(),
            "collection": "inquiries",
            "doc_id": req.inquiry_id,
            "op": f"decision:{req.decision}",
            "actor_role": "agentur",
            "actor_id": "zta-desk",
            "details": outcome,
            "tenant_id": cfg.default_tenant_id,
        }

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

        # Vor dem Eintragen pruefen, ob bereits Optionen, DZR, DT oder Castings im Zeitraum liegen
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
            "event_type": "sperr",
            "title": req.title.strip() or "Privat / Sperrtermin",
            "start_date": req.start_date,
            "end_date": req.end_date,
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

        cols.setdefault("audit_logs", {})[f"aud-{uuid.uuid4().hex[:10]}"] = {
            "timestamp": utc_now_iso(),
            "collection": "calendar_events",
            "doc_id": new_ev_id,
            "op": "portal_blocker",
            "actor_role": "klient",
            "actor_id": req.client_id,
            "warnings": warnings,
            "tenant_id": cfg.default_tenant_id,
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

        cols.setdefault("audit_logs", {})[f"aud-{uuid.uuid4().hex[:10]}"] = {
            "timestamp": utc_now_iso(),
            "collection": col_name,
            "doc_id": req.target_id,
            "op": f"client_response:{req.response}",
            "actor_role": "klient",
            "actor_id": req.client_id,
            "tenant_id": cfg.default_tenant_id,
        }

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

        cols.setdefault("audit_logs", {})[f"aud-{uuid.uuid4().hex[:10]}"] = {
            "timestamp": utc_now_iso(),
            "collection": "contracts",
            "doc_id": req.contract_id,
            "op": f"status:{req.new_status}",
            "actor_role": "inhaberin",
            "actor_id": "zta-finance",
            "details": outcome,
            "tenant_id": cfg.default_tenant_id,
        }

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
            "app_version": cfg.app_version,
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
            cols.setdefault("inquiries", {})[inq_id] = {
                "client_id": str(payload.get("client_id") or "cl-01"),
                "project_title": str(payload.get("project_title") or "Eingehende n8n-Anfrage"),
                "production_company": str(payload.get("production_company") or ""),
                "contact_person": str(payload.get("contact_person") or ""),
                "start_date": str(payload.get("start_date") or "2026-11-20"),
                "end_date": str(payload.get("end_date") or payload.get("start_date") or "2026-11-22"),
                "requested_shooting_days": int(payload.get("requested_shooting_days") or 1),
                "offered_gage_cents": gage_cents,
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
                "event_type": "sperr",
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

        cols.setdefault("audit_logs", {})[f"aud-{uuid.uuid4().hex[:10]}"] = {
            "timestamp": utc_now_iso(),
            "collection": "webhooks",
            "doc_id": req.event_type,
            "op": "webhook_ingest",
            "actor_role": "system",
            "actor_id": req.source,
            "details": action_summary,
            "tenant_id": req.tenant_id,
        }

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
        filename = f"zta-os-backup-rev{state['meta']['revision']}.json"
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
