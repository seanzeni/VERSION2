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


def test_load_system_region_lookup_uses_first_region_per_system() -> None:
    """Verifies MiscEnvironmentSystem lookup keeps the first region per system."""

    class Row:
        def __init__(
            self,
            system: str,
            region: str,
        ) -> None:
            self.System = system
            self.Region = region

    class Cursor:
        query = ""

        def execute(
            self,
            query: str,
        ) -> None:
            self.query = query

        def fetchall(
            self,
        ):
            return [
                Row("SHARED01", "DV9"),
                Row("SHARED01", "DV8"),
                Row("PRIVATE0", "DV7"),
            ]

    class Connection:
        def __init__(
            self,
        ) -> None:
            self.cursor_value = Cursor()

        def __enter__(
            self,
        ):
            return self

        def __exit__(
            self,
            *args,
        ) -> None:
            return None

        def cursor(
            self,
        ) -> Cursor:
            return self.cursor_value

    service = DBService({})
    connection = Connection()
    service.get_connection = lambda: connection

    lookup = service.load_system_region_lookup()

    assert lookup == {
        "SHARED01": "DV9",
        "PRIVATE0": "DV7",
    }
    assert "MiscEnvironmentSystem" in connection.cursor_value.query
    assert "'DEVL1', 'MAIN1'" in connection.cursor_value.query
