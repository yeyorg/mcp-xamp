# Schema Exploration Specification

## Purpose

Three MCP tools for database schema discovery: `list_databases`, `list_tables`, and `describe_table`. Each returns structured data with graceful error handling for missing databases, permission denials, and empty results.

## Requirements

### Requirement: List Databases

The system MUST provide a `list_databases` tool that returns all accessible databases, including system databases (`mysql`, `information_schema`, `performance_schema`).

#### Scenario: Standard databases returned

- **Given** a running MariaDB instance with default databases
- **When** `list_databases` is invoked
- **Then** the response includes `mysql`, `information_schema`, `performance_schema` in the list

#### Scenario: User databases included

- **Given** a MariaDB instance with a database named `test_xamp`
- **When** `list_databases` is invoked
- **Then** the response includes `test_xamp` alongside system databases

#### Scenario: Connection failure

- **Given** MariaDB is unreachable
- **When** `list_databases` is invoked
- **Then** an error response is returned with a connection failure message that does not expose credentials or host

### Requirement: List Tables

The system MUST provide a `list_tables(database: str)` tool that lists all tables in the specified database. The `database` parameter is MANDATORY.

#### Scenario: Tables returned for valid database

- **Given** database `test_xamp` contains tables `users` and `orders`
- **When** `list_tables(database="test_xamp")` is invoked
- **Then** the response includes `users` and `orders` in the table list

#### Scenario: Empty database

- **Given** database `test_xamp` exists but contains no tables
- **When** `list_tables(database="test_xamp")` is invoked
- **Then** an empty list is returned with no error

#### Scenario: Database parameter missing

- **Given** any MariaDB instance
- **When** `list_tables` is invoked without a `database` argument
- **Then** an error response is returned: "El parámetro database es obligatorio. Usá list_databases para ver las bases disponibles."

#### Scenario: Database does not exist

- **Given** no database named `nonexistent_db` exists
- **When** `list_tables(database="nonexistent_db")` is invoked
- **Then** an error response is returned indicating the database was not found

#### Scenario: Permission denied

- **Given** the configured user lacks `SELECT` on database `restricted_db`
- **When** `list_tables(database="restricted_db")` is invoked
- **Then** an error response is returned indicating insufficient permissions without exposing user details

### Requirement: Describe Table

The system MUST provide a `describe_table(database: str, table: str)` tool that returns the full schema of a table: column names, types, nullability, keys, defaults, and extra info (`AUTO_INCREMENT`, `ON UPDATE`).

#### Scenario: Full table structure returned

- **Given** database `test_xamp` has table `users` with columns `id INT PRIMARY KEY AUTO_INCREMENT`, `name VARCHAR(100) NOT NULL`, `email VARCHAR(255) DEFAULT NULL`
- **When** `describe_table(database="test_xamp", table="users")` is invoked
- **Then** the response includes for each column: `Field`, `Type`, `Null`, `Key`, `Default`, `Extra`

#### Scenario: Table with indexes and foreign keys

- **Given** table `orders` has a foreign key `user_id` referencing `users(id)` and an index on `created_at`
- **When** `describe_table(database="test_xamp", table="orders")` is invoked
- **Then** the response includes index information and foreign key constraints

#### Scenario: Table does not exist

- **Given** no table named `ghost` exists in database `test_xamp`
- **When** `describe_table(database="test_xamp", table="ghost")` is invoked
- **Then** an error response is returned indicating the table was not found

#### Scenario: Database parameter missing

- **Given** any MariaDB instance
- **When** `describe_table` is invoked with `table="users"` but no `database`
- **Then** an error response is returned: "El parámetro database es obligatorio. Usá list_databases para ver las bases disponibles."
