"""MCP XAMPP Server — stdio transport with 5 tools for MariaDB/MySQL access."""

import asyncio
import importlib.metadata
import json
import logging
import sys
import traceback

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_xamp.db.connection import ConnectionFactory
from mcp_xamp.db.executor import read_query, write_query
from mcp_xamp.db.schema import describe_table, list_databases, list_tables
from mcp_xamp.security.sanitizer import sanitize_error
from mcp_xamp.security.validator import (
    check_write_allowed,
)
from mcp_xamp.types import (
    XampAuthError,
    XampConnectionError,
    XampDatabaseError,
    XampError,
    XampMissingDatabaseError,
    XampQueryError,
    XampTimeoutError,
    XampWriteRejectedError,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

server = Server("mcp-xamp")
factory = ConnectionFactory.from_env()


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_databases",
            description="Lista todas las bases de datos accesibles en el servidor MariaDB/MySQL.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_tables",
            description="Lista todas las tablas en una base de datos.",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Nombre de la base de datos.",
                    },
                },
                "required": ["database"],
            },
        ),
        Tool(
            name="describe_table",
            description="Describe la estructura de una tabla (columnas, tipos, claves).",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Nombre de la base de datos.",
                    },
                    "table": {
                        "type": "string",
                        "description": "Nombre de la tabla.",
                    },
                },
                "required": ["database", "table"],
            },
        ),
        Tool(
            name="read_query",
            description=(
                "Ejecuta una consulta SQL de solo lectura (SELECT, SHOW, DESCRIBE, EXPLAIN, WITH)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Nombre de la base de datos.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Consulta SQL de solo lectura.",
                    },
                    "parameters": {
                        "type": "array",
                        "items": {"type": ["string", "number", "boolean", "null"]},
                        "description": "Valores opcionales para placeholders %s en la consulta.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Maximo de filas a devolver (limitado por el servidor).",
                    },
                },
                "required": ["database", "query"],
            },
        ),
        Tool(
            name="write_query",
            description=(
                "Ejecuta una consulta SQL de escritura "
                "(INSERT, UPDATE, DELETE, DDL). "
                "Requiere MCP_XAMP_ALLOW_WRITE=true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "Nombre de la base de datos.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Consulta SQL de escritura.",
                    },
                },
                "required": ["database", "query"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = _execute_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except XampMissingDatabaseError:
        raise  # message is already in Spanish from validator
    except XampWriteRejectedError:
        raise  # message is already in Spanish from validator
    except XampQueryError as exc:
        raise XampQueryError(f"Error en la consulta SQL: {sanitize_error(exc)}") from exc
    except XampDatabaseError as exc:
        db = arguments.get("database", "desconocida") if isinstance(arguments, dict) else ""
        raise XampDatabaseError(
            f"La base de datos '{db}' no existe. Usa list_databases para ver las disponibles."
        ) from exc
    except XampConnectionError:
        raise XampConnectionError(
            "No se pudo conectar a la base de datos. Esta corriendo XAMPP?"
        ) from None
    except XampAuthError:
        raise XampAuthError(
            "Error de autenticacion. Verifica MCP_XAMP_USER y MCP_XAMP_PASSWORD."
        ) from None
    except XampTimeoutError:
        raise XampTimeoutError("La consulta excedio el tiempo limite de 30 segundos.") from None
    except XampError as exc:
        raise XampError(sanitize_error(exc)) from exc
    except Exception:
        logger.error("Unexpected error:\n%s", traceback.format_exc())
        raise XampError("Error interno del servidor.") from None


def _execute_tool(name: str, arguments: dict):
    """Route tool calls to the appropriate module function."""
    if name == "list_databases":
        return list_databases(factory)

    if name == "list_tables":
        database = arguments.get("database", "")
        return list_tables(factory, database)

    if name == "describe_table":
        database = arguments.get("database", "")
        table = arguments.get("table", "")
        return describe_table(factory, database, table)

    if name == "read_query":
        database = arguments.get("database", "")
        query = arguments.get("query", "")
        parameters = arguments.get("parameters") or None
        limit = arguments.get("limit")
        return read_query(factory, database, query, parameters=parameters, limit=limit)

    if name == "write_query":
        check_write_allowed()
        database = arguments.get("database", "")
        query = arguments.get("query", "")
        return write_query(factory, database, query)

    raise XampError(f"Herramienta desconocida: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _ping_db() -> None:
    """Synchronous wrapper for the pre-flight connection check."""
    factory.ping()


async def main() -> None:
    """Launch the MCP server on stdio transport."""
    version = importlib.metadata.version("mcp-xamp")
    logger.info("mcp-xamp v%s iniciando.", version)
    try:
        await asyncio.to_thread(_ping_db)
        logger.info("Pre-flight OK: conexion a MariaDB/MySQL establecida.")
    except XampError as exc:
        logger.warning(
            "Pre-flight: no se pudo conectar a la base de datos (%s). "
            "El servidor continua; verifica que XAMPP este corriendo.",
            sanitize_error(exc),
        )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run() -> None:
    """Synchronous entry point for console_scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
