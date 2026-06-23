# Exploration: MCP MariaDB Server for XAMPP

## Executive Summary

Building an MCP server in Python for MariaDB/MySQL via XAMPP is straightforward and well-supported by the official `mcp` Python SDK (v1.27.2 by Anthropic). The closest reference implementation is the archived SQLite MCP server, which provides a proven pattern using the low-level MCP server API. For the database driver, **PyMySQL** is recommended over mysql-connector-python due to its MIT license, pure-Python simplicity, MariaDB compatibility, and negligible footprint. The server should expose tools for query execution (read/write), schema exploration, and database listing -- with **read-only mode as the default** and an explicit opt-in for write operations, following the precedent set by the PostgreSQL reference server.

## Current State

- **Project**: mcp-xamp -- empty, no files yet (only `.atl/skill-registry.md`)
- **Python**: 3.13.1 available (meets MCP SDK requirement of >=3.10)
- **Package manager**: pip 24.3.1 installed; project will migrate to UV for consistency with MCP ecosystem
- **Database**: MariaDB via XAMPP, localhost:3306, root user, all databases accessible
- **OS**: Windows 10/11, PowerShell 5.1
- **No test runner yet**: pytest needs to be installed

## Findings

### 1. MCP Python SDK (v1.27.2)

The official `mcp` package by Anthropic provides two API levels:

**High-Level API (FastMCP):**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MariaDB Explorer", json_response=True)

@mcp.tool()
def run_query(sql: str) -> list[dict]:
    """Execute a SELECT query"""
    ...
```

**Low-Level API (used by reference servers):**

```python
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("mariadb-manager")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="query",
            description="Execute a SQL query",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL to execute"}
                },
                "required": ["sql"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    ...

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)
```

**Key observations:**

- The reference servers use the LOW-LEVEL API for more control
- `FastMCP` is simpler but less flexible for advanced patterns like connection pools
- Transport: stdio (stdin/stdout JSON-RPC) is the standard for local MCP usage
- The `mcp dev` command provides a local dev server with hot reload
- Windows requires `sys.stdin.reconfigure(encoding="utf-8")` for proper stdio encoding

### 2. MySQL/MariaDB Python Driver Comparison

| Criterion | PyMySQL 1.2.0 | mysql-connector-python 9.7.0 |
|-----------|--------------|------------------------------|
| **License** | MIT | GPLv2 (with FOSS exception) |
| **Size** | ~49 KB | ~18 MB (Windows) |
| **Dependencies** | Zero (pure Python) | C extension optional |
| **PEP 249** | Yes | Yes |
| **Async support** | Via aiomysql (third-party) | Built-in (asyncio extension) |
| **MariaDB** | First-class support | MySQL-focused (works but not optimized) |
| **Connection pooling** | Via DBUtils or custom | Built-in via X DevAPI |
| **Python versions** | >=3.9 | >=3.10 |
| **Windows wheel** | Pure Python (any) | Platform-specific (17.7 MB) |
| **Community** | Active, MIT-licensed | Oracle-maintained, GPL |

**Decision: PyMySQL is the clear winner for this project because:**

1. MIT license -- no GPL concerns for redistribution
2. Pure Python -- zero compilation, instant install, trivially small
3. MariaDB-first -- XAMPP ships MariaDB, and PyMySQL is the community-preferred driver for MariaDB
4. Simple API -- PEP 249 compliant, straightforward context manager usage
5. The async limitation is irrelevant: MCP stdio transport runs synchronously (one request at a time per connection)

**If async is ever needed** (e.g., for SSE transport later), use `aiomysql` which wraps PyMySQL with asyncio.

### 3. Reference Implementation Analysis

**SQLite MCP Server (archived, Python):**

- Location: `modelcontextprotocol/servers-archived/src/sqlite/`
- Uses low-level `mcp.server.lowlevel.Server`
- Project structure: `src/mcp_server_sqlite/server.py` with `pyproject.toml`
- Tools: `read_query`, `write_query`, `create_table`, `list_tables`, `describe_table`, `append_insight`
- Resources: `memo://insights` (dynamic business insights)
- Prompts: `mcp-demo` (guided analysis)
- DB class: `SqliteDatabase` encapsulates connection and query logic
- Uses one-off connections per query (`with closing(sqlite3.connect(...))`)
- **Key pattern**: validates query type by checking prefix (`query.strip().upper().startswith('SELECT')`)

**PostgreSQL MCP Server (archived, TypeScript):**

- READ-ONLY ONLY -- all queries wrapped in READ ONLY transaction
- Tools: single `query` tool (SELECT only)
- Resources: table schemas exposed as `postgres://<host>/<table>/schema`
- Connection URL passed as CLI argument

**Pattern comparison:**

