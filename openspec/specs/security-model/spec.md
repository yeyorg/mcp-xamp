# Security Model Specification

## Purpose

Defensive posture for the MCP XAMPP server: read-only by default, write opt-in via explicit flag, SQL injection prevention, credential safety, and non-leaking error messages. These rules apply across all tools.

## Requirements

### Requirement: Read-Only Default

The system MUST default to read-only operations. Any mutation (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `REVOKE`) MUST be rejected unless `MCP_XAMP_ALLOW_WRITE=true` is set in the environment.

The `read_query` tool MUST enforce this at the query-type level regardless of the write flag — it MUST never execute mutations.

#### Scenario: read_query blocks mutation with write flag off

- **Given** `MCP_XAMP_ALLOW_WRITE` is not set
- **When** `read_query` receives `INSERT INTO t VALUES (1)`
- **Then** the query is rejected before reaching the database

#### Scenario: read_query blocks mutation with write flag on

- **Given** `MCP_XAMP_ALLOW_WRITE=true`
- **When** `read_query` receives `DELETE FROM t`
- **Then** the query is rejected before reaching the database — `read_query` never mutates

#### Scenario: write_query blocks mutation with write flag off

- **Given** `MCP_XAMP_ALLOW_WRITE` is not set
- **When** `write_query` receives `DROP TABLE users`
- **Then** the query is rejected before reaching the database

#### Scenario: write_query allows mutation with write flag on

- **Given** `MCP_XAMP_ALLOW_WRITE=true`
- **When** `write_query` receives `INSERT INTO t VALUES (1)`
- **Then** the query is executed

### Requirement: SQL Injection Prevention

The system MUST use parameterized queries (`cursor.execute(sql, params)`) wherever values are passed. Query type validation MUST be performed before execution by inspecting the statement prefix — never by regex alone. Raw string concatenation for SQL values MUST NOT be used.

#### Scenario: Parameterized query used for user-supplied values

- **Given** a query with dynamic values
- **When** the query is executed
- **Then** `cursor.execute(sql, params)` is called with values separated from the SQL string

#### Scenario: Malicious input rejected by query type validation

- **Given** a query string `"SELECT * FROM users; DROP TABLE users; --"`
- **When** query-type validation is performed for `read_query`
- **Then** only the prefix `SELECT` is matched; the trailing `DROP` does not bypass the check because the statement is validated before execution

### Requirement: Credential Safety

The system MUST NOT log, display, or return database credentials (host, port, user, password) in any response, error message, or log output. Credentials MUST be sourced exclusively from environment variables `MCP_XAMP_*`.

#### Scenario: Credentials not in connection error

- **Given** a connection failure due to wrong password
- **When** the error is returned to the MCP client
- **Then** the error message does not contain the password, username, or host

#### Scenario: Credentials not in successful responses

- **Given** a successful `list_databases` call
- **When** the response is returned
- **Then** the response does not contain any credential values or environment variable names

#### Scenario: Credentials not in log output

- **Given** the server is running with logging enabled
- **When** a connection is opened
- **Then** log messages do not contain the password, host, or port values

### Requirement: Error Message Safety

The system MUST NOT leak internal connection details (host, port, user, database engine version) in error messages returned to MCP clients. Error messages MUST be descriptive enough to diagnose the issue but MUST sanitize sensitive information.

#### Scenario: MySQL error without connection details

- **Given** a `ProgrammingError` from PyMySQL containing the host and database name
- **When** the error is mapped to an MCP tool response
- **Then** the response contains the SQL error code and message but not the host, port, or username

#### Scenario: Timeout error returned safely

- **Given** a query exceeds the 30-second timeout
- **When** the error is returned
- **Then** the response indicates a timeout occurred without exposing server configuration details
