"""Connection factory — credential sourcing and per-query connections."""

import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass

import pymysql
import pymysql.err

from mcp_xamp.security.sanitizer import sanitize_error
from mcp_xamp.types import (
    QUERY_TIMEOUT,
    XampAuthError,
    XampConnectionError,
    XampDatabaseError,
    XampQueryError,
    XampTimeoutError,
)


@dataclass
class ConnectionFactory:
    """Holds connection parameters and creates short-lived PyMySQL connections.

    Defaults match a typical XAMPP installation (127.0.0.1:3306, root, no password).
    Credentials MUST come from environment variables — never from tool arguments.
    """

    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""

    @classmethod
    def from_env(cls) -> "ConnectionFactory":
        """Build a factory from ``MCP_XAMP_*`` environment variables."""
        return cls(
            host=os.environ.get("MCP_XAMP_HOST", "127.0.0.1"),
            port=int(os.environ.get("MCP_XAMP_PORT", "3306")),
            user=os.environ.get("MCP_XAMP_USER", "root"),
            password=os.environ.get("MCP_XAMP_PASSWORD", ""),
        )

    @contextmanager
    def connect(self, database: str) -> Iterator[pymysql.Connection]:
        """Open a fresh PyMySQL connection to *database* and close it on exit.

        Maps common PyMySQL exceptions to the Xamp error hierarchy.
        """
        conn: pymysql.Connection | None = None
        try:
            # read_timeout is a CLIENT-SIDE socket timeout only. It controls how
            # long the client waits for the server to send data. The server-side
            # query may continue running after the client times out and disconnects.
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=database,
                connect_timeout=5,
                read_timeout=QUERY_TIMEOUT,
                charset="utf8mb4",
                autocommit=True,
            )
            yield conn
        except pymysql.err.OperationalError as exc:
            code: int | None = exc.args[0] if exc.args else None
            sanitized = sanitize_error(exc)
            if code == 1045:
                raise XampAuthError(sanitized) from exc
            if code in (2003, 2006):
                raise XampConnectionError(sanitized) from exc
            if "timeout" in str(exc).lower():
                raise XampTimeoutError(sanitized) from exc
            raise XampConnectionError(sanitized) from exc
        except pymysql.err.InternalError as exc:
            sanitized = sanitize_error(exc)
            code: int | None = exc.args[0] if exc.args else None
            if code == 1049:
                raise XampDatabaseError(sanitized) from exc
            raise XampDatabaseError(sanitized) from exc
        except pymysql.err.ProgrammingError as exc:
            raise XampQueryError(sanitize_error(exc)) from exc
        finally:
            if conn is not None:
                with suppress(Exception):
                    conn.close()

    def ping(self) -> None:
        """Verify that a connection to the database can be established.

        Opens a short-lived connection to the ``mysql`` system database (always
        present on MariaDB/MySQL), executes ``SELECT 1``, and closes cleanly.
        Exceptions propagate to the caller — error mapping is handled by
        ``connect()``, so all Xamp error types apply here too.
        """
        with self.connect(database="mysql") as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
