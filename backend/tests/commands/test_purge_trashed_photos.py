import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.commands import purge_trashed_photos


def test_main_constructs_trash_service_with_retention_days(monkeypatch) -> None:
    settings = SimpleNamespace(photo_trash_retention_days=30)
    engine = MagicMock()
    session = MagicMock()
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    maintenance = MagicMock()
    maintenance.start_run.return_value = "run-id"
    trash_service = MagicMock()
    trash_service.purge_due_photos.return_value = 2

    monkeypatch.setattr(purge_trashed_photos, "get_management_settings", lambda: settings)
    monkeypatch.setattr(purge_trashed_photos, "create_database_engine", lambda value: engine)
    monkeypatch.setattr(purge_trashed_photos, "Session", lambda value, **kwargs: session_context)
    monkeypatch.setattr(purge_trashed_photos, "PhotoStorage", lambda value: "storage")
    monkeypatch.setattr(purge_trashed_photos, "MaintenanceService", lambda session, storage: maintenance)
    photo_trash_service = MagicMock(return_value=trash_service)
    monkeypatch.setattr(purge_trashed_photos, "PhotoTrashService", photo_trash_service)
    monkeypatch.setattr(sys, "argv", ["purge_trashed_photos"])

    purge_trashed_photos.main()

    photo_trash_service.assert_called_once_with(session, "storage", 30)
    trash_service.purge_due_photos.assert_called_once_with(limit=100)
