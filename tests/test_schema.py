"""Integration tests for schema exploration — requires a running MariaDB instance."""

import pymysql
import pytest

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.db.schema import describe_table, list_databases, list_tables
from mcp_xamp.types import XampDatabaseError, XampMissingDatabaseError

from .conftest import needs_mariadb


@needs_mariadb
class TestListDatabases:
    def test_returns_system_databases(self, connection_factory) -> None:
        dbs = list_databases(connection_factory)
        assert "mysql" in dbs
        assert "information_schema" in dbs
        assert "performance_schema" in dbs

    def test_returns_user_databases(self, connection_factory, test_database) -> None:
        dbs = list_databases(connection_factory)
        assert test_database in dbs


@needs_mariadb
class TestListTables:
    def test_empty_database_returns_empty_list(self, connection_factory, test_database) -> None:
        tables = list_tables(connection_factory, test_database)
        assert tables == []

    def test_with_sample_tables(self, connection_factory, test_database) -> None:
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100))")
            cur.execute("CREATE TABLE orders (id INT, user_id INT)")

        tables = list_tables(connection_factory, test_database)
        assert "users" in tables
        assert "orders" in tables

    def test_missing_database_parameter(self, connection_factory) -> None:
        with pytest.raises(XampMissingDatabaseError):
            list_tables(connection_factory, "")

    def test_nonexistent_database(self, connection_factory) -> None:
        with pytest.raises((XampDatabaseError, pymysql.err.InternalError)):
            list_tables(connection_factory, "nonexistent_db_xyz_12345")


@needs_mariadb
class TestDescribeTable:
    def test_returns_column_structure(self, connection_factory, test_database) -> None:
        factory = ConnectionFactory.from_env()
        with factory.connect(database=test_database) as conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE users ("
                "  id INT PRIMARY KEY AUTO_INCREMENT,"
                "  name VARCHAR(100) NOT NULL,"
                "  email VARCHAR(255) DEFAULT NULL"
                ")"
            )

        columns = describe_table(connection_factory, test_database, "users")
        assert len(columns) == 3

        col_names = {c["Field"] for c in columns}
        assert col_names == {"id", "name", "email"}

        id_col = next(c for c in columns if c["Field"] == "id")
        assert "PRI" in str(id_col["Key"])
        assert "auto_increment" in str(id_col["Extra"]).lower()

        name_col = next(c for c in columns if c["Field"] == "name")
        assert name_col["Null"] == "NO"

        email_col = next(c for c in columns if c["Field"] == "email")
        assert email_col["Null"] == "YES"
        assert email_col["Default"] is None

    def test_missing_table_returns_error(self, connection_factory, test_database) -> None:
        with pytest.raises((XampDatabaseError, pymysql.err.InternalError)):
            describe_table(connection_factory, test_database, "ghost_table")

    def test_missing_database_parameter(self, connection_factory) -> None:
        with pytest.raises(XampMissingDatabaseError):
            describe_table(connection_factory, "", "users")
