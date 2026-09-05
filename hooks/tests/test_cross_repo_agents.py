#!/usr/bin/env python3
"""Tests for cross-repo-agents.py hook."""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from hyphenated filename
import importlib.util

spec = importlib.util.spec_from_file_location(
    "cross_repo_agents", Path(__file__).parent.parent / "cross-repo-agents.py"
)
cross_repo_agents = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cross_repo_agents)

discover_local_agents = cross_repo_agents.discover_local_agents
extract_agent_info = cross_repo_agents.extract_agent_info


class TestExtractAgentInfo:
    """Tests for extract_agent_info function."""

    def test_valid_yaml_frontmatter(self, tmp_path):
        """Test extraction from valid YAML frontmatter."""
        agent_file = tmp_path / "test-agent.md"
        agent_file.write_text("""---
name: test-agent
description: Use this agent when you need help with testing.
---

# Test Agent

This is a test agent.
""")
        info = extract_agent_info(agent_file)

        assert info is not None
        assert info["name"] == "test-agent"
        assert "Use when" in info["description"]
        assert str(agent_file) in info["file"]

    def test_yaml_with_routing_triggers(self, tmp_path):
        """Test extraction of routing triggers."""
        agent_file = tmp_path / "routing-agent.md"
        agent_file.write_text("""---
name: routing-agent
description: Test agent with triggers
routing:
  triggers:
    - "test"
    - "testing"
---

# Routing Agent
""")
        info = extract_agent_info(agent_file)

        assert info is not None
        assert "test" in info["triggers"] or "routing agent" in info["triggers"]

    def test_no_yaml_frontmatter(self, tmp_path):
        """Test agent without YAML frontmatter uses fallbacks."""
        agent_file = tmp_path / "simple-agent.md"
        agent_file.write_text("""# Simple Agent

This agent has no frontmatter.
""")
        info = extract_agent_info(agent_file)

        assert info is not None
        assert info["name"] == "simple-agent"
        assert info["description"] == "Simple Agent"

    def test_malformed_file_returns_none_silently(self, tmp_path):
        """Test that malformed files return None without crashing."""
        agent_file = tmp_path / "bad-agent.md"
        # Create file that will fail to parse but not crash
        agent_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8

        # Should return None, not raise
        info = extract_agent_info(agent_file)
        assert info is None

    def test_missing_file_returns_none(self, tmp_path):
        """Test that missing files return None."""
        agent_file = tmp_path / "nonexistent.md"

        info = extract_agent_info(agent_file)
        assert info is None


class TestDiscoverLocalAgents:
    """Tests for discover_local_agents function."""

    def test_discovers_agents_in_claude_agents_dir(self, tmp_path):
        """Test discovery of agents in .claude/agents/ directory."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        # Create test agent
        agent_file = agents_dir / "local-agent.md"
        agent_file.write_text("""---
name: local-agent
description: A local test agent
---

# Local Agent
""")

        agents = discover_local_agents(str(tmp_path))

        assert len(agents) == 1
        assert agents[0]["name"] == "local-agent"

    def test_returns_empty_when_no_agents_dir(self, tmp_path):
        """Test empty list when .claude/agents/ doesn't exist."""
        agents = discover_local_agents(str(tmp_path))
        assert agents == []

    def test_returns_empty_when_agents_dir_empty(self, tmp_path):
        """Test empty list when agents directory is empty."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        agents = discover_local_agents(str(tmp_path))
        assert agents == []

    def test_ignores_non_markdown_files(self, tmp_path):
        """Test that non-.md files are ignored."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        # Create non-markdown file
        (agents_dir / "readme.txt").write_text("Not an agent")
        (agents_dir / "config.json").write_text("{}")

        agents = discover_local_agents(str(tmp_path))
        assert agents == []

    def test_multiple_agents_sorted_by_name(self, tmp_path):
        """Test multiple agents are returned sorted by name."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        # Create agents in reverse alphabetical order
        for name in ["zebra-agent", "alpha-agent", "beta-agent"]:
            agent_file = agents_dir / f"{name}.md"
            agent_file.write_text(f"""---
name: {name}
description: Test agent {name}
---
""")

        agents = discover_local_agents(str(tmp_path))

        assert len(agents) == 3
        assert agents[0]["name"] == "alpha-agent"
        assert agents[1]["name"] == "beta-agent"
        assert agents[2]["name"] == "zebra-agent"


class TestDebugLogging:
    """Tests for debug logging behavior."""

    def test_debug_logging_when_env_set(self, tmp_path, capsys):
        """Test that debug logging works when CLAUDE_HOOKS_DEBUG is set."""
        agent_file = tmp_path / "bad-agent.md"
        agent_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8

        with mock.patch.dict(os.environ, {"CLAUDE_HOOKS_DEBUG": "1"}):
            info = extract_agent_info(agent_file)

        assert info is None
        captured = capsys.readouterr()
        assert "[cross-repo-agents] HOOK-ERROR:" in captured.err

    def test_loud_error_when_debug_not_set(self, tmp_path, capsys):
        """Errors are always visible (unconditional one-liner via hook_error)."""
        agent_file = tmp_path / "bad-agent.md"
        agent_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLAUDE_HOOKS_DEBUG", None)
            info = extract_agent_info(agent_file)

        assert info is None
        captured = capsys.readouterr()
        assert "[cross-repo-agents] HOOK-ERROR:" in captured.err


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_catalog_preserves_local_paths_and_duplicate_names(tmp_path, capsys, monkeypatch):
    """A shared directory must still identify differently named override files."""
    import json

    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    for filename in ("custom.md", "override.md"):
        (agents_dir / filename).write_text(
            "---\nname: same-name\ndescription: Local domain knowledge\nrouting:\n  triggers:\n    - local task\n---\n"
        )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as result:
        cross_repo_agents.main()
    assert result.value.code == 0
    payload = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert payload.count(str(agents_dir)) == 1
    for filename in ("custom.md", "override.md"):
        assert f"same-name [{filename}] | Local domain knowledge | local task" in payload
    assert "read the selected file" in payload
