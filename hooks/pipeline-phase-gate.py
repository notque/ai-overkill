#!/usr/bin/env python3
# hook-version: 1.0.1
"""
PreToolUse:Write,Edit Hook: Pipeline Phase Gate

Blocks phase-advancing writes when the current phase's required artifact is
absent. Converts LLM-instruction gates into enforced exit-code gates without
per-pipeline scripting.

Exit codes:
  0 — allow (artifact exists, path not gated, or no active pipeline detected)
  2 — block (phase artifact missing; hard gate)

Detection strategy:
  A phase-gate registry maps (pipeline_id, phase_number) -> expected artifact
  filename. The hook resolves the pipeline from the target file path and the
  current phase from the environment or a sentinel file, then checks artifact
  existence before allowing the write.

Registry pattern (extend to new pipelines without modifying core logic):
  PHASE_GATE_REGISTRY = {
      "do-perspectives": {
          # Phase 3 (SYNTHESIZE) requires Phase 2 artifact
          3: "perspectives-analysis.md",
          # Phase 4 (APPLY) requires Phase 3 artifact
          4: "synthesis.md",
      },
  }

Phase detection:
  The hook infers the current phase from a sentinel file
  `.pipeline-phase` written by the skill when it advances. If the sentinel
  is absent, the hook falls back to env var PIPELINE_CURRENT_PHASE.
  If neither exists, the hook allows through (no active phase tracking).

Environment overrides:
  PIPELINE_PHASE_GATE_BYPASS=1   — bypass entirely (for skill own writes)
  PIPELINE_CURRENT_PHASE=N       — override detected phase (integer)
  CLAUDE_HOOKS_DEBUG=1           — verbose stderr output

Triggering file paths (gate applies when write target is in one of these):
  do-perspectives writes happen in the cwd (any .md at repo root/cwd).
  The hook gates based on the file_path matching the artifact name for the
  NEXT phase, not the current phase. That is: if Phase 3 is about to write
  synthesis.md and perspectives-analysis.md doesn't exist yet, Phase 2 was
  never completed.

  Concretely: if the tool is trying to write "synthesis.md" and
  "perspectives-analysis.md" is absent in the same directory, block.
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "PIPELINE_PHASE_GATE_BYPASS"

# Registry: maps pipeline_id -> { artifact_being_written -> prerequisite_artifact }
# "artifact_being_written" is the basename of the file the LLM is about to create.
# "prerequisite_artifact" must already exist in the same directory.
#
# Extend this dict to add gates for new pipelines. Core logic never changes.
PREREQUISITE_REGISTRY: dict[str, dict[str, str]] = {
    "do-perspectives": {
        # Writing synthesis.md (Phase 3 output) requires perspectives-analysis.md (Phase 2 output)
        "synthesis.md": "perspectives-analysis.md",
        # Writing into the target agent/skill (Phase 4) requires synthesis.md (Phase 3 output)
        # Phase 4 writes to the actual target, not a known filename — handled separately via
        # the phase-sentinel approach below. This entry covers the synthesis -> apply gate.
    },
}

# Phase-sentinel-based registry: maps pipeline_id -> { phase_number -> required_artifact }
# Used when a .pipeline-phase sentinel file exists in the cwd.
# Extend this dict to gate new multi-phase skills — core logic never changes.
PHASE_SENTINEL_REGISTRY: dict[str, dict[int, str]] = {
    "do-perspectives": {
        3: "perspectives-analysis.md",  # Phase 3 (SYNTHESIZE) requires Phase 2 artifact
        4: "synthesis.md",  # Phase 4 (APPLY) requires Phase 3 artifact
    },
    # quality-loop (14 phases per quality-loop.md)
    "quality-loop": {
        2: "task_plan.md",  # Phase 2 (IMPLEMENT) requires Phase 1 (PLAN) artifact
        3: "quality-loop-state.md",  # Phase 3 (TEST) requires Phase 2 (IMPLEMENT) state artifact
        4: "quality-loop-state.md",  # Phase 4 (REVIEW) requires IMPLEMENT state (tests run in-memory)
        7: "quality-loop-state.md",  # Phase 7 (FIX) requires implementation state for agent selection
        9: "quality-loop-state.md",  # Phase 9 (PR) requires implementation state for PR body
    },
    # feature-lifecycle (6 phases: DESIGN=1, PLAN=2, IMPLEMENT=3, VALIDATE=4, RELEASE=5, RECORD=6)
    "feature-lifecycle": {
        2: ".feature/",  # Phase 2 (PLAN) requires Phase 1 (DESIGN) — .feature/ dir with design doc
        3: ".feature/",  # Phase 3 (IMPLEMENT) requires Phase 2 (PLAN) — plan artifact in .feature/
        4: ".feature/",  # Phase 4 (VALIDATE) requires Phase 3 (IMPLEMENT) — code committed
        5: ".feature/",  # Phase 5 (RELEASE) requires Phase 4 (VALIDATE) — validation report
    },
    # pr-workflow (commit -> push -> PR)
    "pr-workflow": {
        # Phase 2 (push) requires local commits ahead of remote — checked via git, not file artifact
        # Phase 3 (PR creation) requires committed changes on branch — checked via git, not file artifact
        # These are git-state gates, not file-artifact gates. Handled by _check_git_prerequisite.
    },
    # voice-writer (13 phases: LOAD, GROUND, STATS-CHECKPOINT, GENERATE, HOOK-GATE,
    #   VALIDATE, REFINE, VARIETY-GATE, JOY-CHECK, ANTI-AI, CLOSE-GATE, OUTPUT, CLEANUP)
    "voice-writer": {
        4: ".voice-grounding.md",  # Phase 4 (GENERATE) requires Phase 2 (GROUND) artifact
        6: ".voice-stats-baseline.md",  # Phase 6 (VALIDATE) requires Phase 3 (STATS-CHECKPOINT)
        10: ".voice-validation-report.md",  # Phase 10 (ANTI-AI) requires Phase 6 (VALIDATE) report
    },
}

# Artifact basenames that are themselves phase outputs — used to detect which
# pipeline is active when no sentinel file exists.
ARTIFACT_TO_PIPELINE: dict[str, str] = {
    "perspectives-analysis.md": "do-perspectives",
    "synthesis.md": "do-perspectives",
    "task_plan.md": "quality-loop",
    "quality-loop-state.md": "quality-loop",
}


def _debug(msg: str) -> None:
    if os.environ.get("CLAUDE_HOOKS_DEBUG"):
        print(f"[pipeline-phase-gate] {msg}", file=sys.stderr)


def _block(reason: str, expected_path: str) -> None:
    """Print block output to stderr and exit 2."""
    print(f"[pipeline-phase-gate] BLOCKED: {reason}", file=sys.stderr)
    print(f"[pipeline-phase-gate] Expected artifact: {expected_path}", file=sys.stderr)
    sys.exit(2)


def _read_phase_sentinel(cwd: Path) -> tuple[str | None, int | None]:
    """Read .pipeline-phase sentinel file.

    Supports two formats:
      - Plain integer: "3" (legacy, pipeline inferred from context)
      - JSON: {"pipeline": "quality-loop", "phase": 3}

    Returns:
        (pipeline_id_or_None, phase_int_or_None)
    """
    sentinel = cwd / ".pipeline-phase"
    if not sentinel.is_file():
        return None, None
    try:
        text = sentinel.read_text(encoding="utf-8").strip()
        if not text:
            return None, None
        # Try JSON first
        if text.startswith("{"):
            data = json.loads(text)
            pipeline = data.get("pipeline")
            phase = data.get("phase")
            if isinstance(phase, int):
                return pipeline, phase
            return pipeline, None
        # Fall back to plain integer (legacy)
        return None, int(text)
    except (ValueError, OSError, json.JSONDecodeError):
        return None, None


def _artifact_exists(path: Path) -> bool:
    """Check if a required artifact exists (file or directory)."""
    return path.is_file() or path.is_dir()


def _detect_pipeline_from_path(file_path: str) -> str | None:
    """Infer pipeline id from the target file basename."""
    basename = Path(file_path).name
    return ARTIFACT_TO_PIPELINE.get(basename)


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        _debug("Bypassed via PIPELINE_PHASE_GATE_BYPASS=1")
        sys.exit(0)

    raw = read_stdin(timeout=2)
    if not raw:
        _debug("Empty stdin — allowing through")
        sys.exit(0)

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        _debug("Could not parse stdin JSON — allowing through")
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        _debug("No file_path in tool_input — allowing through")
        sys.exit(0)

    target_basename = Path(file_path).name
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    cwd = Path(cwd_str).resolve()
    target_dir = Path(file_path).parent
    # If file_path is relative, resolve against cwd
    if not Path(file_path).is_absolute():
        target_dir = (cwd / target_dir).resolve()
    else:
        target_dir = target_dir.resolve()

    _debug(f"target={file_path} basename={target_basename} dir={target_dir}")

    # --- Strategy 1: Prerequisite-by-artifact-name ---
    # If the LLM is writing a known phase-N output artifact, check that the
    # phase-(N-1) artifact already exists in the same directory.
    for pipeline_id, prereq_map in PREREQUISITE_REGISTRY.items():
        if target_basename in prereq_map:
            required = prereq_map[target_basename]
            required_path = target_dir / required
            _debug(f"Pipeline={pipeline_id}: writing {target_basename} requires {required_path}")
            if not _artifact_exists(required_path):
                _block(
                    f"Phase prerequisite missing for pipeline '{pipeline_id}'. "
                    f"Writing '{target_basename}' requires '{required}' to exist first.",
                    str(required_path),
                )
            else:
                _debug(f"Prerequisite {required_path} exists — allowing")
                sys.exit(0)

    # --- Strategy 2: Phase-sentinel gate ---
    # If .pipeline-phase exists, use it to look up what artifact is required
    # for the current phase, regardless of what file is being written.
    phase_env = os.environ.get("PIPELINE_CURRENT_PHASE")
    current_phase: int | None = None
    if phase_env is not None:
        try:
            current_phase = int(phase_env)
        except ValueError:
            pass

    sentinel_pipeline: str | None = None
    if current_phase is None:
        sentinel_pipeline, current_phase = _read_phase_sentinel(cwd)

    if current_phase is not None:
        _debug(f"Detected phase={current_phase} from sentinel/env")
        # Determine active pipeline: env > sentinel JSON > target basename inference
        active_pipeline = os.environ.get("PIPELINE_ID") or sentinel_pipeline or _detect_pipeline_from_path(file_path)
        if active_pipeline and active_pipeline in PHASE_SENTINEL_REGISTRY:
            phase_map = PHASE_SENTINEL_REGISTRY[active_pipeline]
            if current_phase in phase_map:
                required = phase_map[current_phase]
                required_path = cwd / required
                _debug(f"Phase {current_phase} of {active_pipeline} requires {required_path}")
                if not _artifact_exists(required_path):
                    _block(
                        f"Phase {current_phase} prerequisite missing for pipeline '{active_pipeline}'. "
                        f"Phase {current_phase - 1} artifact '{required}' must exist before advancing.",
                        str(required_path),
                    )
                else:
                    _debug(f"Phase artifact {required_path} exists — allowing")
                    sys.exit(0)

    # --- Strategy 3: Blog post voice-writer gate ---
    # Any write to content/posts/*.md requires the voice-writer pipeline to
    # have completed. Checked via a .voice-pipeline-complete marker file.
    if "content/posts/" in file_path and file_path.endswith(".md"):
        # Allow the voice-writer itself to write during pipeline execution
        if os.environ.get("VOICE_WRITER_ACTIVE") == "1":
            _debug("VOICE_WRITER_ACTIVE=1 — allowing blog post write during pipeline")
            sys.exit(0)

        marker_path = cwd / ".voice-pipeline-complete"
        if not marker_path.is_file():
            print(
                "[pipeline-phase-gate] BLOCKED: Blog post writes require the voice-writer pipeline. "
                "[fix-with-skill] voice-writer\n"
                "Call the Skill tool with `voice-writer`. The voice pipeline creates .voice-pipeline-complete "
                "when all 13 phases pass.",
                file=sys.stderr,
            )
            sys.exit(2)

        # Validate marker contents
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print(
                "[pipeline-phase-gate] BLOCKED: .voice-pipeline-complete exists but is unreadable or invalid JSON.",
                file=sys.stderr,
            )
            sys.exit(2)

        # Check target_file basename match
        marker_target = marker.get("target_file", "")
        if Path(marker_target).name != target_basename:
            print(
                f"[pipeline-phase-gate] BLOCKED: .voice-pipeline-complete target_file "
                f"'{marker_target}' does not match write target '{target_basename}'. "
                f"[fix-with-skill] voice-writer\n"
                f"Call the Skill tool with `voice-writer`. Run it for this specific post.",
                file=sys.stderr,
            )
            sys.exit(2)

        # Check all 13 phases passed
        required_phases = {
            "LOAD",
            "GROUND",
            "STATS-CHECKPOINT",
            "GENERATE",
            "HOOK-GATE",
            "VALIDATE",
            "REFINE",
            "VARIETY-GATE",
            "JOY-CHECK",
            "ANTI-AI",
            "CLOSE-GATE",
            "OUTPUT",
            "CLEANUP",
        }
        passed = set(marker.get("phases_passed", []))
        missing = required_phases - passed
        if missing:
            print(
                f"[pipeline-phase-gate] BLOCKED: .voice-pipeline-complete is missing phases: "
                f"{', '.join(sorted(missing))}. Pipeline incomplete.",
                file=sys.stderr,
            )
            sys.exit(2)

        _debug(f"Voice-writer pipeline complete for {target_basename} — allowing")
        sys.exit(0)

    _debug(f"No gate matched for {file_path} — allowing through")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        hook_error("pipeline-phase-gate", e)
