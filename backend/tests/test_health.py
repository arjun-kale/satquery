import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.api.health import health
from app.config import Settings
from app.main import create_app


def test_health_reports_database_and_model_mode(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "satquery.db",
        model_mode="mock",
    )
    app = create_app(settings)

    async def invoke_health() -> dict[str, str]:
        async with app.router.lifespan_context(app):
            response = health(SimpleNamespace(app=app))
            return response.model_dump()

    response = asyncio.run(invoke_health())

    assert any(getattr(route, "path", None) == "/health" for route in app.routes)
    assert response == {"status": "ok", "database": "ok", "model_mode": "mock"}
    assert settings.database_path.exists()
