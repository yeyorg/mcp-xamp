# Proposal: MCP XAMPP Server

## Intent

Enable AI agents to interact with MariaDB/MySQL databases running on XAMPP through the Model Context Protocol. Agents need schema exploration and SQL query execution with a secure, read-first posture. No existing MCP server targets XAMPP's MariaDB with Python.

## Scope

### In Scope

- Five MCP tools: `list_databases`, `list_tables`, `describe_table`, `read_query`, `write_query`
- Every query tool requires a `database` parameter; missing it returns guidance to use `list_databases`
- PyMySQL driver (MIT, pure Python, no compilation)
- stdio transport via low-level `mcp.server.lowlevel.Server` API
- Configuration via `MCP_XAMP_*` environment variables with XAMPP defaults
- Query type validation, row limit (1000), query timeout (30s)

### Out of Scope

- SSE/HTTP transport (Phase 2)
- Connection pooling (no benefit for single-threaded stdio)
- MCP Resources or Prompts
- Docker support
- DDL-specific tools (CREATE TABLE folded into `write_query`)

## Capabilities

### New Capabilities

- `database-connection`: Credential sourcing, connection lifecycle, PyMySQL context manager per query
- `schema-exploration`: `list_databases`, `list_tables`, `describe_table` with structured output
- `query-execution`: `read_query` (SELECT only, validated) and `write_query` (INSERT/UPDATE/DELETE/DDL, opt-in)
- `security-model`: Read-only default, write opt-in via `MCP_XAMP_ALLOW_WRITE`, row limits, timeouts

### Modified Capabilities

None (greenfield project).

## Approach

Follow the archived SQLite MCP reference pattern: low-level Server API, stdio transport, connection-per-query. Each tool call opens a fresh PyMySQL connection and closes it immediately — simple, safe, no stale state.

**Project layout**: `src/mcp_xamp/server.py` (tool definitions), `src/mcp_xamp/database.py` (connection + query logic). Entry point `mcp-xamp` console script via `pyproject.toml`. Build with UV, automate with Make.

**Query safety**: `read_query` validates statement starts with SELECT/SHOW/DESCRIBE/EXPLAIN. `write_query` rejects mutations unless `MCP_XAMP_ALLOW_WRITE=true`. Missing `database` parameter returns: "Database parameter is required. Use list_databases to see available databases."

**Testing**: pytest with integration tests against a live XAMPP MariaDB instance. Test database created and torn down per session. MCP in-memory transport for server-level tests.

## Affected Areas

| Area | Impact | Description |
| --- | --- | --- |
| `src/mcp_xamp/` | New | Main package: server, database, \_\_main\_\_ |
| `pyproject.toml` | New | Metadata, deps (mcp, pymysql), entry point |
| `Makefile` | New | Automation: setup, test, lint, run |
| `tests/` | New | pytest suite with conftest fixtures |
| `.python-version` | New | Pin Python 3.13 |

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| LLM generates destructive SQL | Medium | Type validation; write opt-in flag; row limits |
| XAMPP root has no password | High | Document strongly; env var credentials; recommend dedicated user |
| PyMySQL lacks async (future SSE) | Low | Switch to aiomysql if SSE transport added |
| Large result sets overflow context | Medium | Default 1000-row limit; configurable via env var |

## Rollback Plan

Remove the package: `pip uninstall mcp-xamp` (or UV equivalent). Delete `openspec/changes/mcp-xamp-server/`. No database state is modified (read-only default; writes require explicit flag).

## Dependencies

- Python 3.13+ with UV package manager
- Running MariaDB/MySQL via XAMPP on localhost:3306
- PyPI: `mcp[cli]>=1.6.0`, `pymysql>=1.1.0`
- Dev: `pytest>=8.0`, `pytest-asyncio>=0.24`, `ruff>=0.8`

## Success Criteria

- [ ] AI agent lists databases and explores schema via MCP tools
- [ ] `read_query` executes SELECT and returns JSON rows
- [ ] `write_query` rejects mutations unless `MCP_XAMP_ALLOW_WRITE=true`
- [ ] Missing `database` parameter returns guidance referencing `list_databases`
- [ ] Integration tests pass against live XAMPP MariaDB
- [ ] Claude Desktop connects and executes queries via MCP configuration
