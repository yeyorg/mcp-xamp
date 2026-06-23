# Query Execution Specification

## Purpose

Two MCP tools for SQL execution: `read_query` (read-only SELECT) and `write_query` (mutations and DDL, opt-in). Both require a `database` parameter and enforce safety constraints: query type validation, row limits, and timeouts.

## Requirements

### Requirement: Read Query

The system MUST provide a `read_query(database: str, query: str)` tool that executes read-only SQL statements. The `database` parameter is MANDATORY.

The system MUST validate that `query` begins with `SELECT`, `SHOW`, `DESCRIBE`, or `EXPLAIN` (case-insensitive). Statements starting with `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, or `REVOKE` MUST be rejected.

#### Scenario: Valid SELECT executed

- **Given** database `test_xamp` with table `users` containing rows `[{id: 1, name: "Ana"}]`
- **When** `read_query(database="test_xamp", query="SELECT * FROM users")` is invoked
- **Then** the response contains a structured result with columns `["id", "name"]` and rows `[[1, "Ana"]]`

#### Scenario: SHOW TABLES executed

- **Given** database `test_xamp` with tables `users` and `orders`
- **When** `read_query(database="test_xamp", query="SHOW TABLES")` is invoked
- **Then** the response includes `users` and `orders` as rows

#### Scenario: INSERT rejected by read_query

- **Given** database `test_xamp` with table `users`
- **When** `read_query(database="test_xamp", query="INSERT INTO users (name) VALUES ('Hacker')")` is invoked
- **Then** an error response is returned: "read_query solo permite SELECT, SHOW, DESCRIBE y EXPLAIN. Para escrituras usá write_query."

#### Scenario: DELETE rejected by read_query

- **Given** database `test_xamp` with table `users`
- **When** `read_query(database="test_xamp", query="DELETE FROM users WHERE id=1")` is invoked
- **Then** an error response is returned indicating the query type is not allowed for read_query

#### Scenario: DROP rejected by read_query

- **Given** database `test_xamp` with table `users`
- **When** `read_query(database="test_xamp", query="DROP TABLE users")` is invoked
- **Then** an error response is returned indicating the query type is not allowed for read_query

#### Scenario: Database parameter missing

- **Given** any MariaDB instance
- **When** `read_query(query="SELECT 1")` is invoked without a `database` argument
- **Then** an error response is returned: "El parámetro database es obligatorio. Usá list_databases para ver las bases disponibles."

#### Scenario: Empty result set

- **Given** database `test_xamp` with table `users` containing zero rows
- **When** `read_query(database="test_xamp", query="SELECT * FROM users")` is invoked
- **Then** the response contains column names and an empty rows list, with no error

#### Scenario: Syntax error in query

- **Given** database `test_xamp`
- **When** `read_query(database="test_xamp", query="SELEC * FROM users")` is invoked
- **Then** an error response is returned with the MySQL error message without exposing connection details

#### Scenario: Row limit enforced

- **Given** table `logs` with 5000 rows and the default row limit of 1000
- **When** `read_query(database="test_xamp", query="SELECT * FROM logs")` is invoked
- **Then** the response contains at most 1000 rows

### Requirement: Write Query

The system MUST provide a `write_query(database: str, query: str)` tool. Execution MUST be gated by `MCP_XAMP_ALLOW_WRITE=true`. The `database` parameter is MANDATORY.

When the write flag is enabled, `write_query` MUST execute `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE` statements. It MAY also execute read statements but `read_query` is the recommended tool for those.

#### Scenario: Write flag disabled, INSERT rejected

- **Given** `MCP_XAMP_ALLOW_WRITE` is not set
- **When** `write_query(database="test_xamp", query="INSERT INTO users (name) VALUES ('Test')")` is invoked
- **Then** an error response is returned: "Las operaciones de escritura están deshabilitadas. Configurá MCP_XAMP_ALLOW_WRITE=true para habilitarlas."

#### Scenario: Write flag enabled, INSERT executed

- **Given** `MCP_XAMP_ALLOW_WRITE=true` and database `test_xamp` with table `users`
- **When** `write_query(database="test_xamp", query="INSERT INTO users (name) VALUES ('Test')")` is invoked
- **Then** the response contains `{"affected_rows": 1}` and the row is persisted

#### Scenario: Write flag enabled, UPDATE executed

- **Given** `MCP_XAMP_ALLOW_WRITE=true` and row `{id: 1, name: "Old"}`
- **When** `write_query(database="test_xamp", query="UPDATE users SET name='New' WHERE id=1")` is invoked
- **Then** the response contains `{"affected_rows": 1}` and the name is updated

#### Scenario: Write flag enabled, DDL executed

- **Given** `MCP_XAMP_ALLOW_WRITE=true` and database `test_xamp`
- **When** `write_query(database="test_xamp", query="CREATE TABLE temp (id INT)")` is invoked
- **Then** the response contains `{"affected_rows": 0}` and table `temp` exists in the database

#### Scenario: Syntax error on rollback

- **Given** `MCP_XAMP_ALLOW_WRITE=true` and database `test_xamp`
- **When** `write_query(database="test_xamp", query="INSERT INTO nonexistent_table (x) VALUES (1)")` is invoked
- **Then** an error response is returned with the MySQL error and no data is modified

#### Scenario: Database parameter missing

- **Given** `MCP_XAMP_ALLOW_WRITE=true`
- **When** `write_query(query="UPDATE users SET name='X'")` is invoked without `database`
- **Then** an error response is returned: "El parámetro database es obligatorio. Usá list_databases para ver las bases disponibles."
