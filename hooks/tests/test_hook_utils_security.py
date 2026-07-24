#!/usr/bin/env python3
"""Tests for the security/diff helpers lifted into hook_utils.

Run with: python3 -m pytest hooks/tests/test_hook_utils_security.py -v

Covers the helpers promoted out of hooks/security-review-hook.py so multiple
hooks can share one implementation:
- working_tree_diff(cwd)        — git working-tree diff (subprocess wrapper)
- diff_post_image_ext(line)     — extract a +++ header's post-image extension
- has_reviewable_content(diff, scannable_exts) — added-source-line gate
- DiffDedup                     — sha256(cwd,diff) signature + atomic state +
                                  opt-in TTL state machine
- async_rewake(message, summary) — stdout rewakeSummary + stderr context + exit 2
"""

import io
import json
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from hook_utils import (
    DiffDedup,
    async_rewake,
    diff_post_image_ext,
    has_reviewable_content,
    normalize_diff_for_fingerprint,
    working_tree_diff,
)

_SRC_EXTS = frozenset({".py", ".go", ".js", ".ts", ".rb", ".java", ".php", ".kt", ".swift"})


def _src_diff(added: str, path: str = "app.py") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1,1 +1,2 @@\n"
        f" existing\n"
        f"+{added}\n"
    )


# ---------------------------------------------------------------------------
# diff_post_image_ext
# ---------------------------------------------------------------------------


class TestDiffPostImageExt:
    def test_basic_b_prefix(self):
        assert diff_post_image_ext("+++ b/src/app.py") == ".py"

    def test_dev_null_returns_none(self):
        assert diff_post_image_ext("+++ /dev/null") is None

    def test_no_extension_returns_none(self):
        assert diff_post_image_ext("+++ b/Makefile") is None

    def test_lowercased(self):
        assert diff_post_image_ext("+++ b/A.PY") == ".py"

    def test_dotfile_treated_as_extension(self):
        # Behavior preserved byte-identically from security-review-hook.py: a
        # leading-dot dotfile like `.gitignore` is reported as ext ".gitignore".
        # Harmless — such extensions are never in any scannable set, so the
        # has_reviewable_content gate ignores them anyway.
        assert diff_post_image_ext("+++ b/.gitignore") == ".gitignore"


# ---------------------------------------------------------------------------
# has_reviewable_content
# ---------------------------------------------------------------------------


class TestHasReviewableContent:
    def test_added_source_line_is_reviewable(self):
        assert has_reviewable_content(_src_diff("os.system(x)"), _SRC_EXTS) is True

    def test_pure_deletion_not_reviewable(self):
        diff = (
            "diff --git a/app.py b/app.py\n"
            "index 83db48f..8129d30 100644\n--- a/app.py\n+++ b/app.py\n"
            "@@ -1,2 +1,1 @@\n keep\n-os.system(removed)\n"
        )
        assert has_reviewable_content(diff, _SRC_EXTS) is False

    def test_doc_only_added_line_not_reviewable(self):
        diff = (
            "diff --git a/README.md b/README.md\n"
            "index 1..2 100644\n--- a/README.md\n+++ b/README.md\n"
            "@@ -1 +1,2 @@\n intro\n+Call eval(x).\n"
        )
        assert has_reviewable_content(diff, _SRC_EXTS) is False

    def test_mixed_doc_and_source_add_is_reviewable(self):
        diff = (
            "diff --git a/README.md b/README.md\n"
            "index 1..2 100644\n--- a/README.md\n+++ b/README.md\n@@ -1 +1,2 @@\n x\n+docs\n"
            "diff --git a/app.py b/app.py\n"
            "index 3..4 100644\n--- a/app.py\n+++ b/app.py\n@@ -1 +1,2 @@\n y\n+yaml.load(d)\n"
        )
        assert has_reviewable_content(diff, _SRC_EXTS) is True

    def test_pure_rename_not_reviewable(self):
        diff = "diff --git a/old.py b/new.py\nsimilarity index 100%\nrename from old.py\nrename to new.py\n"
        assert has_reviewable_content(diff, _SRC_EXTS) is False

    def test_empty_diff_not_reviewable(self):
        assert has_reviewable_content("", _SRC_EXTS) is False


# ---------------------------------------------------------------------------
# working_tree_diff
# ---------------------------------------------------------------------------


class TestWorkingTreeDiff:
    def test_returns_stdout_on_success(self):
        class _R:
            returncode = 0
            stdout = "diff --git a/x b/x\n"

        with patch("hook_utils.subprocess.run", return_value=_R()):
            assert working_tree_diff("/repo") == "diff --git a/x b/x\n"

    def test_nonzero_returncode_yields_empty(self):
        class _R:
            returncode = 128
            stdout = "fatal: not a repo\n"

        with patch("hook_utils.subprocess.run", return_value=_R()):
            assert working_tree_diff("/repo") == ""

    def test_subprocess_error_yields_empty(self):
        with patch("hook_utils.subprocess.run", side_effect=OSError("boom")):
            assert working_tree_diff("/repo") == ""


