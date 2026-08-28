"""Repository-wide pytest fixtures.

Keeps every test off the production learning database at
`~/.claude/learning/learning.db`. Redirection is belt-and-braces because one
lever is not enough:

- `CLAUDE_LEARNING_DIR` covers the modules that read it (`learning_db_v2`,
  `usage_db`, `route_events`) and every child process a test spawns.
- Patching `learning_db_v2._DEFAULT_DB_DIR` covers the fallback a test reaches
  when it deliberately unsets that env var, as
  `scripts/tests/test_install_doctor.py` does.

The fixture then asserts the resolved path sits outside the real `~/.claude`,
on setup and again on teardown, so a leak fails the test that caused it instead
of silently corrupting production data.
"""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent
_LIB_DIR = _REPO_ROOT / "hooks" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import learning_db_v2

# Resolved at import time, before any test can monkeypatch HOME.
_PRODUCTION_CLAUDE_DIR = Path.home() / ".claude"


def _assert_db_is_isolated(phase: str) -> None:
    """Fail if the learning DB resolves inside the real ~/.claude tree."""
    resolved = learning_db_v2.get_db_path().resolve()
    assert not resolved.is_relative_to(_PRODUCTION_CLAUDE_DIR), (
        f"learning DB resolved to {resolved} at {phase}: tests must never read "
        f"or write anything under {_PRODUCTION_CLAUDE_DIR}"
    )


@pytest.fixture(autouse=True)
def isolate_learning_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the learning database at a throwaway directory for one test."""
    # Not tmp_path/"learning": several tests create that exact directory
    # themselves with a bare mkdir() and would collide with this fixture.
    db_dir = tmp_path / "isolated-learning-db"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    monkeypatch.setattr(learning_db_v2, "_DEFAULT_DB_DIR", db_dir)
    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    _assert_db_is_isolated("setup")
    yield db_dir
    _assert_db_is_isolated("teardown")
