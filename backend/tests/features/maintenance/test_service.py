from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.features.maintenance.models import MaintenanceRun, MaintenanceRunStatus
from app.features.maintenance.service import MaintenanceService
from app.features.photos.public import PhotoStorage


def test_fail_run_records_terminal_failure_without_exception_details() -> None:
    session = MagicMock(spec=Session)
    storage = MagicMock(spec=PhotoStorage)
    service = MaintenanceService(session, storage)
    run = MagicMock(spec=MaintenanceRun)

    result = service.fail_run(run, error_code="photo_integrity_failed", error=OSError("secret path"))

    assert result is run
    assert run.status is MaintenanceRunStatus.FAILED
    assert run.finished_at is not None
    assert run.error_code == "photo_integrity_failed"
    assert run.error_message == "OSError"
    assert run.summary == {}
    session.commit.assert_called_once_with()
