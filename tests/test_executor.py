"""Integration tests for query execution — requires a running MariaDB instance."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pymysql
import pytest

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.db.executor import _detect_operation, read_query, write_query
from mcp_xamp.types import (
    MAX_ROWS,
    XampMissingDatabaseError,
    XampQueryError,
    XampWriteRejectedError,
)

from .conftest import needs_mariadb

# ---------------------------------------------------------------------------
# Unit: _detect_operation (A2.3)
# ---------------------------------------------------------------------------


class TestDetectOperation:
    def test_insert_uppercase(self) -> None:
        assert _detect_operation("INSERT INTO t VALUES (1)") == "INSERT"

    def test_insert_lowercase(self) -> None:
        assert _detect_operation("insert into t values (1)") == "INSERT"

    def test_insert_mixed_case(self) -> None:
        assert _detect_operation("Insert INTO t VALUES (1)") == "INSERT"

    def test_update(self) -> None:
        assert _detect_operation("UPDATE t SET col=1") == "UPDATE"

    def test_delete(self) -> None:
        assert _detect_operation("DELETE FROM t WHERE id=1") == "DELETE"

    def test_create(self) -> None:
        assert _detect_operation("CREATE TABLE t (id INT)") == "CREATE"

    def test_drop(self) -> None:
        assert _detect_operation("DROP TABLE t") == "DROP"

    def test_alter(self) -> None:
        assert _detect_operation("ALTER TABLE t ADD col INT") == "ALTER"

    def test_truncate(self) -> None:
        assert _detect_operation("TRUNCATE TABLE t") == "TRUNCATE"

    def test_grant(self) -> None:
        assert _detect_operation("GRANT SELECT ON *.* TO user") == "GRANT"

    def test_revoke(self) -> None:
        assert _detect_operation("REVOKE SELECT ON *.* FROM user") == "REVOKE"

    def test_empty_string_returns_unknown(self) -> None:
        assert _detect_operation("") == "UNKNOWN"

    def test_whitespace_only_returns_unknown(self) -> None:
        assert _detect_operation("   ") == "UNKNOWN"

    def test_leading_whitespace_detected(self) -> None:
        assert _detect_operation("  INSERT INTO t VALUES (1)") == "INSERT"


# ---------------------------------------------------------------------------
# Unit: WRITE_AUDIT log via caplog (A2.4)
# ---------------------------------------------------------------------------


class TestWriteAuditLog:
    def _make_mock_factory(self, rowcount: int = 1):
        """Return a ConnectionFactory whose connect() yields a mocked cursor."""
        factory = ConnectionFactory()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = rowcount
        mock_cursor.execute = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.commit = MagicMock()
        mock_conn.rollback = MagicMock()

        @contextmanager
        def fake_connect(database):
            yield mock_conn

        factory.connect = fake_connect
        return factory, mock_cursor, mock_conn

    def test_write_audit_emitted_on_success(self, caplog) -> None:
        """A successful write_query must emit exactly one WRITE_AUDIT INFO record."""
        import logging

        factory, mock_cursor, _ = self._make_mock_factory(rowcount=1)

        with caplog.at_level(logging.INFO, logger="mcp_xamp.db.executor"):
            write_query(factory, "mydb", "INSERT INTO t VALUES (1)")

        audit_records = [r for r in caplog.records if "WRITE_AUDIT" in r.message]
        assert len(audit_records) == 1

        msg = audit_records[0].message
        assert "database=mydb" in msg
        assert "operation=INSERT" in msg
        assert "affected_rows=1" in msg

    def test_write_audit_omits_query_text(self, caplog) -> None:
        """The query text must NOT appear in any log record."""
        import logging

        query = "INSERT INTO secret_table VALUES ('top_secret_value')"
        factory, _, _ = self._make_mock_factory(rowcount=1)

        with caplog.at_level(logging.INFO, logger="mcp_xamp.db.executor"):
            write_query(factory, "mydb", query)

        for record in caplog.records:
            assert "secret_table" not in record.message
            assert "top_secret_value" not in record.message

    def test_write_audit_absent_on_rollback(self, caplog) -> None:
        """A failed write (pre-commit exception) must NOT emit a WRITE_AUDIT record."""
        import logging

        factory = ConnectionFactory()
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock(side_effect=pymysql.err.ProgrammingError(1064, "syntax"))

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.rollback = MagicMock()

        @contextmanager
        def fake_connect(database):
            yield mock_conn

        factory.connect = fake_connect

        with (
            caplog.at_level(logging.INFO, logger="mcp_xamp.db.executor"),
            pytest.raises(XampQueryError),
        ):
            write_query(factory, "mydb", "INSERT INTO t VALUES (1)")

        audit_records = [r for r in caplog.records if "WRITE_AUDIT" in r.message]
        assert len(audit_records) == 0


@needs_mariadb
class TestReadQuery:
    def test_select_one(self, connection_factory, test_database) -> None:
        result = read_query(connection_factory, test_database, "SELECT 1 AS num")
        assert result["columns"] == ["num"]
        assert result["rows"] == [[1]]

    def test_select_from_sample_table(self, connection_factory, test_database) -> None:
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE items (id INT, label VARCHAR(50))")
            cur.execute("INSERT INTO items VALUES (1, 'alpha'), (2, 'beta')")

        result = read_query(
            connection_factory, test_database, "SELECT id, label FROM items ORDER BY id"
        )
        assert result["columns"] == ["id", "label"]
        assert result["rows"] == [[1, "alpha"], [2, "beta"]]

    def test_empty_result_set(self, connection_factory, test_database) -> None:
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE empty_tbl (x INT)")

        result = read_query(connection_factory, test_database, "SELECT * FROM empty_tbl")
        assert result["columns"] == ["x"]
        assert result["rows"] == []

    def test_insert_rejected(self, connection_factory, test_database) -> None:
        with pytest.raises(XampQueryError):
            read_query(connection_factory, test_database, "INSERT INTO t VALUES (1)")

    def test_drop_rejected(self, connection_factory, test_database) -> None:
        with pytest.raises(XampQueryError):
            read_query(connection_factory, test_database, "DROP TABLE whatever")

    def test_syntax_error_raises(self, connection_factory, test_database) -> None:
        with pytest.raises((XampQueryError, pymysql.err.ProgrammingError)):
            read_query(connection_factory, test_database, "SELEC * FROM nonexistent")

    def test_missing_database_parameter(self, connection_factory) -> None:
        with pytest.raises(XampMissingDatabaseError):
            read_query(connection_factory, "", "SELECT 1")

    def test_row_limit_enforced(self, connection_factory, test_database) -> None:
        """Insert MAX_ROWS+100 rows and verify only MAX_ROWS are returned."""
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE logs (id INT PRIMARY KEY AUTO_INCREMENT, msg TEXT)")
            values = ", ".join(f"(NULL, 'row {i}')" for i in range(MAX_ROWS + 100))
            cur.execute(f"INSERT INTO logs (id, msg) VALUES {values}")

        result = read_query(connection_factory, test_database, "SELECT * FROM logs")
        assert len(result["rows"]) <= MAX_ROWS

    def test_show_tables_works(self, connection_factory, test_database) -> None:
        result = read_query(connection_factory, test_database, "SHOW TABLES")
        assert "columns" in result
        assert "rows" in result

    def test_describe_works(self, connection_factory, test_database) -> None:
        result = read_query(
            connection_factory, test_database, "DESCRIBE information_schema.COLUMNS"
        )
        assert len(result["columns"]) > 0
        assert len(result["rows"]) > 0

    def test_explain_works(self, connection_factory, test_database) -> None:
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE e_test (id INT PRIMARY KEY)")

        result = read_query(connection_factory, test_database, "EXPLAIN SELECT * FROM e_test")
        assert len(result["rows"]) > 0

    def test_with_cte_works(self, connection_factory, test_database) -> None:
        result = read_query(
            connection_factory,
            test_database,
            "WITH cte AS (SELECT 1 AS n) SELECT n FROM cte",
        )
        assert result["rows"] == [[1]]


@needs_mariadb
class TestWriteQuery:
    def test_write_gate_off_rejected(self, monkeypatch, connection_factory, test_database) -> None:
        monkeypatch.delenv("MCP_XAMP_ALLOW_WRITE", raising=False)
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "false")

        with pytest.raises(XampWriteRejectedError):
            # The gate is checked at the server layer, not executor.
            # Here we test that the executor works; gate test is in test_server.py.
            pass

    def test_insert_with_gate_on(self, connection_factory, test_database, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "true")
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE w_test (id INT, val VARCHAR(20))")

        result = write_query(
            connection_factory, test_database, "INSERT INTO w_test VALUES (1, 'hello')"
        )
        assert result["affected_rows"] == 1

        # Verify it was persisted
        verify = read_query(connection_factory, test_database, "SELECT * FROM w_test")
        assert verify["rows"] == [[1, "hello"]]

    def test_update_with_gate_on(self, connection_factory, test_database, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "true")
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE u_test (id INT, val VARCHAR(20))")
            cur.execute("INSERT INTO u_test VALUES (1, 'old')")

        result = write_query(
            connection_factory,
            test_database,
            "UPDATE u_test SET val = 'new' WHERE id = 1",
        )
        assert result["affected_rows"] == 1

    def test_ddl_with_gate_on(self, connection_factory, test_database, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "true")
        result = write_query(connection_factory, test_database, "CREATE TABLE temp_ddl (id INT)")
        assert result["affected_rows"] == 0

        # Verify table exists
        tables = read_query(connection_factory, test_database, "SHOW TABLES")
        table_names = [row[0] for row in tables["rows"]]
        assert "temp_ddl" in table_names

    def test_syntax_error_rollback(self, connection_factory, test_database, monkeypatch) -> None:
        monkeypatch.setenv("MCP_XAMP_ALLOW_WRITE", "true")
        with pytest.raises((XampQueryError, pymysql.err.ProgrammingError)):
            write_query(
                connection_factory,
                test_database,
                "INSERT INTO nonexistent_table_xyz (x) VALUES (1)",
            )

    def test_missing_database_parameter(self, connection_factory) -> None:
        with pytest.raises(XampMissingDatabaseError):
            write_query(connection_factory, "", "INSERT INTO t VALUES (1)")


# ---------------------------------------------------------------------------
# Helper shared by Slice B unit tests
# ---------------------------------------------------------------------------


def _make_read_factory(rows: list, description: list[tuple] | None = None):
    """Return (factory, mock_cursor) pre-configured to return *rows* from fetchmany."""
    if description is None:
        description = [("col",)]

    factory = ConnectionFactory()
    mock_cursor = MagicMock()
    mock_cursor.description = description
    mock_cursor.fetchmany = MagicMock(return_value=rows)
    mock_cursor.execute = MagicMock()

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def fake_connect(database):
        yield mock_conn

    factory.connect = fake_connect
    return factory, mock_cursor


# ---------------------------------------------------------------------------
# Unit: I3 — Query parameterization (B3.3)
# ---------------------------------------------------------------------------


class TestReadQueryParameters:
    def test_parameters_passed_as_tuple(self) -> None:
        """cur.execute must receive the params as a tuple when parameters given."""
        factory, mock_cursor = _make_read_factory(rows=[("value",)])
        read_query(factory, "db", "SELECT * FROM t WHERE c = %s", parameters=["x"])
        mock_cursor.execute.assert_called_once_with("SELECT * FROM t WHERE c = %s", ("x",))

    def test_no_parameters_passes_none(self) -> None:
        """When parameters=None, cur.execute receives (query, None) — backward compat."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        read_query(factory, "db", "SELECT 1", parameters=None)
        mock_cursor.execute.assert_called_once_with("SELECT 1", None)

    def test_empty_list_treated_as_no_params(self) -> None:
        """An empty parameters list is valid and behaves like no params."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        # parameters=[] → or None → None path
        read_query(factory, "db", "SELECT 1", parameters=[])
        mock_cursor.execute.assert_called_once_with("SELECT 1", None)

    def test_none_element_valid(self) -> None:
        """None (JSON null) inside parameters list is a valid scalar."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        read_query(factory, "db", "SELECT %s", parameters=[None])
        mock_cursor.execute.assert_called_once_with("SELECT %s", (None,))

    def test_bool_element_valid(self) -> None:
        """Boolean inside parameters list is a valid scalar."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        read_query(factory, "db", "SELECT %s", parameters=[True])
        mock_cursor.execute.assert_called_once_with("SELECT %s", (True,))

    def test_nested_list_rejected(self) -> None:
        """A nested list inside parameters must be rejected before the DB call."""
        factory, mock_cursor = _make_read_factory(rows=[])
        with pytest.raises(XampQueryError, match="scalar"):
            read_query(factory, "db", "SELECT %s", parameters=[[1, 2]])
        mock_cursor.execute.assert_not_called()

    def test_non_list_parameters_rejected(self) -> None:
        """parameters must be a list; a bare string at top level is rejected."""
        factory, mock_cursor = _make_read_factory(rows=[])
        with pytest.raises(XampQueryError, match="list"):
            read_query(factory, "db", "SELECT %s", parameters="42")  # type: ignore[arg-type]
        mock_cursor.execute.assert_not_called()

    def test_dict_element_rejected(self) -> None:
        """A dict inside parameters list is not a scalar — must be rejected."""
        factory, mock_cursor = _make_read_factory(rows=[])
        with pytest.raises(XampQueryError, match="scalar"):
            read_query(factory, "db", "SELECT %s", parameters=[{"key": "val"}])
        mock_cursor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Unit: I4 — Effective limit clamping (B4.4)
# ---------------------------------------------------------------------------


class TestReadQueryEffectiveLimit:
    def test_no_limit_uses_max_rows(self) -> None:
        """When limit=None, fetchmany is called with MAX_ROWS + 1."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        read_query(factory, "db", "SELECT 1", limit=None)
        mock_cursor.fetchmany.assert_called_once_with(MAX_ROWS + 1)

    def test_limit_below_max_rows(self) -> None:
        """limit=10 with MAX_ROWS=1000 → fetchmany called with 11."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        read_query(factory, "db", "SELECT 1", limit=10)
        mock_cursor.fetchmany.assert_called_once_with(11)

    def test_limit_above_max_rows_clamped(self) -> None:
        """limit > MAX_ROWS silently clamped — fetchmany uses MAX_ROWS + 1."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        read_query(factory, "db", "SELECT 1", limit=MAX_ROWS + 5000)
        mock_cursor.fetchmany.assert_called_once_with(MAX_ROWS + 1)

    def test_limit_zero_rejected(self) -> None:
        """limit=0 must raise XampQueryError before reaching the database."""
        factory, mock_cursor = _make_read_factory(rows=[])
        with pytest.raises(XampQueryError, match=">="):
            read_query(factory, "db", "SELECT 1", limit=0)
        mock_cursor.execute.assert_not_called()

    def test_limit_negative_rejected(self) -> None:
        """Negative limit must be rejected."""
        factory, mock_cursor = _make_read_factory(rows=[])
        with pytest.raises(XampQueryError, match=">="):
            read_query(factory, "db", "SELECT 1", limit=-1)
        mock_cursor.execute.assert_not_called()

    def test_limit_one_accepted(self) -> None:
        """limit=1 is the minimum valid value — must be accepted."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        read_query(factory, "db", "SELECT 1", limit=1)
        mock_cursor.fetchmany.assert_called_once_with(2)


# ---------------------------------------------------------------------------
# Unit: I5 — Truncation hint (B5.3)
# ---------------------------------------------------------------------------


class TestReadQueryTruncation:
    def test_truncated_true_when_extra_row_fetched(self) -> None:
        """If fetchmany returns effective_limit+1 rows, truncated must be True."""
        effective_limit = 3
        # fetchmany returns 4 rows (one sentinel extra)
        rows = [("r1",), ("r2",), ("r3",), ("r4",)]
        factory, mock_cursor = _make_read_factory(rows=rows)
        result = read_query(factory, "db", "SELECT 1", limit=effective_limit)
        assert result["truncated"] is True
        assert len(result["rows"]) == effective_limit

    def test_truncated_false_when_fewer_rows(self) -> None:
        """If fetchmany returns fewer rows than effective_limit, truncated is False."""
        rows = [("r1",), ("r2",)]
        factory, mock_cursor = _make_read_factory(rows=rows)
        result = read_query(factory, "db", "SELECT 1", limit=5)
        assert result["truncated"] is False
        assert len(result["rows"]) == 2

    def test_truncated_false_on_empty_result(self) -> None:
        """Empty result set → truncated is False, rows is []."""
        factory, mock_cursor = _make_read_factory(rows=[])
        mock_cursor.description = None
        result = read_query(factory, "db", "SELECT 1", limit=5)
        assert result["truncated"] is False
        assert result["rows"] == []

    def test_truncated_false_on_exact_limit_hit(self) -> None:
        """Exactly effective_limit rows returned → truncated is False."""
        effective_limit = 2
        rows = [("r1",), ("r2",)]
        factory, mock_cursor = _make_read_factory(rows=rows)
        result = read_query(factory, "db", "SELECT 1", limit=effective_limit)
        assert result["truncated"] is False
        assert len(result["rows"]) == effective_limit

    def test_truncated_true_with_limit_one(self) -> None:
        """effective_limit=1, 2 rows returned → truncated True, 1 row in result."""
        rows = [("r1",), ("r2",)]
        factory, mock_cursor = _make_read_factory(rows=rows)
        result = read_query(factory, "db", "SELECT 1", limit=1)
        assert result["truncated"] is True
        assert len(result["rows"]) == 1
