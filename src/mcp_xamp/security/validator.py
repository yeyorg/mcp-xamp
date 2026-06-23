"""Query validation, write gate, and parameter checks."""

import os

from mcp_xamp.types import (
    FORBIDDEN_KEYWORDS,
    READ_KEYWORDS,
    XampMissingDatabaseError,
    XampQueryError,
    XampWriteRejectedError,
)


def validate_read_query(sql: str) -> None:
    """Ensure *sql* is a read-only statement.

    Raises XampQueryError if the query is empty or its first keyword is a
    write / DDL statement.
    """
    stripped = (sql or "").strip()
    if not stripped:
        raise XampQueryError("La consulta SQL esta vacia.")

    first_word = stripped.upper().split()[0]

    if first_word in FORBIDDEN_KEYWORDS:
        raise XampQueryError(
            "read_query solo permite SELECT, SHOW, DESCRIBE, EXPLAIN y WITH. "
            "Para escrituras usa write_query."
        )

    if first_word not in READ_KEYWORDS:
        raise XampQueryError(
            f"Tipo de consulta '{first_word}' no permitido. "
            "read_query solo permite SELECT, SHOW, DESCRIBE, EXPLAIN y WITH."
        )


def check_write_allowed() -> None:
    """Raise XampWriteRejectedError unless the MCP_XAMP_ALLOW_WRITE env var
    is set to ``"true"`` (case-insensitive).
    """
    allowed = os.environ.get("MCP_XAMP_ALLOW_WRITE", "").lower()
    if allowed != "true":
        raise XampWriteRejectedError(
            "Las operaciones de escritura estan deshabilitadas. "
            "Configura MCP_XAMP_ALLOW_WRITE=true para habilitarlas."
        )


def require_database(database: str | None) -> None:
    """Raise XampMissingDatabaseError when *database* is None, empty, or whitespace-only."""
    if not database or not database.strip():
        raise XampMissingDatabaseError(
            "El parametro 'database' es obligatorio. "
            "Usa list_databases para ver las bases disponibles."
        )
