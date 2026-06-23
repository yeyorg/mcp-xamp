# MCP-XAMP

> MCP server that gives Claude Code and OpenCode direct access to your XAMPP
> MariaDB/MySQL databases. Five tools: list databases, list tables, describe
> table, read query, write query.

## Quick Start

1. **Clone** the repo
2. **Configure** your AI agent (Claude Code or OpenCode)
3. **Start querying** — `list_databases`, `read_query`, etc.

No global install needed — runs directly with `uv run`.

---

## Requirements

- Python 3.13+
- XAMPP with MariaDB/MySQL running on `localhost:3306`
- [uv](https://docs.astral.sh/uv/)

---

## Installation

```bash
git clone https://github.com/<user>/mcp-xamp.git
cd mcp-xamp
uv sync
```

Verify it works:

```bash
uv run mcp-xamp
```

### Optional: install globally

If you prefer `mcp-xamp` available as a command anywhere:

```bash
uv tool install --python 3.13 .
```

Then use `"command": "mcp-xamp"` instead of `uv run --directory ...` in the
configs below.

---

## Claude Code Setup

### Option A: global install (recomendado)

Instala `mcp-xamp` como comando global y registralo en Claude Code:

```bash
uv tool install --python 3.13 .
```

Luego agregá el server MCP. Elegí el scope que prefieras:

```bash
# Scope project (crea .mcp.json en el directorio actual)
claude mcp add xamp \
  -e MCP_XAMP_HOST=localhost \
  -e MCP_XAMP_PORT=3306 \
  -e MCP_XAMP_USER=root \
  -e MCP_XAMP_PASSWORD= \
  -e MCP_XAMP_ALLOW_WRITE=true \
  -- mcp-xamp

# Scope user (disponible en todos tus proyectos)
claude mcp add --scope user xamp \
  -e MCP_XAMP_HOST=localhost \
  -e MCP_XAMP_PORT=3306 \
  -e MCP_XAMP_USER=root \
  -e MCP_XAMP_PASSWORD= \
  -e MCP_XAMP_ALLOW_WRITE=true \
  -- mcp-xamp
```

Ajusta los valores de las variables según tu instalacion de XAMPP.

### Option B: sin instalar (usando uv run)

Si preferis no instalar globalmente, apunta al directorio del repo:

```bash
claude mcp add xamp \
  -e MCP_XAMP_HOST=localhost \
  -e MCP_XAMP_PORT=3306 \
  -e MCP_XAMP_USER=root \
  -e MCP_XAMP_PASSWORD= \
  -e MCP_XAMP_ALLOW_WRITE=true \
  -- uv run --directory /ruta/a/mcp-xamp mcp-xamp
```

Reemplaza `/ruta/a/mcp-xamp` con la ruta real donde clonaste el repo.

### Config manual (archivo .mcp.json)

Si preferis editar el archivo a mano, tambien funciona:

```json
{
  "mcpServers": {
    "xamp": {
      "command": "mcp-xamp",
      "args": [],
      "env": {
        "MCP_XAMP_HOST": "localhost",
        "MCP_XAMP_PORT": "3306",
        "MCP_XAMP_USER": "root",
        "MCP_XAMP_PASSWORD": "",
        "MCP_XAMP_ALLOW_WRITE": "true"
      }
    }
  }
}
```

Si no instalaste globalmente, usa `"command": "uv"` con los args correspondientes
(ver el `.mcp.json` de este repo como referencia).

### Verify

Dentro de Claude Code, corre `/mcp` para confirmar que `xamp` aparece como
conectado. Despues proba:

```
List all databases on my XAMPP server.
```

---

## OpenCode Setup

### Config location

OpenCode reads MCP config from `opencode.json` or `opencode.jsonc`. The file
can be in:

| Location | Scope |
| --- | --- |
| `<project-root>/opencode.json` | Project-specific |
| `<project-root>/.opencode/opencode.json` | Project-specific (alt) |
| `~/.config/opencode/opencode.json` | Global (all projects) |

### Add the MCP server

Add this block to your `opencode.json` or `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "xamp": {
      "type": "local",
      "command": ["uv", "run", "--directory", "/path/to/mcp-xamp", "mcp-xamp"],
      "enabled": true,
      "environment": {
        "MCP_XAMP_ALLOW_WRITE": "true"
      }
    }
  }
}
```

Replace `/path/to/mcp-xamp` with your actual clone path.

If you used `uv tool install`, simplify to:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "xamp": {
      "type": "local",
      "command": ["mcp-xamp"],
      "enabled": true,
      "environment": {
        "MCP_XAMP_ALLOW_WRITE": "true"
      }
    }
  }
}
```

### Verify

Restart OpenCode, then try:

```
Show me all databases on the xamp server. use xamp tools
```

---

## Environment Variables

All configuration goes through environment variables. Sensible defaults for a
standard XAMPP installation.

| Variable | Default | Description |
| --- | --- | --- |
| `MCP_XAMP_HOST` | `127.0.0.1` | MariaDB/MySQL host |
| `MCP_XAMP_PORT` | `3306` | MariaDB/MySQL port |
| `MCP_XAMP_USER` | `root` | Database user |
| `MCP_XAMP_PASSWORD` | (empty) | Database password |
| `MCP_XAMP_ALLOW_WRITE` | `false` | Set to `true` to enable INSERT/UPDATE/DELETE/DDL |

Credentials are read from environment variables **only**. They never appear in
tool arguments, log output, or error messages.

---

## Tools

| Tool | Description | Requires |
| --- | --- | --- |
| `list_databases` | Show all accessible databases | — |
| `list_tables` | Show tables in a database | `database` |
| `describe_table` | Show columns, types, and keys | `database`, `table` |
| `read_query` | Execute SELECT / SHOW / DESCRIBE / EXPLAIN | `database`, `query` |
| `write_query` | Execute INSERT / UPDATE / DELETE / DDL | `database`, `query`, `MCP_XAMP_ALLOW_WRITE=true` |

---

## Security

- **Read-only by default.** Write operations require `MCP_XAMP_ALLOW_WRITE=true`.
- **Credentials never logged.** Host, port, user, and password are stripped from
  error messages.
- **Credentials only from env vars.** No tool parameters, no config files,
  no CLI args.
- **Connection-per-query.** Each tool invocation opens and closes its own
  connection — no shared state, no stale connections.
- **XAMPP default is root with no password.** Create a dedicated user for
  production use:

  ```sql
  CREATE USER 'mcp_agent'@'127.0.0.1' IDENTIFIED BY 'secure_password';
  GRANT SELECT ON *.* TO 'mcp_agent'@'127.0.0.1';
  ```

---

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest -v --cov=src/mcp_xamp

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/
```

---

## License

MIT — see [LICENSE](LICENSE).
