"""Shared types, constants, and error hierarchy for MCP XAMPP Server."""

import os
from typing import TypedDict

# --- Error Hierarchy ---


class XampError(RuntimeError):
    """Base error for all XAMPP MCP Server errors."""


class XampConnectionError(XampError):
    """Cannot connect to the database — host unreachable, port closed, or server down."""


class XampAuthError(XampError):
    """Authentication failed — wrong user or password."""


class XampTimeoutError(XampError):
    """Query or connection exceeded the configured timeout."""


class XampQueryError(XampError):
    """SQL syntax error, invalid query, or constraint violation."""


class XampDatabaseError(XampError):
    """Database not found or insufficient permissions."""


class XampWriteRejectedError(XampError):
    """Write operation blocked by the environment gate."""


class XampMissingDatabaseError(XampError):
    """The required 'database' parameter was not provided."""


# --- Constants ---

READ_KEYWORDS: frozenset[str] = frozenset({"SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "WITH"})

FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
    }
)

QUERY_TIMEOUT: int = 30

MAX_SERVER_LIMIT: int = 10_000


def _read_max_rows() -> int:
    """Read MCP_XAMP_MAX_ROWS from the environment, clamp to MAX_SERVER_LIMIT.

    - Unset → 1000 (default)
    - Non-integer string → raises ValueError at import (fail fast)
    - Value < 1 → raises ValueError at import (fail fast)
    - Value > MAX_SERVER_LIMIT → silently clamped to MAX_SERVER_LIMIT
    """
    raw = os.environ.get("MCP_XAMP_MAX_ROWS")
    if raw is None:
        return 1000
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"MCP_XAMP_MAX_ROWS must be an integer, got: {raw!r}") from None
    if value < 1:
        raise ValueError(f"MCP_XAMP_MAX_ROWS must be >= 1, got: {value}")
    return min(value, MAX_SERVER_LIMIT)


MAX_ROWS: int = _read_max_rows()


# --- Result Types ---


class QueryResult(TypedDict):
    """Structured result from a read query."""

    columns: list[str]
    rows: list[list]
    truncated: bool