# ---------------------------------------------------------------------------
# DiffDedup
# ---------------------------------------------------------------------------


class TestDiffDedup:
    def test_signature_distinguishes_cwd(self):
        d = DiffDedup(Path("/tmp/x"), Path("/tmp/x/s.json"))
        assert d.signature("/a", "diff") != d.signature("/b", "diff")

    def test_signature_distinguishes_diff(self):
        d = DiffDedup(Path("/tmp/x"), Path("/tmp/x/s.json"))
        assert d.signature("/a", "diff1") != d.signature("/a", "diff2")

    def test_first_seen_is_not_duplicate(self, tmp_path):
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        is_dup, _ = d.is_duplicate("/repo", "diffA")
        assert is_dup is False

    def test_record_then_identical_is_duplicate(self, tmp_path):
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        d.record("/repo", "diffA")
        is_dup, _ = d.is_duplicate("/repo", "diffA")
        assert is_dup is True

    def test_record_writes_atomically(self, tmp_path):
        state = tmp_path / "s.json"
        d = DiffDedup(tmp_path, state)
        d.record("/repo", "diffA")
        assert state.exists()
        data = json.loads(state.read_text())
        assert "hash" in data and "ts" in data

    def test_changed_diff_is_not_duplicate(self, tmp_path):
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        d.record("/repo", "diffA")
        is_dup, _ = d.is_duplicate("/repo", "diffB")
        assert is_dup is False

    def test_different_cwd_not_duplicate(self, tmp_path):
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        d.record("/repo-a", "diffA")
        is_dup, _ = d.is_duplicate("/repo-b", "diffA")
        assert is_dup is False

    def test_no_ttl_is_permanent(self, tmp_path):
        """Default TTL=0 → an ancient ts still dedups when the hash matches."""
        state = tmp_path / "s.json"
        d = DiffDedup(tmp_path, state, ttl_seconds=0)
        state.write_text(json.dumps({"hash": d.signature("/repo", "diffA"), "ts": 0, "ts_iso": "x", "cwd": "/repo"}))
        is_dup, _ = d.is_duplicate("/repo", "diffA")
        assert is_dup is True

    def test_positive_ttl_expires_old_record(self, tmp_path):
        state = tmp_path / "s.json"
        d = DiffDedup(tmp_path, state, ttl_seconds=300)
        old_ts = time.time() - 10_000
        state.write_text(
            json.dumps({"hash": d.signature("/repo", "diffA"), "ts": old_ts, "ts_iso": "x", "cwd": "/repo"})
        )
        is_dup, _ = d.is_duplicate("/repo", "diffA")
        assert is_dup is False

    def test_corrupt_state_is_not_duplicate(self, tmp_path):
        state = tmp_path / "s.json"
        state.write_text("not json {{{")
        d = DiffDedup(tmp_path, state)
        is_dup, _ = d.is_duplicate("/repo", "diffA")
        assert is_dup is False

    def test_record_failure_is_silent(self, tmp_path):
        # An unwritable state dir must not raise — dedup persistence is best-effort.
        d = DiffDedup(tmp_path / "nope", tmp_path / "nope" / "deep" / "s.json")
        with patch("hook_utils.os.replace", side_effect=OSError("ro")):
            d.record("/repo", "diffA")  # must not raise

    # --- fingerprint normalization: blob-SHA / mode churn must NOT re-trigger ---

    def test_signature_ignores_index_blob_sha_churn(self, tmp_path):
        """Same paths + same hunks but fresh ``index`` blob SHAs → same signature."""
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        before = (
            "diff --git a/static/game/index.html b/static/game/index.html\n"
            "index 71aae3b..739f207 100644\n"
            "--- a/static/game/index.html\n"
            "+++ b/static/game/index.html\n"
            "@@ -1 +1,2 @@\n x\n+rebuilt\n"
        )
        after = before.replace("index 71aae3b..739f207", "index aaaaaaa..bbbbbbb")
        assert d.signature("/repo", before) == d.signature("/repo", after)

    def test_index_churn_dedups_end_to_end(self, tmp_path):
        """Record a diff, then re-fire with only blob-SHA churn → duplicate."""
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        first = (
            "diff --git a/app.js b/app.js\nindex 1111111..2222222 100644\n"
            "--- a/app.js\n+++ b/app.js\n@@ -1 +1,2 @@\n y\n+z\n"
        )
        d.record("/repo", first)
        rebuilt = first.replace("index 1111111..2222222", "index 9999999..8888888")
        is_dup, _ = d.is_duplicate("/repo", rebuilt)
        assert is_dup is True

    def test_real_content_change_is_not_duplicate(self, tmp_path):
        """A changed hunk (one new added line) still produces a fresh review."""
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        first = (
            "diff --git a/app.js b/app.js\nindex 1111111..2222222 100644\n"
            "--- a/app.js\n+++ b/app.js\n@@ -1 +1,2 @@\n y\n+z\n"
        )
        d.record("/repo", first)
        changed = first.replace("+z\n", "+z\n+brand_new_line\n")
        is_dup, _ = d.is_duplicate("/repo", changed)
        assert is_dup is False

    def test_new_file_path_is_not_duplicate(self, tmp_path):
        """A new file path differs from the recorded diff → fresh review."""
        d = DiffDedup(tmp_path, tmp_path / "s.json")
        first = (
            "diff --git a/app.js b/app.js\nindex 1111111..2222222 100644\n"
            "--- a/app.js\n+++ b/app.js\n@@ -1 +1,2 @@\n y\n+z\n"
        )
        d.record("/repo", first)
        with_new = first + (
            "diff --git a/extra.js b/extra.js\nindex 0000000..3333333 100644\n"
            "--- a/extra.js\n+++ b/extra.js\n@@ -0,0 +1 @@\n+added\n"
        )
        is_dup, _ = d.is_duplicate("/repo", with_new)
        assert is_dup is False


