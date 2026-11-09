"""Tests fuer atomare Persistenz, Backup-Rotation (.bak.1..5), 409-Konflikte und Drive-Sync-Schutz."""
from __future__ import annotations

from pathlib import Path
import pytest

from backend.app.storage import RevisionConflictError, StorageCorruptedError, StorageEngine


def test_atomic_write_and_backup_rotation(tmp_path: Path) -> None:
    data_file = tmp_path / "data.json"
    engine = StorageEngine(data_file)

    for i in range(1, 8):
        state = engine.mutate_document(
            collection="clients",
            doc_id=f"cl-{i:02d}",
            op="set",
            data={"name": f"Talent {i}", "division": "schauspiel"},
        )
        assert state["meta"]["revision"] == i

    # Es muessen genau .bak.1 bis .bak.5 existieren
    for slot in range(1, 6):
        assert (tmp_path / f"data.json.bak.{slot}").exists()
    assert not (tmp_path / "data.json.bak.6").exists()


def test_optimistic_locking_raises_409_conflict(tmp_path: Path) -> None:
    data_file = tmp_path / "data.json"
    engine = StorageEngine(data_file)

    s1 = engine.mutate_document("clients", "cl-01", "set", {"name": "Mara"})
    assert s1["meta"]["revision"] == 1

    with pytest.raises(RevisionConflictError) as exc_info:
        engine.mutate_document("clients", "cl-01", "update", {"location": "Hamburg"}, if_revision=0)

    assert exc_info.value.expected_revision == 0
    assert exc_info.value.current_state["meta"]["revision"] == 1


def test_corrupted_file_is_never_overwritten(tmp_path: Path) -> None:
    data_file = tmp_path / "data.json"
    engine = StorageEngine(data_file)
    engine.mutate_document("clients", "cl-01", "set", {"name": "Mara"})
    engine.mutate_document("clients", "cl-02", "set", {"name": "Tarik"})

    # Korrupte Datei simulieren
    data_file.write_text("{ungueltiges json", encoding="utf-8")

    with pytest.raises(StorageCorruptedError) as exc_info:
        engine.read_state()

    assert exc_info.value.latest_backup == "data.json.bak.1"


def test_detect_google_drive_sync_conflicts(tmp_path: Path) -> None:
    data_file = tmp_path / "data.json"
    engine = StorageEngine(data_file)
    engine.mutate_document("clients", "cl-01", "set", {"name": "Mara"})

    (tmp_path / "data (1).json").write_text("{}", encoding="utf-8")
    (tmp_path / "data conflicted copy.json").write_text("{}", encoding="utf-8")

    conflicts = engine.detect_sync_conflicts()
    assert "data (1).json" in conflicts
    assert "data conflicted copy.json" in conflicts
