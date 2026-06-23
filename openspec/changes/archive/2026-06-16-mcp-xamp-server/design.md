# Design: MCP XAMPP Server

## Technical Approach

Greenfield `src/mcp_xamp/` package exposing 5 MCP tools via stdio transport. Uses `mcp.server.lowlevel.Server` + PyMySQL with connection-per-query lifecycle — each tool call opens a fresh connection and closes it via context manager. Read-first security: `read_query` validates SELECT/SHOW/DESCRIBE/EXPLAIN prefix only; `write_query` gated behind `MCP_XAMP_ALLOW_WRITE=true`. Credentials exclusively from `MCP_XAMP_*` env vars with XAMPP defaults (127.0.0.1:3306/root/empty-password). Architecture splits `db/` (connection, schema, execution) from `security/` (validation, sanitization) following the 4-capability design mandate from the proposal.

## Architecture Decisions

| Decision | Choice | Alternatives rejected | Rationale |
| --- | --- | --- | --- |
| Module layout | `db/` + `security/` subpackages | Single `database.py` (SQLite ref) | 4 distinct capabilities; separate concerns improve test isolation and match design mandate |
| Credential source | `MCP_XAMP_*` env vars only | CLI args + env vars (exploration notes) | Spec mandates env-only; prevents `ps` leaks on shared hosts |
| Row limit strategy | `cursor.fetchmany(N+1)` | Append `LIMIT N` to SQL | Parsing UNION/subqueries for LIMIT is fragile; fetchmany guarantees cap without SQL rewriting |
| Query type detection | `query.strip().upper().split()[0]` | Full regex tokenizer or sqlparse | First keyword determines statement type; sufficient for prefix matching without third-party dependency |
| Write gate location | `server.py` handler, before connection | Inside db/executor.py | Fail-fast: reject writes before consuming any DB resource |
| Transaction model | Autocommit + explicit rollback on error | Explicit BEGIN/COMMIT/ROLLBACK | PyMySQL defaults `autocommit=True`; write_query wraps execution in try/except with `conn.rollback()` |
| Error language | Spanish (rioplatense) for UX messages | English | Spec mandates specific Spanish messages; internal log messages remain English |

## Data Flow

```text
MCP Client ──(stdio JSON-RPC)──▶ server.py: call_tool()
    │                                │
    │                    ┌───────────┤
    │                    ▼           ▼
    │              validator.py  connection.py
    │              · require_db() ConnectionFactory
    │              · check_write() .connect(db)
    │              · validate_type()   │
    │                    │             ▼
    │                    │       PyMySQL connection
    │                    │       (context manager)
    │                    ▼             │
    │              schema.py      executor.py
    │              (list_dbs,     (read_query,
    │               list_tbls,     write_query)
    │               desc_tbl)         │
    │                    │            │
    │                    ▼            ▼
    │               Formatted result (dict)
    │
    │  Error path: sanitizer.py strips
    │  host/user/password from exceptions
    ▼
MCP Client ◀── TextContent (isError=False|True)
```

## File Changes

| File | Action | Description |
| --- | --- | --- |
| `src/mcp_xamp/__init__.py` | Create | Package marker |
| `src/mcp_xamp/server.py` | Create | MCP Server init, 5 tool handlers, `main()` entry |
| `src/mcp_xamp/db/__init__.py` | Create | DB subpackage |
| `src/mcp_xamp/db/connection.py` | Create | `ConnectionFactory`: from_env(), connect(database) context manager |
| `src/mcp_xamp/db/schema.py` | Create | `list_databases`, `list_tables`, `describe_table` |
| `src/mcp_xamp/db/executor.py` | Create | `read_query`, `write_query`, `format_results` |
| `src/mcp_xamp/security/__init__.py` | Create | Security subpackage |
| `src/mcp_xamp/security/validator.py` | Create | `validate_read_query`, `check_write_allowed`, `require_database` |
| `src/mcp_xamp/security/sanitizer.py` | Create | `sanitize_error(exc)` — strips connection params |
| `src/mcp_xamp/types.py` | Create | Error hierarchy (7 classes), constants, `QueryResult` TypedDict |
| `pyproject.toml` | Create | Metadata, deps (mcp, pymysql), scripts entry `mcp-xamp` |
| `Makefile` | Create | Targets: install, test, lint, format, run, clean |
| `.python-version` | Create | Pin `3.13` |
| `tests/conftest.py` | Create | Fixtures: test DB create/drop, MCP in-memory transport |
| `tests/test_connection.py` | Create | Unit: env var parsing, error mapping |
| `tests/test_validator.py` | Create | Unit: query type detection, write gate, db param check |
| `tests/test_schema.py` | Create | Integration: list_dbs, list_tbls, desc_tbl vs real MariaDB |
| `tests/test_executor.py` | Create | Integration: read_query, write_query, row limits, error sanitization |

## Interfaces

**Error hierarchy:**

```python
XampError(RuntimeError)
├── XampConnectionError     # connect timeout, connection refused, unknown host
├── XampAuthError           # wrong password, access denied
├── XampTimeoutError        # read_timeout exceeded
├── XampQueryError          # syntax error, constraint violation
├── XampDatabaseError       # database not found
├── XampWriteRejectedError  # write gate blocks execution
└── XampMissingDatabaseError # database parameter absent
```

**ConnectionFactory.connect()** returns a context manager: `with factory.connect(database) as conn:` — conn auto-closes on exit. Defaults: host `127.0.0.1`, port `3306`, user `root`, password `""`, connect_timeout `5`, read_timeout `30`.

**Result format:** `{"columns": ["id", "name"], "rows": [[1, "Ana"]]}` for read queries; `{"affected_rows": 1}` for write queries.

**Write gate:** `security/validator.py` provides `check_write_allowed()` called in `server.py` before the write_query handler opens a connection. Reads `MCP_XAMP_ALLOW_WRITE` from env, raises `XampWriteRejectedError` if not `"true"`.

## Testing Strategy

| Layer | What | Approach |
| --- | --- | --- |
| Unit | validator, sanitizer, ConnectionFactory.from_env | Mock `os.environ`; parametrize query strings; no database required |
| Unit | Result formatting | Mock `cursor.description` and `cursor.fetchmany` |
| Integration | All 5 tools end-to-end | Real XAMPP MariaDB; fixture creates/drops `mcp_xamp_test` database with sample tables |
| Integration | Write gate, error sanitization | Toggle `MCP_XAMP_ALLOW_WRITE`; assert errors lack host/user/password |

Coverage target: 85%+ line coverage. Integration tests skip gracefully via `pytest.skip` if MariaDB is unavailable.

## Makefile Targets

| Target | Command |
| --- | --- |
| `install` | `uv sync --group dev` |
| `test` | `uv run pytest -v --cov=src/mcp_xamp` |
| `lint` | `uv run ruff check src/ tests/` |
| `format` | `uv run ruff format src/ tests/` |
| `run` | `uv run mcp-xamp` |
| `clean` | Remove `__pycache__/`, `.coverage`, `.pytest_cache/` |

## Migration / Rollout

No migration required. Greenfield project. Rollback: `uv pip uninstall mcp-xamp` and delete the source tree.

## Open Questions

None. All 12 requirements and 35 scenarios from the 4 delta specs are unambiguous and self-contained.
