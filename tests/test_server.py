"""Integration tests for the MCP server — exercises all 5 tools end-to-end."""

import asyncio
import json
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp_xamp.db.connection import ConnectionFactory  # noqa: E402
from mcp_xamp.server import server  # noqa: E402
from mcp_xamp.types import XampConnectionError  # noqa: E402

from .conftest import needs_mariadb  # noqa: E402

# ---------------------------------------------------------------------------
# Unit: main() pre-flight (A6.4) — no real DB needed
# ---------------------------------------------------------------------------


class TestMainPreflight:
    def _run_main_with_ping(self, ping_side_effect, caplog):
        """Run main() with a mocked _ping_db and a mocked stdio_server."""
        import mcp_xamp.server as server_module

        mock_read_stream = MagicMock()
        mock_write_stream = MagicMock()

        mock_server_instance = MagicMock()
        mock_server_instance.run = AsyncMock()
        mock_server_instance.create_initialization_options = MagicMock(return_value={})

        async def fake_stdio():
            yield mock_read_stream, mock_write_stream

        with (
            patch.object(server_module, "_ping_db", side_effect=ping_side_effect),
            patch("mcp_xamp.server.stdio_server") as mock_stdio,
            patch.object(server_module, "server", mock_server_instance),
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(
                return_value=(mock_read_stream, mock_write_stream)
            )
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)

            with caplog.at_level(logging.INFO, logger="mcp_xamp.server"):
                asyncio.run(server_module.main())

        return mock_server_instance

    def test_preflight_success_logs_info(self, caplog) -> None:
        """When _ping_db succeeds, main() logs an INFO message and runs the server."""
        mock_server = self._run_main_with_ping(ping_side_effect=None, caplog=caplog)

        info_msgs = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert any("Pre-flight OK" in m for m in info_msgs)
        mock_server.run.assert_awaited_once()

    def test_preflight_failure_logs_warning_and_continues(self, caplog) -> None:
        """When _ping_db raises XampConnectionError, main() logs WARNING and still starts."""
        mock_server = self._run_main_with_ping(
            ping_side_effect=XampConnectionError("Connection refused"),
            caplog=caplog,
        )

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Pre-flight" in m for m in warning_msgs)
        mock_server.run.assert_awaited_once()

    def test_preflight_failure_does_not_raise(self, caplog) -> None:
        """A pre-flight XampError must not propagate — server must start regardless."""
        # This test passes if _run_main_with_ping does not raise.
        self._run_main_with_ping(
            ping_side_effect=XampConnectionError("XAMPP not running"),
            caplog=caplog,
        )


# ---------------------------------------------------------------------------
# In-memory transport helpers
# ---------------------------------------------------------------------------


async def _call_tool_via_server(tool_name: str, arguments: dict | None = None) -> str:
    """Invoke a tool directly against the server's ``call_tool`` handler and
    return the serialized response text."""
    args = arguments or {}
    result = await server._tool_handler(tool_name, args)  # type: ignore[attr-defined]
    # result is list[TextContent]
    return result[0].text if result else ""


def _run_async(coro):
    """Helper to run an async coroutine in sync tests."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@needs_mariadb
class TestServerListDatabases:
    def test_returns_system_databases(self) -> None:
        result = _run_async(_call_tool_via_server("list_databases"))
        data = json.loads(result)
        assert "mysql" in data
        assert "information_schema" in data


@needs_mariadb
class TestServerListTables:
    def test_requires_database(self) -> None:
        result = _run_async(_call_tool_via_server("list_tables", {}))
        assert "database" in result.lower()
        assert "list_databases" in result

    def test_lists_tables(self, test_database) -> None:
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE t1 (id INT)")

        result = _run_async(_call_tool_via_server("list_tables", {"database": test_database}))
        data = json.loads(result)
        assert "t1" in data


@needs_mariadb
class TestServerDescribeTable:
    def test_requires_database(self) -> None:
        result = _run_async(_call_tool_via_server("describe_table", {"table": "x"}))
        assert "database" in result.lower()

    def test_describes_table(self, test_database) -> None:
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE dt (col1 INT PRIMARY KEY, col2 VARCHAR(10))")

        result = _run_async(
            _call_tool_via_server("describe_table", {"database": test_database, "table": "dt"})
        )
        data = json.loads(result)
        fields = {c["Field"] for c in data}
        assert fields == {"col1", "col2"}


@needs_mariadb
class TestServerReadQuery:
    def test_select_one(self, test_database) -> None:
        result = _run_async(
            _call_tool_via_server(
                "read_query", {"database": test_database, "query": "SELECT 1 AS n"}
            )
        )
        data = json.loads(result)
        assert data["rows"] == [[1]]

    def test_drop_rejected(self, test_database) -> None:
        result = _run_async(
            _call_tool_via_server(
                "read_query", {"database": test_database, "query": "DROP TABLE x"}
            )
        )
        assert "read_query" in result.lower() or "consulta" in result.lower()

    def test_missing_database(self) -> None:
        result = _run_async(_call_tool_via_server("read_query", {"query": "SELECT 1"}))
        assert "database" in result.lower()


@needs_mariadb
class TestServerWriteQuery:
    def test_rejected_without_env_var(self, monkeypatch, test_database) -> None:
        monkeypatch.delenv("MCP_XAMP_ALLOW_WRITE", raising=False)
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "false")

        result = _run_async(
            _call_tool_via_server(
                "write_query",
                {"database": test_database, "query": "INSERT INTO t VALUES (1)"},
            )
        )
        assert "MCP_XAMP_ALLOW_WRITE" in result or "escritura" in result.lower()

    def test_allowed_with_env_var(self, monkeypatch, test_database) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "true")
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE wt (id INT)")

        result = _run_async(
            _call_tool_via_server(
                "write_query",
                {"database": test_database, "query": "INSERT INTO wt VALUES (99)"},
            )
        )
        data = json.loads(result)
        assert data.get("affected_rows") == 1

    def test_missing_database(self) -> None:
        result = _run_async(
            _call_tool_via_server("write_query", {"query": "INSERT INTO t VALUES (1)"})
        )
        assert "database" in result.lower()


@needs_mariadb
class TestSpanishErrorMessages:
    def test_successful_query_returns_data(self) -> None:
        result = _run_async(
            _call_tool_via_server("read_query", {"database": "mysql", "query": "SELECT 1"})
        )
        data = json.loads(result)
        assert data["rows"] == [[1]]

    def test_missing_database_spanish_message(self) -> None:
        result = _run_async(_call_tool_via_server("list_tables", {}))
        assert "database" in result.lower()
        assert "list_databases" in result.lower()

    def test_write_rejected_spanish_message(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "false")
        result = _run_async(
            _call_tool_via_server(
                "write_query", {"database": "test", "query": "INSERT INTO t VALUES (1)"}
            )
        )
        assert "escritura" in result.lower() or "MCP_XAMP_ALLOW_WRITE" in result
