"""Unit tests for types.py — MAX_ROWS env-var computation (B4.4)."""

import importlib

import pytest


def _reload_read_max_rows(monkeypatch, env_value: str | None) -> int:
    """Set or clear MCP_XAMP_MAX_ROWS and re-evaluate _read_max_rows().

    We import and call ``_read_max_rows`` directly rather than reloading the
    module so that other constants (error classes, READ_KEYWORDS, …) are not
    re-created and tests stay isolated.
    """
    if env_value is None:
        monkeypatch.delenv("MCP_XAMP_MAX_ROWS", raising=False)
    else:
        monkeypatch.setenv("MCP_XAMP_MAX_ROWS", env_value)

    # Re-import to get a fresh binding, but call the helper directly.
    import mcp_xamp.types as t

    importlib.reload(t)  # re-runs module-level code with new env
    return t.MAX_ROWS


class TestReadMaxRows:
    def test_default_when_env_unset(self, monkeypatch) -> None:
        """Unset MCP_XAMP_MAX_ROWS → MAX_ROWS defaults to 1000."""
        result = _reload_read_max_rows(monkeypatch, None)
        assert result == 1000

    def test_custom_valid_value(self, monkeypatch) -> None:
        """Valid integer env → MAX_ROWS equals that value."""
        result = _reload_read_max_rows(monkeypatch, "500")
        assert result == 500

    def test_clamped_to_max_server_limit(self, monkeypatch) -> None:
        """Value > MAX_SERVER_LIMIT (10000) is silently clamped."""
        result = _reload_read_max_rows(monkeypatch, "15000")
        assert result == 10_000

    def test_exact_max_server_limit_accepted(self, monkeypatch) -> None:
        """Value == MAX_SERVER_LIMIT is accepted without clamping."""
        result = _reload_read_max_rows(monkeypatch, "10000")
        assert result == 10_000

    def test_non_integer_raises_at_import(self, monkeypatch) -> None:
        """Non-integer string → ValueError raised at module import time."""
        monkeypatch.setenv("MCP_XAMP_MAX_ROWS", "abc")
        import mcp_xamp.types as t

        with pytest.raises(ValueError, match="integer"):
            importlib.reload(t)

    def test_zero_raises_at_import(self, monkeypatch) -> None:
        """MCP_XAMP_MAX_ROWS=0 → ValueError at import (fail fast)."""
        monkeypatch.setenv("MCP_XAMP_MAX_ROWS", "0")
        import mcp_xamp.types as t

        with pytest.raises(ValueError, match=">= 1"):
            importlib.reload(t)

    def test_negative_raises_at_import(self, monkeypatch) -> None:
        """Negative value → ValueError at import."""
        monkeypatch.setenv("MCP_XAMP_MAX_ROWS", "-5")
        import mcp_xamp.types as t

        with pytest.raises(ValueError, match=">= 1"):
            importlib.reload(t)

    def test_value_one_accepted(self, monkeypatch) -> None:
        """MCP_XAMP_MAX_ROWS=1 is the minimum valid value."""
        result = _reload_read_max_rows(monkeypatch, "1")
        assert result == 1
