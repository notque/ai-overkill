# Python FastMCP Server Scaffold Template

Reference for Phase 3 GENERATE when `--python` flag is set. Use these patterns for Python MCP servers.

---

## When to Use Python Mode

Generate a Python FastMCP server (instead of TypeScript) when:
1. The user explicitly passes `--python`, AND
2. The target repo is a Python project (has `pyproject.toml`, `setup.py`, or `requirements.txt`)

Python mode is preferred when the target exports an installable package that can be imported directly (`--import` flag). Otherwise, TypeScript is simpler and more type-safe.

---

## Directory Structure

```
{service}-mcp-server/
  pyproject.toml
  src/
    main.py       ← @mcp.tool decorators, mcp.run()
    client.py     ← Shared client class (HTTP or subprocess)
  README.md
```

---

## `pyproject.toml` Template

```toml
[project]
name = "{service}-mcp-server"
version = "0.1.0"
description = "MCP server for {Service Name}"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=0.1.0",
    "httpx>=0.27.0",        # For HTTP client; remove if not needed
    "pydantic>=2.0.0",      # Included transitively by fastmcp
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

---

## `src/main.py` Template

```python
"""
{Service Name} MCP server.

Provides tools for {one-line purpose}.

Environment variables:
    SERVICE_API_KEY: Required. API key for authenticating with {Service Name}.
"""

import os
import json
from typing import Annotated

import fastmcp
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .client import ServiceClient

# Validate required env vars at startup
_API_KEY = os.environ.get("SERVICE_API_KEY")
if not _API_KEY:
    raise ValueError(
        "SERVICE_API_KEY environment variable is required. "
        "Set it before starting the server."
    )

# Initialize FastMCP
mcp = FastMCP("{service}-mcp-server")

# Initialize shared client
_client = ServiceClient(api_key=_API_KEY)

# --- Tool parameter models (Pydantic v2) ---

class GetIssueParams(BaseModel):
    owner: str = Field(description="Repository owner or organization name")
    repo: str = Field(description="Repository name")
    issue_number: int = Field(description="Issue number", gt=0)

class ListIssuesParams(BaseModel):
    owner: str = Field(description="Repository owner or organization name")
    repo: str = Field(description="Repository name")
    state: str = Field(default="open", description="Filter by state: open, closed, all")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results. Default: 20")

# --- Tools ---

@mcp.tool(
    description="Get a single issue by number. Returns title, description, state, labels, and assignees."
)
def service_get_issue(params: GetIssueParams) -> str:
    """Get a single issue with full context."""
    try:
        issue = _client.get_issue(params.owner, params.repo, params.issue_number)
        return json.dumps(issue, indent=2)
    except Exception as e:
        # Raise with a clear message — FastMCP converts this to an MCP error response
        raise ValueError(f"Error fetching issue {params.issue_number}: {e}") from e

@mcp.tool(
    description="List issues with optional state filter. Returns a JSON array of matching issues."
)
def service_list_issues(params: ListIssuesParams) -> str:
    """List issues with filters."""
    try:
        issues = _client.list_issues(params.owner, params.repo, params.state, params.limit)
        return json.dumps(issues, indent=2)
    except Exception as e:
        raise ValueError(f"Error listing issues: {e}") from e

# --- Entry point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## `src/client.py` Template

The shared client class. Adapt to the target service's protocol.

### HTTP Client Pattern

```python
"""Shared HTTP client for {Service Name} API."""

import httpx
from typing import Any

class ServiceClient:
    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Make an authenticated GET request."""
        with httpx.Client() as client:
            response = client.get(
                f"{self._base_url}{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        return self._get(f"/repos/{owner}/{repo}/issues/{number}")

    def list_issues(self, owner: str, repo: str, state: str, limit: int) -> list:
        return self._get(
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": str(limit)},
        )
```

### Subprocess/CLI Client Pattern