| Feature | SQLite | PostgreSQL | Recommended for MariaDB |
|---------|--------|------------|--------------------------|
| Read query tool | `read_query` | `query` | `read_query` |
| Write query tool | `write_query` | N/A (read-only) | `write_query` (opt-in) |
| Create table | `create_table` | N/A | `create_table` (or merge into write_query) |
| List tables | `list_tables` | N/A (resources) | `list_tables` |
| Describe table | `describe_table` | resources | `describe_table` |
| List databases | N/A | N/A | `list_databases` (new, MariaDB-specific) |
| DDL support | CREATE TABLE only | None | Full DDL in write_query |

### 4. Proposed Tool Set

Based on reference patterns and MariaDB-specific needs:

**Schema Exploration Tools:**

- `list_databases` -- SHOW DATABASES (critical for XAMPP multi-DB access)
- `list_tables` -- SHOW TABLES [FROM db] with optional database parameter
- `describe_table` -- DESCRIBE / SHOW COLUMNS / SHOW CREATE TABLE for a specific table

**Query Tools:**

- `read_query` -- SELECT only (validated). Returns rows as JSON array of objects.
- `write_query` -- INSERT, UPDATE, DELETE, DDL (opt-in via config). Returns affected rows.

**Utility Tools (optional, from SQLite pattern):**

- `create_table` -- dedicated CREATE TABLE with validation (or fold into write_query)

**Resources (optional):**

- `mariadb://{database}/{table}/schema` -- JSON schema for each table
- `mariadb://databases` -- list of available databases

### 5. Security Considerations

This is the most critical section. An MCP database server gives an LLM the ability to execute arbitrary SQL. The risks:

1. **SQL Injection via LLM-generated SQL**: The AI generates SQL strings. While parameterized queries prevent traditional injection, the AI itself might construct malicious queries. Mitigation: query type validation + optional read-only mode.

2. **Destructive Operations**: DROP TABLE, DELETE without WHERE, UPDATE without WHERE, ALTER TABLE. Mitigation: separate `read_query` (safe) from `write_query` (dangerous). Default to read-only. Require explicit `--allow-write` flag.

3. **Credential Exposure**: Database credentials in MCP config files. Mitigation: support environment variables for credentials. Never log passwords.

4. **Data Exfiltration**: LLM could SELECT sensitive data and exfiltrate it. Mitigation: this is inherent -- the LLM has the data. The MCP server should document this clearly.

5. **Denial of Service**: Expensive queries (cartesian joins, full table scans). Mitigation: query timeout, result row limit (e.g., max 1000 rows).

**Recommended security model (inspired by PostgreSQL reference):**

- **Default mode**: Read-only. Only `SELECT` and `SHOW` statements allowed.
- **Write mode**: Opt-in via `--allow-write` CLI flag or `MARIADB_ALLOW_WRITE=true` env var.
- **Row limit**: Default max 1000 rows per query. Configurable.
- **Query timeout**: Default 30 seconds. Configurable.
- **No DDL by default**: CREATE/DROP/ALTER require `--allow-ddl` flag.
- **Credential sourcing**: `MARIADB_HOST`, `MARIADB_PORT`, `MARIADB_USER`, `MARIADB_PASSWORD`, `MARIADB_DATABASE` env vars or CLI args.

### 6. Connection Management

For MariaDB, unlike SQLite (file-based), we manage TCP connections:

**Options considered:**

| Strategy | Pros | Cons | Complexity |
|----------|------|------|------------|
| **Connection per query** (SQLite pattern) | Simple, safe, no stale connections | Overhead of TCP handshake per query (but localhost is fast) | Low |
| **Connection pool** | Faster for concurrent use | MCP stdio is single-threaded -- no concurrent queries; pool is overkill | Medium |
| **Persistent connection** | Reuses one connection | Stale connection handling, reconnection logic | Medium |

**Recommendation: Connection per query** (mirrors SQLite reference pattern) for initial implementation:

- MCP stdio transport processes one request at a time (single-threaded)
- No benefit from pooling in stdio mode
- Clean: each query gets a fresh connection, no state leaks
- MariaDB on localhost: TCP handshake is negligible (~1ms)
- If SSE transport is added later, can add pooling then

### 7. Project Structure

Following the SQLite reference pattern and modern Python packaging:

```
mcp-xamp/
├── .gitignore
├── .python-version          # 3.13
├── Makefile                 # Automation (setup, test, lint, run)
├── pyproject.toml           # Project metadata, dependencies, scripts
├── README.md
├── src/
│   └── mcp_server_mariadb/
│       ├── __init__.py
│       ├── server.py        # MCP server entry point + tool definitions
│       ├── database.py      # Database connection/query class
│       └── __main__.py      # python -m mcp_server_mariadb support
└── tests/
    ├── __init__.py
    ├── conftest.py          # Pytest fixtures (test DB setup)
    ├── test_database.py     # Unit tests for database module
    └── test_server.py       # Integration tests using MCP in-memory transport
```

**pyproject.toml structure:**

