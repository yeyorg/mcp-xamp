"""Query execution — read_query (validated) and write_query (gated)."""

import pymysql.err

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.security.sanitizer import sanitize_error
from mcp_xamp.security.validator import require_database, validate_read_query
from mcp_xamp.types import MAX_ROWS, QueryResult, XampDatabaseError, XampQueryError


def read_query(
    factory: ConnectionFactory, database: str, query: str
) -> QueryResult:
    """Execute a read-only SQL query and return columns + rows.

    Validates that *query* starts with a read keyword (SELECT, SHOW,
    DESCRIBE, EXPLAIN, WITH). Caps results at ``MAX_ROWS``.
    """
    require_database(database)
    validate_read_query(query)

    try:
        with factory.connect(database=database) as conn, conn.cursor() as cur:
            cur.execute(query)
            columns: list[str] = (
                [desc[0] for desc in cur.description] if cur.description else []
            )
            rows_raw = cur.fetchmany(MAX_ROWS + 1)
            rows = [list(row) for row in rows_raw[:MAX_ROWS]]
            return QueryResult(columns=columns, rows=rows)
    except pymysql.err.ProgrammingError as exc:
        raise XampQueryError(sanitize_error(exc)) from exc
    except pymysql.err.InternalError as exc:
        raise XampDatabaseError(sanitize_error(exc)) from exc


def write_query(
    factory: ConnectionFactory, database: str, query: str
) -> dict[str, int]:
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
    columns: list[str] = (
        [desc[0] for desc in cur.description] if cur.description else []
    )
    rows: list[list] = [list(row) for row in cur.fetchall()]
    return {"columns": columns, "rows": rows}
