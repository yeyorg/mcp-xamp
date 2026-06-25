"""Tests for ConnectionFactory — env-var parsing (unit) and real connections (integration)."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.types import QUERY_TIMEOUT, XampAuthError, XampConnectionError  # noqa: F401

from .conftest import needs_mariadb

# ---------------------------------------------------------------------------
# Unit: QUERY_TIMEOUT wiring (A1.3)
# ---------------------------------------------------------------------------


class TestQueryTimeoutWiring:
    def test_read_timeout_uses_query_timeout_constant(self) -> None:
        """pymysql.connect must receive read_timeout=QUERY_TIMEOUT, not a literal."""
        factory = ConnectionFactory()
        captured_kwargs: dict = {}

        def fake_connect(**kwargs):
            captured_kwargs.update(kwargs)
            mock_conn = MagicMock()
            mock_conn.__enter__ = lambda s: s
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.close = MagicMock()
            mock_conn.open = True
            return mock_conn

        with patch("pymysql.connect", side_effect=fake_connect), factory.connect(database="test"):
            pass

        assert "read_timeout" in captured_kwargs
        assert captured_kwargs["read_timeout"] == QUERY_TIMEOUT

    def test_read_timeout_value_matches_types_constant(self) -> None:
        """The value passed must equal whatever types.QUERY_TIMEOUT resolves to."""
        from mcp_xamp import types

        factory = ConnectionFactory()
        captured_kwargs: dict = {}

        def fake_connect(**kwargs):
            captured_kwargs.update(kwargs)
            mock_conn = MagicMock()
            mock_conn.__enter__ = lambda s: s
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.close = MagicMock()
            mock_conn.open = True
            return mock_conn

        with patch("pymysql.connect", side_effect=fake_connect), factory.connect(database="test"):
            pass

        assert captured_kwargs["read_timeout"] == types.QUERY_TIMEOUT


# ---------------------------------------------------------------------------
# Unit: ping() (A6.3)
# ---------------------------------------------------------------------------


class TestPing:
    def test_ping_success_returns_none(self) -> None:
        """ping() should return None when the connection succeeds."""
        factory = ConnectionFactory()

        @contextmanager
        def fake_connect(database):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            yield mock_conn

        with patch.object(factory, "connect", side_effect=fake_connect):
            result = factory.ping()

        assert result is None

    def test_ping_propagates_connection_error(self) -> None:
        """ping() should let XampConnectionError propagate to the caller."""
        factory = ConnectionFactory()

        @contextmanager
        def failing_connect(database):
            raise XampConnectionError("Cannot reach DB")
            yield  # make it a generator

        with (
            patch.object(factory, "connect", side_effect=failing_connect),
            pytest.raises(XampConnectionError),
        ):
            factory.ping()


# ---------------------------------------------------------------------------
# Unit: from_env()
# ---------------------------------------------------------------------------


class TestFromEnvDefaults:
    def test_all_defaults(self, monkeypatch) -> None:
        for var in ("MCP_XAMP_HOST", "MCP_XAMP_PORT", "MCP_XAMP_USER", "MCP_XAMP_PASSWORD"):
            monkeypatch.delenv(var, raising=False)

        f = ConnectionFactory.from_env()
        assert f.host == "127.0.0.1"
        assert f.port == 3306
        assert f.user == "root"
        assert f.password == ""

    def test_custom_values(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_HOST", "db.example.com")
        monkeypatch.setenv("MCP_XAMP_PORT", "3307")
        monkeypatch.setenv("MCP_XAMP_USER", "agent")
        monkeypatch.setenv("MCP_XAMP_PASSWORD", "s3cret")

        f = ConnectionFactory.from_env()
        assert f.host == "db.example.com"
        assert f.port == 3307
        assert f.user == "agent"
        assert f.password == "s3cret"

    def test_partial_override(self, monkeypatch) -> None:
        monkeypatch.delenv("MCP_XAMP_HOST", raising=False)
        monkeypatch.delenv("MCP_XAMP_PORT", raising=False)
        monkeypatch.delenv("MCP_XAMP_USER", raising=False)
        monkeypatch.setenv("MCP_XAMP_PASSWORD", "my_pass")

        f = ConnectionFactory.from_env()
        assert f.host == "127.0.0.1"
        assert f.port == 3306
        assert f.user == "root"
        assert f.password == "my_pass"


class TestFromEnvInvalidPort:
    def test_non_numeric_port_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_PORT", "abc")
        with pytest.raises(ValueError):
            ConnectionFactory.from_env()


# ---------------------------------------------------------------------------
# Integration: real connections
# ---------------------------------------------------------------------------


@needs_mariadb
class TestConnectionIntegration:
    def test_valid_connection(self, connection_factory) -> None:
        with connection_factory.connect(database="mysql") as conn:
            assert conn.open is True
        # After context exit the connection should be closed
        assert conn.open is False  # type: ignore[possibly-undefined]

    def test_invalid_host_raises_connection_error(self) -> None:
        factory = ConnectionFactory(
            host="does.not.exist.local", port=3306, user="root", password=""
        )
        with pytest.raises(XampConnectionError), factory.connect(database="mysql"):
            pass

    def test_invalid_password_raises_auth_error(self) -> None:
        factory = ConnectionFactory.from_env()
        factory.password = "wrong_password_xyz_12345"
        with pytest.raises((XampAuthError, XampConnectionError)), factory.connect(database="mysql"):
            pass
