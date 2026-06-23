# Tasks: MCP XAMPP Server

## Review Workload Forecast

| Field | Value |
| --- | --- |
| Estimated changed lines | ~1000 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation+Types → PR 2: DB Layer → PR 3: Server+Tests |
| Delivery strategy | ask-on-risk |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

**Resolution**: `size:exception` — approved by maintainer, single changeset.

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
| --- | --- | --- | --- |
| 1 | Project scaffolding, types, security module | PR 1 | ~190 source lines; unit-testable independently |
| 2 | Database layer (connection, schema, executor) | PR 2 | ~220 source lines; depends on PR 1 types/errors |
| 3 | MCP server wiring + test suite | PR 3 | ~650 lines total; depends on PR 2 db modules |

## Phase 1: Project Foundation

- [x] 1.1 Create `pyproject.toml` with UV config, mcp+pymysql deps, dev group (pytest, ruff, pytest-cov), entry script `mcp-xamp`
- [x] 1.2 Create `Makefile` with install, test, lint, format, run, clean targets
- [x] 1.3 Create package structure: `src/mcp_xamp/` with `db/`, `security/` subpackages, `__init__.py` files, and `tests/` directory
- [x] 1.4 Create `.python-version` (3.13) and `.gitignore`

## Phase 2: Core Types & Security

- [x] 2.1 Implement `src/mcp_xamp/types.py`: 7 error classes (XampError hierarchy), READ_KEYWORDS set, QUERY_TIMEOUT, MAX_ROWS constants, QueryResult TypedDict
- [x] 2.2 Implement `src/mcp_xamp/security/validator.py`: `validate_read_query(sql)`, `check_write_allowed()`, `require_database(database)`
- [x] 2.3 Implement `src/mcp_xamp/security/sanitizer.py`: `sanitize_error(exc)` strips connection params from messages

## Phase 3: Database Layer

- [x] 3.1 Implement `src/mcp_xamp/db/connection.py`: `ConnectionFactory` class with `from_env()` and `connect(database)` context manager
- [x] 3.2 Implement `src/mcp_xamp/db/schema.py`: `list_databases(factory)`, `list_tables(factory, database)`, `describe_table(factory, database, table)`
- [x] 3.3 Implement `src/mcp_xamp/db/executor.py`: `read_query(factory, database, query)`, `write_query(factory, database, query)`, `format_results(cursor)`

## Phase 4: MCP Server

- [x] 4.1 Implement `src/mcp_xamp/server.py`: stdio server, 5 tool handlers with write gate, Spanish error messages, `main()` entry point

## Phase 5: Tests

- [x] 5.1 Create `tests/conftest.py`: MariaDB availability check, test database fixture
- [x] 5.2 Write unit tests: `test_validator.py`, `test_sanitizer.py`, `test_connection.py` (mock os.environ, no DB needed)
- [x] 5.3 Write integration tests: `test_schema.py`, `test_executor.py`, `test_server.py` against real MariaDB (skip via pytest.skip if unavailable)

## Implementation Notes

- `uv sync --group dev` installed all 41 packages successfully
- All 49 unit tests pass; 3 integration tests gracefully skip when MariaDB is unavailable
- Ruff lint passes with zero errors
- MCP SDK version 1.27.2, PyMySQL 1.2.0
- Integration tests require MariaDB with matching `MCP_XAMP_*` credentials (currently root password is set, so tests skip)
