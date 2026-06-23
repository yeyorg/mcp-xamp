"""Shared fixtures and utilities for MCP XAMPP Server tests."""

import os
import sys

import pymysql
import pytest

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp_xamp.db.connection import ConnectionFactory  # noqa: E402

TEST_DB_NAME = "mcp_xamp_test"


def check_mariadb_available() -> bool:
    """Return ``True`` when a MariaDB/MySQL instance is reachable with the
    configured ``MCP_XAMP_*`` env vars."""
    try:
        factory = ConnectionFactory.from_env()
        conn = pymysql.connect(
            host=factory.host,
            port=factory.port,
            user=factory.user,
            password=factory.password,
            connect_timeout=2,
            charset="utf8mb4",
        )
        conn.close()
        return True
    except Exception:
        return False


MARIA_AVAILABLE = check_mariadb_available()
needs_mariadb = pytest.mark.skipif(
    not MARIA_AVAILABLE,
    reason="MariaDB/MySQL not available (start XAMPP)",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def setup_test_db():
    """Create a dedicated test database before integration tests and drop it
    afterwards."""
    if not MARIA_AVAILABLE:
        pytest.skip("MariaDB/MySQL not available")

    factory = ConnectionFactory.from_env()
    conn = pymysql.connect(
        host=factory.host,
        port=factory.port,
        user=factory.user,
        password=factory.password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`")
            cur.execute(f"CREATE DATABASE `{TEST_DB_NAME}`")
        yield TEST_DB_NAME
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`")
    finally:
        conn.close()


@pytest.fixture()
def connection_factory(monkeypatch) -> ConnectionFactory:
    """Return a ConnectionFactory reading from the live environment."""
    return ConnectionFactory.from_env()


@pytest.fixture()
def test_database(setup_test_db) -> str:
    """Name of the isolated test database, guaranteed to exist."""
    return setup_test_db
