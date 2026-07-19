PYTHON ?= .venv/bin/python
PYTEST ?= $(PYTHON) -m pytest
CURL ?= curl

.PHONY: help all run-all api api-dev mcp mcp-http mcp-sse docs health-api test tests run-tests

help:
	@echo "AVGE server commands"
	@echo ""
	@echo "  make run-all    Run API (:8000) and MCP HTTP (:8002)"
	@echo "  make all        Alias for run-all"
	@echo "  make api        Run FastAPI HTTP server on :8000"
	@echo "  make api-dev    Run FastAPI HTTP server on :8000 with reload"
	@echo "  make mcp-http   Run MCP Streamable HTTP server on :8002"
	@echo "  make mcp-sse    Run MCP SSE server on :8001"
	@echo "  make mcp        Run MCP stdio server"
	@echo "  make docs       Print generated MCP tool docs"
	@echo "  make health-api Check API health endpoint"
	@echo "  make run-tests  Run test suite"
	@echo "  make tests      Alias for run-tests"
	@echo "  make test       Alias for run-tests"

all: run-all

run-all:
	@trap 'kill 0' INT TERM EXIT; \
	$(PYTHON) -m avge_engine api & \
	$(PYTHON) -m avge_engine mcp-http & \
	wait

api:
	$(PYTHON) -m avge_engine api

api-dev:
	$(PYTHON) -m avge_engine dev

mcp:
	$(PYTHON) -m avge_engine mcp

mcp-http:
	$(PYTHON) -m avge_engine mcp-http

mcp-sse:
	$(PYTHON) -m avge_engine mcp-sse

docs:
	$(PYTHON) -m avge_engine docs

health-api:
	$(CURL) -fsS http://127.0.0.1:8000/health

test tests run-tests:
	$(PYTEST)
