from __future__ import annotations

from app.core.models import ReleaseEffort
from app.services.db_service import DBService


def test_connection_uses_built_connection_string(monkeypatch) -> None:
    """Verifies connection uses built connection string."""
    captured: dict[str, str] = {}

    def fake_connect(conn_str: str):
        captured["conn_str"] = conn_str
        return object()

    monkeypatch.setattr("app.services.db_service.pyodbc.connect", fake_connect)

    service = DBService(
        {
            "driver": "ODBC Driver 17 for SQL Server",
            "server": "server-name",
            "database": "db-name",
        }
    )

    assert service.connection() is not None
    assert captured["conn_str"] == service.conn_str


def test_build_effort_lookup_returns_effort_by_uppercase_id() -> None:
    """Verifies build effort lookup returns effort by uppercase id."""
    effort = ReleaseEffort(effort_id="abc123")
    service = DBService({})

    lookup = service.build_effort_lookup([effort])

    assert lookup == {"ABC123": effort}
