from app.core.config import Settings
from app.features.auth.dependencies import require_system_admin
from app.features.maintenance.router import router
from app.main import create_app


def test_maintenance_status_route_is_registered_and_admin_only() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "get" in paths["/api/v1/admin/maintenance/status"]
    assert any(dependency.dependency is require_system_admin for dependency in router.dependencies)