```toml
[project]
name = "mcp-server-mariadb"
version = "0.1.0"
description = "MCP server for MariaDB/MySQL via XAMPP"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.6.0",
    "pymysql>=1.1.0",
]

[project.scripts]
mcp-server-mariadb = "mcp_server_mariadb.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.8",
]
```

### 8. Testing Approach

**Three layers:**

1. **Unit tests** (`tests/test_database.py`):
   - Test `MariaDBDatabase` class with mocked connection
   - Test query validation logic
   - Test result formatting
   - Framework: pytest

2. **Integration tests** (`tests/test_server.py`):
   - Test MCP server using MCP's in-memory transport (per SDK docs)
   - Test against a real MariaDB instance (XAMPP)
   - Create test database, run queries, verify results
   - Requires: running MariaDB (XAMPP)
   - Framework: pytest + pytest-asyncio

3. **Manual testing**:
   - `mcp dev src/mcp_server_mariadb/server.py` -- MCP Inspector integration
   - Test with Claude Desktop configuration

**Note:** The MCP SDK provides `mcp.client.session.ClientSession` with in-memory transport for testing:

```python
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
# ... in-memory transport for testing
```

### 9. Additional Considerations

**Configuration priority** (highest to lowest):

1. CLI arguments (`--host`, `--port`, `--user`, `--password`, `--database`)
2. Environment variables (`MARIADB_HOST`, etc.)
3. Default values (localhost, 3306, root)

**Windows-specific:**

- `sys.stdin.reconfigure(encoding="utf-8")` required (see SQLite server)
- `PYTHONIOENCODING=utf-8` env var fallback
- Path handling: use `pathlib.Path` for any file operations

**XAMPP-specific:**

- MariaDB runs on port 3306 (same as MySQL default)
- Root user has no password by default in XAMPP -- DOCUMENT THIS
- Recommend: create a dedicated user for MCP access
- `mysql` database is accessible -- be careful

**Claude Desktop config example:**

```json
{
  "mcpServers": {
    "mariadb": {
      "command": "uv",
      "args": [
        "--directory", "C:\\Users\\desar\\OneDrive\\Escritorio\\MCP-XAMP",
        "run", "mcp-server-mariadb",
        "--host", "localhost",
        "--port", "3306",
        "--user", "root",
        "--password", "",
        "--database", "test"
      ],
      "env": {
        "MARIADB_ALLOW_WRITE": "false"
      }
    }
  }
}
```

## Recommendations

### Primary Recommendation: Phase 1 -- Read-Only Essentials

1. Start with PyMySQL (MIT, pure Python, small, MariaDB-friendly)
2. Use the low-level MCP Server API (proven pattern from SQLite reference)
3. Implement 5 tools: `list_databases`, `list_tables`, `describe_table`, `read_query`, `write_query`
4. Default to read-only mode with `--allow-write` opt-in flag
5. CLI args for connection params (host, port, user, password, database)
6. Connection-per-query strategy (simple, safe for stdio)
7. Project structure: `src/mcp_server_mariadb/` layout with makefile

### Future Enhancements (beyond Phase 1):

- SSE transport for team/server access
- Connection pooling for SSE mode
- MCP Resources exposing table schemas
- Query result caching for repeated schema queries
- Docker support (Dockerfile)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **SQL injection via LLM** | High -- could corrupt/destroy data | Query type validation (SELECT vs others); read-only default; row limits |
| **Credential leaks** | Medium -- DB access exposed | Env vars only; never log passwords; document security |
| **XAMPP root no-password** | High -- trivial DB access | Document strongly; prompt user to create dedicated user |
| **PyMySQL no async** | Low -- stdio is synchronous | If SSE added later, switch to PyMySQL+aiomysql or mysql-connector-python |
| **Connection drops** | Medium -- stale connections | Connection-per-query avoids this; add reconnect logic if using persistent connections |
| **Large result sets** | Medium -- context overflow | Default 1000-row limit; configurable |
| **GPL license risk** (if using mysql-connector-python) | Low-Medium | Use PyMySQL (MIT) instead -- no GPL concerns |

## Next Steps

1. **Proceed to SDD Proposal phase** (sdd-propose) -- formalize the scope, approach, and rollback plan
2. Create `pyproject.toml` and project skeleton
3. Install dependencies: `mcp[cli]`, `pymysql`, `pytest`
4. Implement `database.py` with MariaDB connection and query logic
5. Implement `server.py` with tool definitions
6. Write integration tests against XAMPP MariaDB
7. Configure Claude Desktop for testing

## References

- MCP Python SDK: <https://github.com/modelcontextprotocol/python-sdk> (v1.27.2)
- PyMySQL: <https://github.com/PyMySQL/PyMySQL> (v1.2.0, MIT)
- SQLite Reference Server (archived): <https://github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite>
- PostgreSQL Reference Server (archived): <https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres>
- MCP Specification: <https://modelcontextprotocol.io/specification/latest>
- MCP Server Testing Guide: <https://modelcontextprotocol.github.io/python-sdk/testing/>
