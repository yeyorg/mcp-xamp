"""Query execution — read_query (validated) and write_query (gated)."""

import logging
import re

import pymysql.err

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.security.sanitizer import sanitize_error
from mcp_xamp.security.validator import require_database, validate_read_query
from mcp_xamp.types import MAX_ROWS, QueryResult, XampDatabaseError, XampQueryError

logger = logging.getLogger(__name__)

_FIRST_WORD_PATTERN = re.compile(r"^\s*(\w+)")


def _detect_operation(query: str) -> str:
    """Return the uppercased first SQL keyword from *query*, or ``"UNKNOWN"``.

    Pure function — no side effects.  Used to populate the ``op=`` field in
    WRITE_AUDIT log lines without ever logging the full query text.
    """
    match = _FIRST_WORD_PATTERN.match(query)
    if match:
        return match.group(1).upper()
    return "UNKNOWN"


def read_query(
    factory: ConnectionFactory,
    database: str,
    query: str,
    parameters: list | None = None,
    limit: int | None = None,
) -> QueryResult:
    """Execute a read-only SQL query and return columns + rows.

    Validates that *query* starts with a read keyword (SELECT, SHOW,
    DESCRIBE, EXPLAIN, WITH).  Caps results at *limit* (or ``MAX_ROWS`` when
    absent).  Accepts optional *parameters* for ``%s`` placeholder binding —
    the driver handles escaping, never the caller.

    Args:
        factory: Connection factory used to open a short-lived connection.
        database: Target database name (must be non-empty).
        query: Read-only SQL statement, optionally with ``%s`` placeholders.
        parameters: Optional list of scalar values to bind to ``%s``
            placeholders.  Must be a flat list — nested lists/dicts are
            rejected before the DB call.
        limit: Maximum rows to return.  Must be >= 1 when provided.
            Silently clamped to ``MAX_ROWS`` if it exceeds the server max.
    """
    require_database(database)
    validate_read_query(query)

    # --- Validate parameters (I3) ---
    if parameters is not None:
        if not isinstance(parameters, list):
            raise XampQueryError(f"'parameters' must be a list, got {type(parameters).__name__!r}")
        for i, elem in enumerate(parameters):
            if not isinstance(elem, (str, int, float, bool, type(None))):
                raise XampQueryError(
                    f"'parameters[{i}]' must be a scalar (str, int, float, bool, null), "
                    f"got {type(elem).__name__!r}"
                )

    # --- Compute effective limit (I4) ---
    if limit is not None and limit < 1:
        raise XampQueryError("'limit' must be >= 1")
    effective_limit = min(limit, MAX_ROWS) if limit is not None else MAX_ROWS

    try:
        with factory.connect(database=database) as conn, conn.cursor() as cur:
            cur.execute(query, tuple(parameters) if parameters else None)
            columns: list[str] = [desc[0] for desc in cur.description] if cur.description else []
            # Fetch one extra row to detect truncation (I5 sentinel)
            rows_raw = cur.fetchmany(effective_limit + 1)
            truncated = len(rows_raw) > effective_limit
            rows = [list(row) for row in rows_raw[:effective_limit]]
            return QueryResult(columns=columns, rows=rows, truncated=truncated)
    except pymysql.err.ProgrammingError as exc:
        raise XampQueryError(sanitize_error(exc)) from exc
    except pymysql.err.InternalError as exc:
        raise XampDatabaseError(sanitize_error(exc)) from exc


def write_query(factory: ConnectionFactory, database: str, query: str) -> dict[str, int]:
    """Execute a mutating SQL statement and return the affected row count.

    Callers MUST gate this behind ``check_write_allowed()`` in the server
    layer before invoking. Rolls back on failure.
    """
    require_database(database)

    try:
        with factory.connect(database=database) as conn, conn.cursor() as cur:
            try:
                cur.execute(query)
                conn.commit()
                logger.info(
                    "WRITE_AUDIT database=%s operation=%s affected_rows=%d",
                    database,
                    _detect_operation(query),
                    cur.rowcount,
                )
                return {"affected_rows": cur.rowcount}
            except Exception:
                conn.rollback()
                raise
    except pymysql.err.ProgrammingError as exc:
        raise XampQueryError(sanitize_error(exc)) from exc
    except pymysql.err.InternalError as exc:
        raise XampDatabaseError(sanitize_error(exc)) from exc


def format_results(cur) -> dict[str, list]:
    """Extract columns and rows from a cursor into a plain dict.

    Useful for callers that need the same shape without the TypedDict
    constraint.
    """
    columns: list[str] = [desc[0] for desc in cur.description] if cur.description else []
    rows: list[list] = [list(row) for row in cur.fetchall()]
    return {"columns": columns, "rows": rows}
