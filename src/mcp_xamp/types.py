"""Shared types, constants, and error hierarchy for MCP XAMPP Server."""

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

FORBIDDEN_KEYWORDS: frozenset[str] = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "GRANT", "REVOKE",
})

QUERY_TIMEOUT: int = 30
MAX_ROWS: int = 1000


# --- Result Types ---


class QueryResult(TypedDict):
    """Structured result from a read query."""

    columns: list[str]
    rows: list[list]
