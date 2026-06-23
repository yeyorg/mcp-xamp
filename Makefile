.PHONY: install install-global test lint format run clean claude-setup opencode-setup

install:
	uv sync --group dev

install-global:
	uv tool install --python 3.13 .

test:
	uv run pytest -v --cov=src/mcp_xamp --cov-report=term-missing

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

run:
	uv run mcp-xamp

claude-setup:
	@echo ""
	@echo "Run this command (replace /path/to/mcp-xamp with your clone path):"
	@echo "  claude mcp add --transport stdio --scope project --env MCP_XAMP_ALLOW_WRITE=true xamp -- uv run --directory /path/to/mcp-xamp mcp-xamp"
	@echo ""
	@echo "Or add this to your ~/.claude.json or project .mcp.json:"
	@echo '{'
	@echo '  "mcpServers": {'
	@echo '    "xamp": {'
	@echo '      "command": "uv",'
	@echo '      "args": ["run", "--directory", "/path/to/mcp-xamp", "mcp-xamp"],'
	@echo '      "env": { "MCP_XAMP_ALLOW_WRITE": "true" }'
	@echo '    }'
	@echo '  }'
	@echo '}'
	@echo ""
	@echo "Or install globally first (make install-global) then use:"
	@echo "  claude mcp add --transport stdio --scope project --env MCP_XAMP_ALLOW_WRITE=true xamp -- mcp-xamp"

opencode-setup:
	@echo ""
	@echo "Add this to your opencode.json, .opencode/opencode.json, or ~/.config/opencode/opencode.json"
	@echo "(replace /path/to/mcp-xamp with your clone path):"
	@echo '{'
	@echo '  "mcp": {'
	@echo '    "xamp": {'
	@echo '      "type": "local",'
	@echo '      "command": ["uv", "run", "--directory", "/path/to/mcp-xamp", "mcp-xamp"],'
	@echo '      "enabled": true,'
	@echo '      "environment": {'
	@echo '        "MCP_XAMP_ALLOW_WRITE": "true"'
	@echo '      }'
	@echo '    }'
	@echo '  }'
	@echo '}'

clean:
	powershell -Command "Get-ChildItem -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force"
	powershell -Command "Get-ChildItem -Recurse -Directory -Filter '.pytest_cache' | Remove-Item -Recurse -Force"
	powershell -Command "if (Test-Path .coverage) { Remove-Item .coverage -Force }"
	powershell -Command "if (Test-Path dist) { Remove-Item dist -Recurse -Force }"
