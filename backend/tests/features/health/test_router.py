from unittest.mock import MagicMock

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_session
from app.features.health.router import get_readiness_storage
from app.features.photos.storage import PhotoStorage, StorageStatus, StorageStatusCode
from app.main import create_app


class ReadinessStorage(PhotoStorage):
    def __init__(self, available: bool = True) -> None:
        self.available = available

    def get_read_status(self) -> StorageStatus:
        return StorageStatus(
            status=StorageStatusCode.AVAILABLE if self.available else StorageStatusCode.ROOT_NOT_FOUND,
            writable=False,
            free_bytes=None,
            minimum_free_bytes=None,
        )


@pytest.mark.anyio
async def test_get_root_returns_api_links() -> None:
    app = create_app(Settings(app_env="test"))
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Photo storage API is running",
        "health": "/api/v1/health",
        "docs": "/docs",
    }


@pytest.mark.anyio
async def test_get_health_returns_ok() -> None:
    app = create_app(Settings(app_env="test"))
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "private, no-store"
    assert len(response.headers["x-request-id"]) == 36


@pytest.mark.anyio
async def test_get_readiness_checks_database_and_photo_storage() -> None:
    app = create_app(Settings(app_env="test"))
    session = MagicMock(spec=Session)

    async def override_session() -> Session:
        return session

    async def override_storage() -> PhotoStorage:
        return ReadinessStorage()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_readiness_storage] = override_storage
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "available",
        "photo_storage": "available",
    }
    session.execute.assert_called_once()


@pytest.mark.anyio
async def test_get_readiness_returns_503_when_photo_storage_is_unavailable() -> None:
    app = create_app(Settings(app_env="test"))
    session = MagicMock(spec=Session)

    async def override_session() -> Session:
        return session

    async def override_storage() -> PhotoStorage:
        return ReadinessStorage(available=False)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_readiness_storage] = override_storage
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/readiness")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


@pytest.mark.anyio
async def test_lifespan_exposes_settings() -> None:
    settings = Settings(app_env="test")
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        assert app.state.settings is settings
