"""Atomare Dateipersistenz mit Backup-Rotation (.bak.1..5), 409-Revisionen und Konflikterkennung."""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import KNOWN_COLLECTIONS, migrate_schema, utc_now_iso

MAX_BACKUPS = 5

CONFLICT_PATTERNS = (
    re.compile(r".*\(\d+\)\.json$", re.IGNORECASE),
    re.compile(r".*conflicted copy.*", re.IGNORECASE),
    re.compile(r".*konfliktkopie.*", re.IGNORECASE),
    re.compile(r".*conflict.*", re.IGNORECASE),
)


class StorageCorruptedError(Exception):
    """Wird ausgeloest, wenn data.json beschaedigt oder unlesbar ist."""

    def __init__(self, message: str, latest_backup: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.latest_backup = latest_backup


class RevisionConflictError(Exception):
    """Wird ausgeloest, wenn if_revision nicht mit meta.revision uebereinstimmt (HTTP 409)."""

    def __init__(self, expected_revision: int, current_state: Dict[str, Any]):
        super().__init__(
            f"Revision conflict: client sent {expected_revision}, "
            f"but current revision is {current_state['meta']['revision']}"
        )
        self.expected_revision = expected_revision
        self.current_state = current_state


class StorageEngine:
    """Thread-sichere, Google-Drive-kompatible Storage-Engine ohne In-Memory-Cache als Wahrheit."""

    def __init__(self, data_path: Path):
        self.data_path = Path(data_path).resolve()
        self.data_dir = self.data_path.parent
        self.files_dir = self.data_dir / "files"
        self._lock = threading.RLock()

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def _empty_state(self) -> Dict[str, Any]:
        return migrate_schema(
            {
                "meta": {
                    "schema_version": 1,
                    "revision": 0,
                    "updated_at": utc_now_iso(),
                    "default_tenant_id": "zta-berlin",
                },
                "collections": {col: {} for col in KNOWN_COLLECTIONS},
            }
        )

    def find_latest_backup(self) -> Optional[str]:
        for i in range(1, MAX_BACKUPS + 1):
            bak = self.data_path.with_name(f"{self.data_path.name}.bak.{i}")
            if bak.exists():
                return bak.name
        return None

    def list_backups(self) -> List[Dict[str, Any]]:
        backups: List[Dict[str, Any]] = []
        for i in range(1, MAX_BACKUPS + 1):
            bak = self.data_path.with_name(f"{self.data_path.name}.bak.{i}")
            if bak.exists():
                stat = bak.stat()
                backups.append(
                    {
                        "slot": i,
                        "filename": bak.name,
                        "size_bytes": stat.st_size,
                    }
                )
        return backups

    def detect_sync_conflicts(self) -> List[str]:
        if not self.data_dir.exists():
            return []
        conflicts: List[str] = []
        stem = self.data_path.stem.lower()
        for entry in self.data_dir.iterdir():
            if not entry.is_file():
                continue
            name = entry.name
            if name == self.data_path.name:
                continue
            if ".bak." in name or ".tmp." in name:
                continue
            lower = name.lower()
            if stem in lower and any(pat.match(name) for pat in CONFLICT_PATTERNS):
                conflicts.append(name)
        return sorted(conflicts)

    def read_state(self) -> Dict[str, Any]:
        with self._lock:
            if not self.data_path.exists():
                return self._empty_state()
            try:
                raw_bytes = self.data_path.read_bytes()
                if not raw_bytes.strip():
                    raise ValueError("Datei ist leer (0 Bytes)")
                raw_data = json.loads(raw_bytes.decode("utf-8"))
                return migrate_schema(raw_data)
            except Exception as exc:
                latest_bak = self.find_latest_backup()
                hint = (
                    f"Letztes verfuegbares Backup: {latest_bak}"
                    if latest_bak
                    else "Kein Backup im Datenordner gefunden."
                )
                raise StorageCorruptedError(
                    f"Die Datendatei '{self.data_path.name}' ist beschaedigt oder unlesbar "
                    f"und wurde zum Schutz nicht ueberschrieben. ({hint})",
                    latest_backup=latest_bak,
                ) from exc

    def has_any_data(self) -> bool:
        if not self.data_path.exists():
            return False
        state = self.read_state()
        cols = state.get("collections", {})
        return any(
            bool(cols.get(col))
            for col in ("clients", "calendar_events", "inquiries", "castings", "contracts")
        )

    def _rotate_backups(self) -> None:
        if not self.data_path.exists():
            return
        _ = self.read_state()
        for i in range(MAX_BACKUPS - 1, 0, -1):
            src = self.data_path.with_name(f"{self.data_path.name}.bak.{i}")
            dst = self.data_path.with_name(f"{self.data_path.name}.bak.{i + 1}")
            if src.exists():
                os.replace(src, dst)
        bak1 = self.data_path.with_name(f"{self.data_path.name}.bak.1")
        shutil.copy2(self.data_path, bak1)

    def _atomic_write(
        self,
        state: Dict[str, Any],
        before_replace_hook: Optional[Callable[[Path], None]] = None,
    ) -> None:
        self.ensure_dirs()
        tmp_name = f"{self.data_path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
        tmp_path = self.data_dir / tmp_name
        payload = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")

        try:
            with open(tmp_path, "wb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            if before_replace_hook is not None:
                before_replace_hook(tmp_path)
            os.replace(tmp_path, self.data_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def write_new_state(
        self,
        collections: Dict[str, Dict[str, Dict[str, Any]]],
        if_revision: Optional[int] = None,
        before_replace_hook: Optional[Callable[[Path], None]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            current = self.read_state()
            cur_rev = int(current["meta"].get("revision", 0))

            if if_revision is not None and if_revision != cur_rev:
                raise RevisionConflictError(if_revision, current)

            self._rotate_backups()

            next_state = migrate_schema(
                {
                    "meta": {
                        "schema_version": current["meta"].get("schema_version", 1),
                        "revision": cur_rev + 1,
                        "updated_at": utc_now_iso(),
                        "default_tenant_id": current["meta"].get("default_tenant_id", "zta-berlin"),
                    },
                    "collections": collections,
                }
            )
            self._atomic_write(next_state, before_replace_hook=before_replace_hook)
            return next_state

    def mutate_document(
        self,
        collection: str,
        doc_id: str,
        op: str,
        data: Optional[Dict[str, Any]] = None,
        if_revision: Optional[int] = None,
        actor_role: str = "inhaberin",
        actor_id: str = "user-zetha",
    ) -> Dict[str, Any]:
        if collection not in KNOWN_COLLECTIONS:
            raise ValueError(f"Unbekannte Collection: {collection}")

        with self._lock:
            current = self.read_state()
            cur_rev = int(current["meta"].get("revision", 0))

            if if_revision is not None and if_revision != cur_rev:
                raise RevisionConflictError(if_revision, current)

            cols = current["collections"]
            col_map = cols.setdefault(collection, {})

            if op == "set":
                clean = dict(data or {})
                clean.pop("id", None)
                clean.setdefault("updated_at", utc_now_iso())
                col_map[doc_id] = clean
            elif op == "update":
                existing = dict(col_map.get(doc_id, {}))
                patch = dict(data or {})
                patch.pop("id", None)
                existing.update(patch)
                existing["updated_at"] = utc_now_iso()
                col_map[doc_id] = existing
            elif op == "delete":
                col_map.pop(doc_id, None)
            else:
                raise ValueError(f"Nicht unterstuetzte Operation: {op}")

            # Audit-Trail mitschreiben (ausser wenn audit_logs selbst mutiert wird)
            if collection != "audit_logs":
                audit_id = f"aud-{uuid.uuid4().hex[:10]}"
                cols.setdefault("audit_logs", {})[audit_id] = {
                    "timestamp": utc_now_iso(),
                    "collection": collection,
                    "doc_id": doc_id,
                    "op": op,
                    "actor_role": actor_role,
                    "actor_id": actor_id,
                    "tenant_id": current["meta"].get("default_tenant_id", "zta-berlin"),
                }

            return self.write_new_state(cols, if_revision=cur_rev)