```python
"""Shared subprocess client for {Service Name} CLI."""

import subprocess
import json
import os

class CliClient:
    def __init__(self, executable: str, env: dict[str, str] | None = None):
        self._executable = executable
        self._env = {**os.environ, **(env or {})}

    def run(self, args: list[str]) -> str:
        """Run CLI command and return stdout as string."""
        result = subprocess.run(
            [self._executable, *args],
            capture_output=True,
            text=True,
            env=self._env,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed (exit {result.returncode}): {result.stderr}"
            )
        return result.stdout

    def run_json(self, args: list[str]) -> Any:
        """Run CLI command expecting JSON output."""
        output = self.run(args)
        return json.loads(output)
```

### Import Mode Pattern (only with `--import` flag)

When the target is an installable Python package:

```python
"""Direct import client for {service} Python library."""

# Install the target: pip install {service-package}
from {service_package} import SomeClient, Config

class ImportClient:
    def __init__(self, api_key: str):
        self._client = SomeClient(Config(api_key=api_key))

    def get_thing(self, thing_id: str) -> dict:
        result = self._client.things.get(thing_id)
        # Convert SDK objects to plain dicts for JSON serialization
        return result.model_dump() if hasattr(result, "model_dump") else vars(result)
```

---

## Key Differences from TypeScript

| Aspect | TypeScript | Python FastMCP |
|--------|-----------|----------------|
| Tool registration | `server.tool(name, desc, zodSchema, annotations, handler)` | `@mcp.tool(description=...)` decorator on function |
| Parameter validation | Zod schema (compile-time) | Pydantic v2 model (runtime) |
| Error handling | Return `{ content: [...], isError: true }` | `raise ValueError("message")` |
| Startup | `await server.connect(transport)` | `mcp.run(transport="stdio")` |
| Logging | Use `console.error()` (not `console.log()`) | Use `print(..., file=sys.stderr)` |
| Auth check | `if (!API_KEY) throw new Error(...)` | `if not _API_KEY: raise ValueError(...)` |

---

## Error Handling Pattern

In Python FastMCP, raise exceptions with clear messages. FastMCP converts them to MCP error responses automatically.

```python
@mcp.tool(description="...")
def my_tool(params: MyParams) -> str:
    try:
        result = _client.do_something(params.thing_id)
        return json.dumps(result, indent=2)
    except httpx.HTTPStatusError as e:
        raise ValueError(f"API error {e.response.status_code}: {e.response.text}") from e
    except Exception as e:
        raise ValueError(f"Unexpected error: {e}") from e
```

**Preferred behavior**: Raise explicit exceptions instead of catching everything silently or returning empty strings. The model cannot act on silent failures.

---

## Environment Variable Pattern

```python
import os

def _require_env(name: str) -> str:
    """Get a required environment variable or raise at startup."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(
            f"{name} environment variable is required. "
            f"Set it before starting the server: export {name}=your_value"
        )
    return value

# At module level (checked at startup, not at first tool call)
API_KEY = _require_env("SERVICE_API_KEY")
```

---

## `README.md` Template

```markdown
# {Service Name} MCP Server

MCP server for {Service Name}. Provides Claude Code with tools to {one-line purpose}.

## Tools

| Tool | Description |
|------|-------------|
| `service_get_thing` | Get a single thing by ID |
| `service_list_things` | List things with optional filters |

## Setup

### Prerequisites
- Python >= 3.11
- {Service Name} API key

### Install

\`\`\`bash
pip install -e .
\`\`\`

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SERVICE_API_KEY` | Yes | {Service Name} API key from {where to get it} |

### Register with Claude Code

\`\`\`bash
python3 skills/workflow/references/mcp-pipeline-builder/scripts/register_mcp.py \
  --name {service}-mcp-server \
  --command python3 \
  --args $(pwd)/src/main.py \
  --env SERVICE_API_KEY=your_key_here
\`\`\`

Or add manually to `~/.claude.json`:

\`\`\`json
{
  "mcpServers": {
    "{service}-mcp-server": {
      "command": "python3",
      "args": ["/absolute/path/to/src/main.py"],
      "env": {
        "SERVICE_API_KEY": "your_key_here"
      }
    }
  }
}
\`\`\`
```
