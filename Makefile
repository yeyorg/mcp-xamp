.PHONY: install install-global update test lint format run clean claude-setup opencode-setup

install:
	uv sync --group dev

install-global:
	uv tool install --python 3.13 .

update:
	git pull
	uv tool install --python 3.13 .
	@echo ""
	@echo "mcp-xamp actualizado. Reinicia tu CLI para aplicar los cambios."

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
	@echo "=== Global install (recommended) ==="
	@echo "  make install-global"
	@echo "  claude mcp add xamp -e MCP_XAMP_HOST=localhost -e MCP_XAMP_PORT=3306 -e MCP_XAMP_USER=root -e MCP_XAMP_PASSWORD= -e MCP_XAMP_ALLOW_WRITE=true -- mcp-xamp"
	@echo ""
	@echo "=== Without install (uv run) ==="
	@echo "  claude mcp add xamp -e MCP_XAMP_HOST=localhost -e MCP_XAMP_PORT=3306 -e MCP_XAMP_USER=root -e MCP_XAMP_PASSWORD= -e MCP_XAMP_ALLOW_WRITE=true -- uv run mcp-xamp"
	@echo ""
	@echo "=== Manual .mcp.json ==="
	@echo '{'
	@echo '  "mcpServers": {'
	@echo '    "xamp": {'
	@echo '      "command": "mcp-xamp",'
	@echo '      "args": [],'
	@echo '      "env": {'
	@echo '        "MCP_XAMP_HOST": "localhost",'
	@echo '        "MCP_XAMP_PORT": "3306",'
	@echo '        "MCP_XAMP_USER": "root",'
	@echo '        "MCP_XAMP_PASSWORD": "",'
	@echo '        "MCP_XAMP_ALLOW_WRITE": "true"'
	@echo '      }'
	@echo '    }'
	@echo '  }'
	@echo '}'

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
