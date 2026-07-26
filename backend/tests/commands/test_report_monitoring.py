from unittest.mock import MagicMock

import pytest

from app.commands import report_monitoring


def test_report_is_disabled_without_job_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MONITORING_PING_URL_DB_BACKUP", raising=False)

    assert report_monitoring.report("db-backup", "start") is False


def test_report_uses_healthchecks_compatible_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONITORING_PING_URL_DB_BACKUP", "https://monitor.example/ping/check-id")
    response = MagicMock(status=200)
    context = MagicMock()
    context.__enter__.return_value = response
    monkeypatch.setattr(report_monitoring, "urlopen", MagicMock(return_value=context))

    assert report_monitoring.report("db-backup", "failure") is True

    request = report_monitoring.urlopen.call_args.args[0]
    assert request.full_url == "https://monitor.example/ping/check-id/fail"
    assert request.method == "POST"


def test_report_rejects_cleartext_remote_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONITORING_PING_URL_DB_BACKUP", "http://monitor.example/ping/check-id")

    with pytest.raises(ValueError):
        report_monitoring.report("db-backup", "success")
