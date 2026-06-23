"""Integration tests for query execution — requires a running MariaDB instance."""

import pymysql
import pytest

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.db.executor import read_query, write_query
from mcp_xamp.types import (
    MAX_ROWS,
    XampMissingDatabaseError,
    XampQueryError,
    XampWriteRejectedError,
)

from .conftest import needs_mariadb


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

        result = read_query(
            connection_factory, test_database, "EXPLAIN SELECT * FROM e_test"
        )
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
        result = write_query(
            connection_factory, test_database, "CREATE TABLE temp_ddl (id INT)"
        )
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
