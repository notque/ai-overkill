#!/usr/bin/env python3
"""
run_eval.py — Execute a skill against a test prompt via claude -p subprocess.

Produces in --output-dir:
  outputs/         All files written during the run
  transcript.md    Full execution log
  timing.json      Token count and wall-clock duration
  metrics.json     Tool usage counts
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Execute a skill against a test prompt via claude -p",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--skill-path", required=True, help="Path to the skill directory (contains SKILL.md)")
    p.add_argument("--prompt", required=True, help="Test prompt text to run")
    p.add_argument("--output-dir", required=True, help="Directory to write outputs, transcript, timing, metrics")
    p.add_argument("--model", default=None, help="Claude model for claude -p (default: your configured model)")
    p.add_argument("--no-skill", action="store_true", help="Run without loading the skill (baseline run)")
    p.add_argument("--timeout", type=int, default=300, help="Max seconds to wait for claude -p (default: 300)")
    return p


def check_claude_available() -> None:
    """Verify claude CLI is in PATH. Exit 1 with actionable message if not."""
    if shutil.which("claude") is None:
        print(
            "ERROR: 'claude' CLI not found in PATH.\n"
            "Install with: npm install -g @anthropic-ai/claude-code\n"
            "Verify with: which claude && claude --version",
            file=sys.stderr,
        )
        sys.exit(1)


def prepare_output_dir(output_dir: Path) -> Path:
    """Create output directory structure. Returns outputs/ subdirectory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = output_dir / "outputs"
    outputs.mkdir(exist_ok=True)
    return outputs


def build_claude_command(
    skill_path: Path,
    prompt: str,
    outputs_dir: Path,
    model: str | None,
    no_skill: bool,
) -> list[str]:
    """Construct the claude -p command with appropriate flags."""
    cmd = [
        "claude",
        "-p",
        prompt,
        *(["--model", model] if model else []),
        "--output-format",
        "json",
    ]

    if not no_skill:
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            print(f"ERROR: SKILL.md not found at {skill_md}", file=sys.stderr)
            sys.exit(1)
        cmd.extend(["--system-prompt-file", str(skill_md)])

    # Ask claude to write outputs to the outputs directory
    cmd.extend(
        [
            "--working-dir",
            str(outputs_dir),
        ]
    )

    return cmd


def count_tools(transcript_text: str) -> dict:
    """Count tool invocations by type from transcript text."""
    import re

    tool_pattern = re.compile(r'"tool":\s*"([^"]+)"')
    counts: dict[str, int] = {}
    for match in tool_pattern.finditer(transcript_text):
        tool = match.group(1)
        counts[tool] = counts.get(tool, 0) + 1
    return counts


def run_eval(args: argparse.Namespace) -> int:
    check_claude_available()

    skill_path = Path(args.skill_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    outputs_dir = prepare_output_dir(output_dir)

    cmd = build_claude_command(
        skill_path=skill_path,
        prompt=args.prompt,
        outputs_dir=outputs_dir,
        model=args.model,
        no_skill=args.no_skill,
    )

    print(f"Running: {' '.join(cmd[:4])} ...", file=sys.stderr)
    start_time = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            cwd=str(outputs_dir),
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR: claude -p timed out after {args.timeout}s", file=sys.stderr)
        (output_dir / "transcript.md").write_text(
            f"# Execution Timeout\n\nRun timed out after {args.timeout} seconds.\n"
        )
        _write_timing(output_dir, duration=float(args.timeout), tokens=0, timed_out=True)
        _write_metrics(output_dir, tool_counts={})
        return 1

    duration = time.monotonic() - start_time

    # Write transcript
    transcript_lines = [
        "# Execution Transcript\n",
        f"**Model**: {args.model or 'configured default'}\n",
        f"**Skill loaded**: {not args.no_skill}\n",
        f"**Duration**: {duration:.2f}s\n",
        f"**Exit code**: {result.returncode}\n\n",
        "## stdout\n\n```\n",
        result.stdout or "(empty)",
        "\n```\n\n## stderr\n\n```\n",
        result.stderr or "(empty)",
        "\n```\n",
    ]
    transcript_text = "".join(transcript_lines)
    (output_dir / "transcript.md").write_text(transcript_text)

    # Parse token counts from JSON output if available
    tokens = 0
    try:
        response = json.loads(result.stdout)
        usage = response.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    except (json.JSONDecodeError, AttributeError):
        pass

    _write_timing(output_dir, duration=duration, tokens=tokens, timed_out=False)
    _write_metrics(output_dir, tool_counts=count_tools(result.stdout + result.stderr))

    if result.returncode != 0:
        print(
            f"WARNING: claude -p exited with code {result.returncode}. Check transcript.md for details.",
            file=sys.stderr,
        )
        return result.returncode

    print(f"Eval complete. Outputs: {output_dir}", file=sys.stderr)
    return 0


def _write_timing(output_dir: Path, duration: float, tokens: int, timed_out: bool) -> None:
    timing = {
        "duration_seconds": round(duration, 3),
        "tokens_total": tokens,
        "timed_out": timed_out,
    }
    (output_dir / "timing.json").write_text(json.dumps(timing, indent=2))


def _write_metrics(output_dir: Path, tool_counts: dict) -> None:
    metrics = {
        "tool_usage": tool_counts,
        "total_tool_calls": sum(tool_counts.values()),
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_eval(args)


if __name__ == "__main__":
    sys.exit(main())
