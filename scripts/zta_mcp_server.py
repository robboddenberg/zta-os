"""
ZTA-OS Executive AI Co-Pilot MCP Server (Model Context Protocol, stdio JSON-RPC 2.0).
Erlaubt Inhaberin Zetha den direkten Zugriff aus Claude Desktop auf alle 9 Playbooks (A bis I),
den Sperrtermin-Rechner (DZR), Auto-Offset-Buchungen und die Zugangsrechte-Steuerung.

Konfiguration in Claude Desktop (claude_desktop_config.json):
{
  "mcpServers": {
    "zta-os": {
      "command": "D:\\G-Drive\\Canvas\\zta-os\\.venv\\Scripts\\python.exe",
      "args": ["D:\\G-Drive\\Canvas\\zta-os\\scripts\\zta_mcp_server.py"],
      "env": {
        "ZTA_API_URL": "http://127.0.0.1:8020",
        "ZTA_TENANT_ID": "zta-berlin"
      }
    }
  }
}
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

API_BASE = os.environ.get("ZTA_API_URL", "http://127.0.0.1:8020").rstrip("/")
TENANT_ID = os.environ.get("ZTA_TENANT_ID", "zta-berlin")

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "zta_run_playbook",
        "description": (
            "Fuehrt eines der 9 operativen ZTA-OS Playbooks (A bis I) aus: "
            "weekly_briefing (A), news_triage (B), dzr_fee_check (C), booking_auto_offset (D), "
            "payroll_readiness (E), casting_radar_48h (F), annual_review_dossier (G), "
            "multi_talent_matcher (H), access_governance (I)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "playbook_id": {
                    "type": "string",
                    "description": "Playbook ID: A..I oder weekly_briefing, news_triage, dzr_fee_check, booking_auto_offset, payroll_readiness, casting_radar_48h, annual_review_dossier, multi_talent_matcher, access_governance",
                },
                "params": {
                    "type": "object",
                    "description": "Optionale Parameter wie client_id, dzr_start, dzr_end, sender_category, department, gage_cents, engagement_days.",
                },
                "confirm_gate": {
                    "type": "string",
                    "enum": ["CONFIRM", "CANCEL"],
                    "description": "Nur bei destruktiven/finanziellen Aktionen nach expliziter Nutzer-Freigabe setzen.",
                },
            },
            "required": ["playbook_id"],
        },
    },
    {
        "name": "zta_dzr_check",
        "description": "Prueft Sperrtermine (Rot/Orange), Anreisetage und Richtgage fuer eine Klient:in im angefragten Drehzeitraum (DZR).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "z. B. cl-01 oder Name"},
                "dzr_start": {"type": "string", "description": "YYYY-MM-DD"},
                "dzr_end": {"type": "string", "description": "YYYY-MM-DD"},
                "sender_category": {"type": "string", "description": "z. B. ZDF, ARD/Degeto, Streamer, Kino"},
                "project_name": {"type": "string"},
            },
            "required": ["client_id", "dzr_start", "dzr_end"],
        },
    },
    {
        "name": "zta_clients_list",
        "description": "Listet Klient:innen von ZTA Management nach Department oder Suchbegriff auf.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "actors, directors_writers, nxt, pr_commercial, consulting, all"},
                "query": {"type": "string", "description": "Name oder ID fuer unscharfe Suche"},
            },
        },
    },
    {
        "name": "zta_access_list",
        "description": "Zeigt alle Benutzerkonten, Rollen (super_admin, team_zta, klient), Portal-Status und Zugangscodes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "zta_access_update",
        "description": "Aktiviert oder sperrt den App-Zugang einer Klient:in/eines Kontos oder aendert die Rolle. Sperren erfordert confirm_gate='CONFIRM'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_id_or_client_id": {"type": "string"},
                "has_app_access": {"type": "boolean"},
                "role": {"type": "string", "enum": ["super_admin", "team_zta", "klient"]},
                "rotate_code": {"type": "boolean"},
                "confirm_gate": {"type": "string", "enum": ["CONFIRM", "CANCEL"]},
            },
            "required": ["account_id_or_client_id"],
        },
    },
    {
        "name": "zta_auto_offset",
        "description": "Fuehrt End-to-End Buchung & Auto-Offset (Vertrag final_signed, Cent-Provision, Kalender-Drehtag, Gagen-Auto-Raise) aus. Erfordert confirm_gate='CONFIRM'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "project_title": {"type": "string"},
                "gage_cents": {"type": "integer"},
                "engagement_days": {"type": "integer"},
                "commission_rate_bp": {"type": "integer"},
                "confirm_gate": {"type": "string", "enum": ["CONFIRM", "CANCEL"]},
            },
            "required": ["client_id", "project_title", "gage_cents"],
        },
    },
]


def _http_json(method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-ID": TENANT_ID,
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_text = exc.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {exc.code}", "detail": err_text}
    except Exception as exc:
        return {"error": "connection_error", "detail": str(exc)}


def _handle_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "zta_run_playbook":
        res = _http_json(
            "POST",
            "/api/copilot/playbook",
            {
                "playbook_id": args.get("playbook_id", "weekly_briefing"),
                "params": args.get("params") or {},
                "confirm_gate": args.get("confirm_gate"),
                "tenant_id": TENANT_ID,
            },
        )
    elif name == "zta_dzr_check":
        res = _http_json(
            "POST",
            "/api/copilot/playbook",
            {
                "playbook_id": "dzr_fee_check",
                "params": args,
                "tenant_id": TENANT_ID,
            },
        )
    elif name == "zta_clients_list":
        qs = urllib.parse.urlencode({k: v for k, v in args.items() if v})
        path = f"/api/clients?{qs}" if qs else "/api/clients"
        res = _http_json("GET", path)
    elif name == "zta_access_list":
        res = _http_json("GET", "/api/access/accounts")
    elif name == "zta_access_update":
        payload = dict(args)
        payload["tenant_id"] = TENANT_ID
        res = _http_json("POST", "/api/access/update", payload)
    elif name == "zta_auto_offset":
        payload = dict(args)
        payload["tenant_id"] = TENANT_ID
        res = _http_json("POST", "/api/finance/auto-offset", payload)
    else:
        res = {"error": f"Unbekanntes Tool: {name}"}

    text_out = res.get("markdown_report") if isinstance(res, dict) and res.get("markdown_report") else json.dumps(res, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": text_out}],
        "isError": bool(isinstance(res, dict) and res.get("error")),
    }


def main() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "zta-os-copilot", "version": "10.2.0"},
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = _handle_tool_call(params.get("name", ""), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            if req_id is None:
                continue
            sys.stdout.write(
                json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}) + "\n"
            )
            sys.stdout.flush()
            continue

        if req_id is not None:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
