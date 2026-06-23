# Database Connection Specification

## Purpose

Connection management for XAMPP MariaDB/MySQL via PyMySQL. Covers credential sourcing from environment variables, connection lifecycle (per-query open/close), and error handling for connection failures.

## Requirements

### Requirement: Credential Sourcing

The system MUST read database credentials exclusively from `MCP_XAMP_*` environment variables with XAMPP defaults.

| Variable | Default | Required |
|----------|---------|----------|
| `MCP_XAMP_HOST` | `127.0.0.1` | No |
| `MCP_XAMP_PORT` | `3306` | No |
| `MCP_XAMP_USER` | `root` | No |
| `MCP_XAMP_PASSWORD` | `""` (empty) | No |

The system MUST NOT accept credentials from tool parameters, config files, or command-line arguments.

#### Scenario: All variables set

- **Given** `MCP_XAMP_HOST=db.example.com`, `MCP_XAMP_PORT=3307`, `MCP_XAMP_USER=agent`, `MCP_XAMP_PASSWORD=s3cret`
- **When** any tool opens a connection
- **Then** PyMySQL connects to `db.example.com:3307` as user `agent` with password `s3cret`

#### Scenario: Defaults applied when variables absent

- **Given** no `MCP_XAMP_*` environment variables are set
- **When** any tool opens a connection
- **Then** PyMySQL connects to `127.0.0.1:3306` as user `root` with empty password

#### Scenario: Partial override

- **Given** only `MCP_XAMP_PASSWORD=my_pass` is set, others absent
- **When** a connection is opened
- **Then** host defaults to `127.0.0.1`, port to `3306`, user to `root`, password is `my_pass`

### Requirement: Connection Lifecycle

The system MUST open a fresh PyMySQL connection per tool invocation and MUST close it immediately after the query completes (success or failure). Each connection MUST use a context manager (`with`) to guarantee cleanup.

#### Scenario: Successful query disposes connection

- **Given** a valid connection is opened for `list_databases`
- **When** the query returns results
- **Then** the connection is closed before the tool returns its response

#### Scenario: Failed query disposes connection

- **Given** a connection is opened for `read_query` with a syntax error
- **When** PyMySQL raises a `ProgrammingError`
- **Then** the connection is closed within the context manager's `__exit__` and the error propagates as a tool error response

#### Scenario: Concurrent tool calls each get independent connections

- **Given** two agents invoke tools simultaneously against the same server
- **When** each tool call reaches the connection logic
- **Then** each call opens its own connection with no shared state

### Requirement: Error Handling

The system MUST return descriptive error messages when connection fails. Error messages MUST NOT leak credentials, host, or port values.

#### Scenario: Connection refused

- **Given** no MariaDB is running at the configured host/port or `MCP_XAMP_HOST=down.host.example`
- **When** any tool attempts to connect
- **Then** an error response is returned with a message indicating connection failure without exposing the host or port

#### Scenario: Authentication failure

- **Given** `MCP_XAMP_PASSWORD=wrong_password`
- **When** any tool attempts to connect
- **Then** an error response is returned with a message indicating authentication failure without exposing the password or username

#### Scenario: Unknown host

- **Given** `MCP_XAMP_HOST=does.not.exist.local`
- **When** any tool attempts to connect
- **Then** an error response is returned with a message indicating the host could not be resolved without exposing the hostname
