"""Strikte Pydantic v2 Modelle und Schema-Migration fuer ZTA OS."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

KNOWN_COLLECTIONS = (
    "clients",
    "calendar_events",
    "inquiries",
    "castings",
    "contracts",
    "time_logs",
    "feedback_items",
    "audit_logs",
    "settings",
)

DivisionType = Literal["schauspiel", "regie_drehbuch", "nxt", "pr_commercial"]
CalendarEventType = Literal["sperr", "option", "dzr", "dt", "nachsyn", "aufnahme", "casting"]
InquiryStatus = Literal["open", "checked", "optioned", "confirmed", "declined"]
ClientResponseType = Literal["pending", "fits", "declined", "question"]
ContractStatus = Literal["draft", "negotiation", "final_signed", "invoiced", "paid", "cancelled"]
FeedbackStatus = Literal[
    "neu",
    "angenommen",
    "zurueckgestellt",
    "abgelehnt",
    "in_arbeit",
    "umgesetzt_zu_pruefen",
    "erledigt",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MutateRequest(BaseModel):
    collection: str
    doc_id: str
    op: Literal["set", "update", "delete"]
    data: Optional[Dict[str, Any]] = None
    if_revision: Optional[int] = None
    actor_role: str = "inhaberin"
    actor_id: str = "user-zetha"


class StateWriteRequest(BaseModel):
    collections: Dict[str, Dict[str, Any]]
    if_revision: Optional[int] = None


class ClientFilterQuery(BaseModel):
    start_date: str
    end_date: str
    division: Optional[str] = None
    include_options: bool = True
    tenant_id: str = "zta-berlin"


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
    title: str = "Privat / Sperrtermin"
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
    division: DivisionType = "schauspiel"
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


def migrate_schema(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Stellt sicher, dass das State-Dokument alle Pflicht-Collections und Meta-Felder besitzt."""
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

    # Sicherstellen, dass Geldbetraege in contracts & inquiries immer Ganzzahlen (Cent) sind
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
        if "offered_gage_cents" in idoc and idoc["offered_gage_cents"] is not None:
            idoc["offered_gage_cents"] = int(round(float(idoc["offered_gage_cents"])))
        else:
            idoc["offered_gage_cents"] = 0

    return {
        "meta": meta,
        "collections": collections,
    }
