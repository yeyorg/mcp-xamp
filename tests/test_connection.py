"""Tests for ConnectionFactory — env-var parsing (unit) and real connections (integration)."""


import pytest

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.types import XampAuthError, XampConnectionError

from .conftest import needs_mariadb

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
        with pytest.raises((XampAuthError, XampConnectionError)), factory.connect(
            database="mysql"
        ):
            pass
