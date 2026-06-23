"""Schema exploration — list databases, tables, and describe table structure."""

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.security.validator import require_database


def _escape_identifier(name: str) -> str:
    """Backtick-escape a database or table identifier."""
    return name.replace("`", "``")


def list_databases(factory: ConnectionFactory) -> list[str]:
    """Return every accessible database on the server, including system DBs."""
    with factory.connect(database="mysql") as conn, conn.cursor() as cur:
        cur.execute("SHOW DATABASES")
        return [row[0] for row in cur.fetchall()]


def list_tables(factory: ConnectionFactory, database: str) -> list[str]:
    """Return all BASE TABLE names in *database*.

    Requires the *database* parameter. Returns an empty list when the
    database exists but has no tables.
    """
    require_database(database)
    safe_db = _escape_identifier(database)
    sql = f"SHOW FULL TABLES FROM `{safe_db}` WHERE Table_Type = 'BASE TABLE'"
    with factory.connect(database=database) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


def describe_table(
    factory: ConnectionFactory, database: str, table: str
) -> list[dict[str, str | None]]:
    """Return the column schema for *table* in *database*.

    Each dict includes: Field, Type, Null, Key, Default, Extra.
    """
    require_database(database)
    with factory.connect(database=database) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, "
            "COLUMN_KEY, COLUMN_DEFAULT, EXTRA "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (database, table),
        )
        rows = cur.fetchall()
        return [
            {
                "Field": row[0],
                "Type": row[1],
                "Null": row[2],
                "Key": row[3],
                "Default": row[4],
                "Extra": row[5],
            }
            for row in rows
        ]