class TestNormalizeDiffForFingerprint:
    def test_drops_index_line(self):
        norm = normalize_diff_for_fingerprint("index 71aae3b..739f207 100644\n")
        assert "index " not in norm

    def test_drops_mode_lines(self):
        diff = "old mode 100644\nnew mode 100755\n"
        assert normalize_diff_for_fingerprint(diff).strip() == ""

    def test_drops_similarity_index(self):
        diff = "similarity index 95%\ndissimilarity index 5%\n"
        assert normalize_diff_for_fingerprint(diff).strip() == ""

    def test_keeps_file_paths_and_hunks(self):
        diff = (
            "diff --git a/app.py b/app.py\nindex abc..def 100644\n--- a/app.py\n+++ b/app.py\n@@ -1 +1,2 @@\n x\n+y\n"
        )
        norm = normalize_diff_for_fingerprint(diff)
        for keep in ("diff --git a/app.py b/app.py", "--- a/app.py", "+++ b/app.py", "@@ -1 +1,2 @@", "+y"):
            assert keep in norm

    def test_keeps_rename_path_lines(self):
        diff = "rename from old.py\nrename to new.py\n"
        norm = normalize_diff_for_fingerprint(diff)
        assert "rename from old.py" in norm and "rename to new.py" in norm

    def test_empty_diff_is_empty(self):
        assert normalize_diff_for_fingerprint("") == ""


# ---------------------------------------------------------------------------
# async_rewake
# ---------------------------------------------------------------------------


class TestAsyncRewake:
    def test_exits_2_with_summary_and_context(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                async_rewake("CONTEXT-BODY", "ONE-LINE-SUMMARY")
            except SystemExit as e:
                code = int(e.code) if e.code is not None else 0
        assert code == 2
        data = json.loads(out.getvalue().strip().splitlines()[0])
        assert data["rewakeSummary"] == "ONE-LINE-SUMMARY"
        assert "CONTEXT-BODY" in err.getvalue()


# ---------------------------------------------------------------------------
# is_sensitive_path
# ---------------------------------------------------------------------------


class TestIsSensitivePath:
    """Credential-shaped paths are flagged; ordinary source paths are not."""

    def test_credential_directories_flagged(self):
        from hook_utils import is_sensitive_path

        for p in (
            "/home/u/.ssh/deploy_ed25519.pub",
            "/home/u/.ssh/id_rsa",
            "/home/u/.gnupg/pubring.kbx",
            "/home/u/.aws/config",
            "relative/.kube/config",
        ):
            assert is_sensitive_path(p), p

    def test_credential_basenames_flagged(self):
        from hook_utils import is_sensitive_path

        for p in (
            "/app/.env",
            "/app/.env.production",
            "/certs/server.pem",
            "/certs/tls.key",
            "/home/u/id_ed25519.pub",
            "/srv/service-account-credentials.json",
            "/srv/client_secret.json",
            "/home/u/token.json",
            "/home/u/.netrc",
        ):
            assert is_sensitive_path(p), p

    def test_ordinary_paths_not_flagged(self):
        from hook_utils import is_sensitive_path

        for p in (
            "/app/main.py",
            "/repo/hooks/adr-enforcement.py",
            "/docs/environment.md",  # 'env' substring must not match
            "/src/assh/parser.go",  # '.ssh' must match whole segments only
            "/lib/monkey.rb",  # '.key' suffix check is on basename pattern, not substring
            "README.md",
            "",
        ):
            assert not is_sensitive_path(p), p
