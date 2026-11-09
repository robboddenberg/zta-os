"""Konfiguration fuer ZTA OS ueber Umgebungsvariablen."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_version: str
    root_dir: Path
    data_path: Path
    frontend_dir: Path
    port: int
    default_tenant_id: str
    webhook_secret: str
    gemini_api_key: str
    gemini_model: str


def load_config() -> AppConfig:
    raw_data_path = os.environ.get("DATA_PATH", "").strip()
    if raw_data_path:
        data_path = Path(raw_data_path)
        if not data_path.is_absolute():
            data_path = (ROOT_DIR / data_path).resolve()
    else:
        data_path = (ROOT_DIR / "data" / "data.json").resolve()

    port = int(os.environ.get("PORT", "8020"))
    default_tenant_id = os.environ.get("DEFAULT_TENANT_ID", "zta-berlin").strip() or "zta-berlin"
    webhook_secret = os.environ.get("WEBHOOK_SECRET", "zta-local-webhook-secret").strip()
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    return AppConfig(
        app_name="ZTA OS",
        app_version="1.0.0",
        root_dir=ROOT_DIR,
        data_path=data_path,
        frontend_dir=ROOT_DIR / "frontend",
        port=port,
        default_tenant_id=default_tenant_id,
        webhook_secret=webhook_secret,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
    )
