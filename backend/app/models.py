"""Strikte Pydantic v2 Modelle und Schema-Migration fuer ZTA OS (Stand V10)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

SCHEMA_VERSION = 10

KNOWN_COLLECTIONS = (
    "clients",
    "calendar_events",
    "inquiries",
    "castings",
    "contracts",
    "fee_matrix",
    "reference_deals",
    "documents",
    "notifications",
    "team_tasks",
    "time_logs",
    "feedback_items",
    "hub_questions",
    "audit_logs",
    "settings",
)

DepartmentType = Literal["actors", "directors_writers", "nxt", "pr_commercial", "consulting"]
DivisionType = Literal["schauspiel", "regie_drehbuch", "nxt", "pr_commercial", "actors", "directors_writers", "consulting"]
SperrLevelType = Literal["orange", "rot"]
FeeCategoryType = Literal["Streamer", "ARD/Degeto", "ZDF", "Kino", "Kino/Streaming", "International"]
FeeVariantType = Literal["MW", "MA"]
FeeStatusType = Literal["fest", "VB", "TBA"]
PipelineStageType = Literal["zeitanfrage", "e_casting", "live_casting"]
ContractStatus = Literal["draft", "negotiation", "final_signed", "invoiced", "paid", "cancelled"]
ClientResponseType = Literal["pending", "fits", "declined", "question"]
TeamAssigneeType = Literal["sarah", "elias", "zetha"]
TaskPriorityType = Literal["p1_urgent", "p2_important", "p3_routine"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MutateRequest(BaseModel):
    collection: str
    doc_id: str
    op: Literal["set", "update", "delete"]
    data: Optional[Dict[str, Any]] = None
    if_revision: Optional[int] = None
    actor_role: str = "inhaberin"
    actor_id: str = "team-zta"


class StateWriteRequest(BaseModel):
    collections: Dict[str, Dict[str, Any]]
    if_revision: Optional[int] = None


class ClientFilterQuery(BaseModel):
    start_date: str
    end_date: str
    division: Optional[str] = None
    department: Optional[str] = None
    include_options: bool = True
    include_adjacent_days: bool = False
    tenant_id: str = "zta-berlin"


class SperrterminCreateRequest(BaseModel):
    client_id: str
    start_date: str
    end_date: str
    level: SperrLevelType = "rot"
    location: str = ""
    title: str = "Sperrtermin"
    would_cancel_shoot_day: bool = True
    created_by_role: str = "klient"
    if_revision: Optional[int] = None


class SperrterminCalculatorRequest(BaseModel):
    client_id: str
    dzr_start: str
    dzr_end: str
    sender_category: str = "ZDF"
    project_name: str = ""
    include_adjacent_days: bool = True
    reference_date: str = "2026-11-14"


class InquiryV10CreateRequest(BaseModel):
    client_id: str
    received_date: str = "2026-11-14"
    caster_name: str = "Casting Office"
    project_title: str = ""
    project_name: str = ""
    production_company: str = ""
    sender_platform: str = "ZDF"
    sender_category: str = ""
    project_type: str = "TV-Reihe (90 Min.)"
    time_slot: str = "20:15 Primetime"
    role_size: str = "Hauptrolle"
    dzr_start: str
    dzr_end: str
    shooting_days: int = Field(default=3, ge=1)
    shooting_location: str = "Berlin"
    quoted_fee_cents: Optional[int] = None
    fee_variant: FeeVariantType = "MW"
    pipeline_stage: PipelineStageType = "zeitanfrage"
    e_casting_deadline: str = ""
    live_casting_date: str = ""
    live_casting_location: str = ""
    contract_dropbox_url: str = ""
    if_revision: Optional[int] = None


class PipelineUpdateRequest(BaseModel):
    inquiry_id: str
    pipeline_stage: Optional[PipelineStageType] = None
    e_casting_deadline: Optional[str] = None
    live_casting_date: Optional[str] = None
    live_casting_location: Optional[str] = None
    contract_dropbox_url: Optional[str] = None
    if_revision: Optional[int] = None


class FeeEntryUpsertRequest(BaseModel):
    entry_id: Optional[str] = None
    client_id: str
    category: str
    unit: Literal["Tag", "Woche"] = "Tag"
    currency: Literal["EUR", "GBP"] = "EUR"
    last_achieved_cents: int = Field(default=0, ge=0)
    last_achieved_eur: Optional[str] = None
    guideline_cents: int = Field(default=0, ge=0)
    guideline_eur: Optional[str] = None
    guideline_ma_cents: Optional[int] = None
    variant_default: FeeVariantType = "MW"
    settlement_model: Optional[str] = None
    valid_years: str = "2025+2026"
    target_next_year_cents: int = Field(default=0, ge=0)
    fee_status: str = "fest"
    status: Optional[str] = None
    zdf_model: str = ""
    zdf_length_model: Optional[str] = None
    auto_raise_guideline: bool = True
    if_revision: Optional[int] = None


class MasterDataFieldUpdateRequest(BaseModel):
    client_id: str
    field_key: str = ""
    field_name: str = ""
    new_value: str
    valid_from: str = "2026-11-14"
    source_doc: str = "Bestaetigung Zetha"
    confirmed_by: str = "Zetha"
    verified_by: str = "Zetha"
    if_revision: Optional[int] = None


class InquiryDecisionRequest(BaseModel):
    inquiry_id: str
    decision: Literal["option", "confirm", "decline"]
    option_rank: int = 1
    option_expires_at: Optional[str] = None
    create_contract_draft: bool = True
    if_revision: Optional[int] = None


class ClientPortalBlockerRequest(BaseModel):
    client_id: str
    start_date: str
    end_date: str
    title: str = "Sperrtermin"
    level: SperrLevelType = "rot"
    location: str = "Berlin"
    would_cancel_shoot_day: bool = True
    all_day: bool = True
    time_label: str = ""
    notes: str = ""
    if_revision: Optional[int] = None


class ClientPortalResponseRequest(BaseModel):
    client_id: str
    target_type: Literal["inquiry", "casting"]
    target_id: str
    response: ClientResponseType
    comment: str = ""
    if_revision: Optional[int] = None


class ContractCalculateRequest(BaseModel):
    division: str = "schauspiel"
    gage_cents: int = Field(ge=0)
    buyout_cents: int = Field(default=0, ge=0)
    commission_rate_bp: int = Field(default=1000, ge=0, le=5000)
    engagement_days: int = Field(default=1, ge=1)
    vat_rate_bp: int = Field(default=1900, ge=0, le=3000)


class ContractStatusUpdateRequest(BaseModel):
    contract_id: str
    new_status: ContractStatus
    paid_amount_cents: Optional[int] = None
    paid_at: Optional[str] = None
    if_revision: Optional[int] = None


class FeedbackCreateRequest(BaseModel):
    title: str
    description: str = ""
    category: Literal["bug", "wunsch", "frage", "idee"] = "wunsch"
    reported_by_role: str = "inhaberin"
    reported_by_name: str = "Zetha"
    view_context: str = "cockpit"
    element_selector: str = ""
    device_hint: str = "Desktop / PWA"
    if_revision: Optional[int] = None


class WebhookIngestRequest(BaseModel):
    event_type: Literal[
        "inquiry.received",
        "payment.settled",
        "calendar.blocker",
        "casting.invited",
    ]
    source: str = "n8n"
    tenant_id: str = "zta-berlin"
    payload: Dict[str, Any] = Field(default_factory=dict)


class CsvOrJsonImportRequest(BaseModel):
    format: Literal["csv", "json"] = "csv"
    target_collection: Literal["calendar_events", "inquiries", "clients"] = "calendar_events"
    raw_content: str
    tenant_id: str = "zta-berlin"
    if_revision: Optional[int] = None


class AiAssistRequest(BaseModel):
    mode: Literal["inquiry_reply", "contract_check", "dossier_pitch"] = "inquiry_reply"
    context: Dict[str, Any] = Field(default_factory=dict)


class TeamTaskCreateRequest(BaseModel):
    raw_input: str = ""
    title: str = ""
    assignee: TeamAssigneeType = "sarah"
    created_by: str = "zetha"
    priority: TaskPriorityType = "p2_important"
    client_id: Optional[str] = None
    due_date: str = "2026-11-15"
    reminder_interval_hours: int = Field(default=4, ge=1, le=72)
    notes: str = ""
    if_revision: Optional[int] = None


class TeamTaskToggleRequest(BaseModel):
    task_id: str
    completed_by: str = "sarah"
    if_revision: Optional[int] = None


class TeamTaskPingRequest(BaseModel):
    task_id: str
    triggered_by: str = "zetha"
    if_revision: Optional[int] = None


class MultiTalentDzrRequest(BaseModel):
    dzr_start: str
    dzr_end: str
    department: str = "actors"
    sender_category: str = "ZDF"
    project_name: str = ""
    include_adjacent_days: bool = True


def migrate_schema(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Stellt sicher, dass das State-Dokument alle Pflicht-Collections und Meta-Felder (Stand V10) besitzt."""
    if not isinstance(raw, dict):
        raw = {}

    meta_in = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    meta = {
        "schema_version": SCHEMA_VERSION,
        "revision": int(meta_in.get("revision", 0)),
        "updated_at": str(meta_in.get("updated_at") or utc_now_iso()),
        "default_tenant_id": str(meta_in.get("default_tenant_id") or "zta-berlin"),
    }

    cols_in = raw.get("collections") if isinstance(raw.get("collections"), dict) else {}
    collections: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for col in KNOWN_COLLECTIONS:
        col_data = cols_in.get(col)
        if isinstance(col_data, dict):
            cleaned_col: Dict[str, Dict[str, Any]] = {}
            for doc_id, doc in col_data.items():
                if isinstance(doc, dict):
                    doc_copy = dict(doc)
                    doc_copy.pop("id", None)
                    doc_copy.setdefault("tenant_id", meta["default_tenant_id"])
                    cleaned_col[str(doc_id)] = doc_copy
            collections[col] = cleaned_col
        else:
            collections[col] = {}

    for cid, cdoc in collections["contracts"].items():
        for money_field in (
            "gage_cents",
            "buyout_cents",
            "total_gross_cents",
            "commission_cents",
            "agency_vat_cents",
            "client_payout_cents",
            "outstanding_cents",
            "paid_amount_cents",
        ):
            if money_field in cdoc and cdoc[money_field] is not None:
                cdoc[money_field] = int(round(float(cdoc[money_field])))
        cdoc.setdefault("commission_rate_bp", 1000)
        cdoc["commission_rate_bp"] = int(cdoc["commission_rate_bp"])

    for iid, idoc in collections["inquiries"].items():
        for mfield in ("offered_gage_cents", "quoted_fee_cents"):
            if mfield in idoc and idoc[mfield] is not None:
                idoc[mfield] = int(round(float(idoc[mfield])))

    for fid, fdoc in collections["fee_matrix"].items():
        for mfield in ("last_achieved_cents", "guideline_cents", "guideline_ma_cents", "target_next_year_cents"):
            if mfield in fdoc and fdoc[mfield] is not None:
                fdoc[mfield] = int(round(float(fdoc[mfield])))

    return {
        "meta": meta,
        "collections": collections,
    }
