import pytest

from app.core import config as config_module
from app.core.config import Settings


@pytest.fixture(autouse=True)
def isolate_application_environment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Keep developer and deployment settings from leaking into unit tests."""
    monkeypatch.setattr(config_module, "BACKEND_ENV_FILE", tmp_path / ".env")
    for field_name in Settings.model_fields:
        monkeypatch.delenv(field_name, raising=False)
        monkeypatch.delenv(field_name.upper(), raising=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
