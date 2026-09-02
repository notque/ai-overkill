#!/usr/bin/env python3
"""Generate an optimized variant of an agent/skill file using Claude Code.

Supports two optimization scopes:
- description-only: mutate frontmatter description only
- body-only: mutate the markdown body only

Pattern: uses `claude -p` so generation runs through Claude Code directly.

Usage:
    python3 skills/meta/agent-comparison/scripts/generate_variant.py \
        --target agents/golang-general-engineer.md \
        --goal "improve error handling instructions" \
        --current-content "..." \
        --failures '[...]' \
        --model claude-opus-5

Output (JSON to stdout):
    {
        "variant": "full file content with updated description...",
        "summary": "Added concrete trigger phrases to the description",
        "deletion_justification": "",
        "reasoning": "Extended thinking content...",
        "tokens_used": 12345
    }

See ADR-131 for safety rules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Protected section handling
# ---------------------------------------------------------------------------

_PROTECTED_RE = re.compile(
    r"(<!--\s*DO NOT OPTIMIZE\s*-->.*?<!--\s*END DO NOT OPTIMIZE\s*-->)",
    re.DOTALL,
)


def extract_protected(content: str) -> list[str]:
    """Extract all protected sections from content."""
    return _PROTECTED_RE.findall(content)


def restore_protected(original: str, variant: str) -> str:
    """Restore protected sections from original into variant."""
    orig_sections = extract_protected(original)
    var_sections = extract_protected(variant)

    if len(orig_sections) != len(var_sections):
        print(
            f"Warning: Protected section count mismatch (original={len(orig_sections)}, variant={len(var_sections)}).",
            file=sys.stderr,
        )
        return variant

    result = variant
    for orig_sec, var_sec in zip(orig_sections, var_sections):
        result = result.replace(var_sec, orig_sec, 1)

    return result


# ---------------------------------------------------------------------------
# Deletion detection
# ---------------------------------------------------------------------------


def detect_deletions(original: str, variant: str) -> list[str]:
    """Find sections that exist in original but are missing from variant.

    Returns list of deleted section headings. Only checks ## headings.
    """
    orig_headings = set(re.findall(r"^##\s+(.+)$", original, re.MULTILINE))
    var_headings = set(re.findall(r"^##\s+(.+)$", variant, re.MULTILINE))
    return sorted(orig_headings - var_headings)


# ---------------------------------------------------------------------------
# Description-only optimization helpers
# ---------------------------------------------------------------------------


def extract_description(content: str) -> str:
    """Extract frontmatter description text from a markdown file."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("Content missing frontmatter opening delimiter")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("Content missing frontmatter closing delimiter")

    fm_lines = lines[1:end_idx]
    idx = 0
    while idx < len(fm_lines):
        line = fm_lines[idx]
        if line.startswith("description:"):
            value = line[len("description:") :].strip()
            if value in (">", "|", ">-", "|-"):
                parts: list[str] = []
                idx += 1
                while idx < len(fm_lines) and (fm_lines[idx].startswith("  ") or fm_lines[idx].startswith("\t")):
                    parts.append(fm_lines[idx].strip())
                    idx += 1
                return "\n".join(parts).strip()
            return value.strip('"').strip("'").strip()
        idx += 1

    raise ValueError("Content missing frontmatter description")


def replace_description(content: str, new_description: str) -> str:
    """Replace the frontmatter description while preserving all other content verbatim."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("Content missing frontmatter opening delimiter")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("Content missing frontmatter closing delimiter")

    fm_lines = lines[1:end_idx]
    start_idx = None
    stop_idx = None
    idx = 0
    while idx < len(fm_lines):
        line = fm_lines[idx]
        if line.startswith("description:"):
            start_idx = idx
            value = line[len("description:") :].strip()
            stop_idx = idx + 1
            if value in (">", "|", ">-", "|-"):
                stop_idx = idx + 1
                while stop_idx < len(fm_lines) and (
                    fm_lines[stop_idx].startswith("  ") or fm_lines[stop_idx].startswith("\t")
                ):
                    stop_idx += 1
            break
        idx += 1

    if start_idx is None or stop_idx is None:
        raise ValueError("Content missing frontmatter description")

    normalized = new_description.strip()
    replacement = ["description: |"]
    if normalized:
        replacement.extend(f"  {line}" if line else "  " for line in normalized.splitlines())
    else:
        replacement.append("  ")

    new_fm_lines = fm_lines[:start_idx] + replacement + fm_lines[stop_idx:]
    rebuilt_lines = ["---", *new_fm_lines, "---", *lines[end_idx + 1 :]]
    return "\n".join(rebuilt_lines)


def extract_body(content: str) -> str:
    """Extract markdown body content after frontmatter."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("Content missing frontmatter opening delimiter")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("Content missing frontmatter closing delimiter")
    return "\n".join(lines[end_idx + 1 :])


def replace_body(content: str, new_body: str) -> str:
    """Replace the markdown body while preserving frontmatter verbatim."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("Content missing frontmatter opening delimiter")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("Content missing frontmatter closing delimiter")
    rebuilt_lines = [*lines[: end_idx + 1], *new_body.splitlines()]
    rebuilt = "\n".join(rebuilt_lines)
    if content.endswith("\n") and not rebuilt.endswith("\n"):
        rebuilt += "\n"
    return rebuilt


# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    print("Warning: .claude/ directory not found, using cwd as project root", file=sys.stderr)
    return current


def _run_claude_code(prompt: str, model: str | None) -> tuple[str, str, int]:
    """Run Claude Code and return (response_text, raw_result_text, tokens_used)."""
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--print"]
    if model:
        cmd.extend(["--model", model])

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_find_project_root()),
        env=env,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"Error: claude -p failed with code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)

    try:
        events = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"Error: could not parse claude -p JSON output: {exc}", file=sys.stderr)
        sys.exit(1)

    assistant_text = ""
    raw_result_text = ""
    tokens_used = 0
    for event in events:
        if event.get("type") == "assistant":
            message = event.get("message", {})
            for content in message.get("content", []):
                if content.get("type") == "text":
                    assistant_text += content.get("text", "")
        elif event.get("type") == "result":
            raw_result_text = event.get("result", "")
            usage = event.get("usage", {})
            tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    return assistant_text or raw_result_text, raw_result_text, tokens_used


def generate_variant(
    target_path: str,
    goal: str,
    current_content: str,
    failures: list[dict],
    model: str | None,
    optimization_scope: str = "description-only",
    history: list[dict] | None = None,
    diversification_note: str | None = None,
) -> dict:
    """Call Claude Code to generate a variant of the target file.

    Returns dict with variant content, summary, reasoning, and token count.
    """
    # Build the prompt
    failure_section = ""
    if failures:
        failure_section = "\n\nFailed tasks from the last iteration:\n"
        for f in failures:
            label = f.get("query") or f.get("name", "unnamed")
            should_trigger = f.get("should_trigger")
            expectation = ""
            if should_trigger is True:
                expectation = " (expected: SHOULD trigger)"
            elif should_trigger is False:
                expectation = " (expected: should NOT trigger)"
            detail_bits = []
            if f.get("details"):
                detail_bits.append(str(f["details"]))
            if "trigger_rate" in f:
                detail_bits.append(f"raw_trigger_rate={f['trigger_rate']:.2f}")
            details = "; ".join(detail_bits) if detail_bits else "failed"
            failure_section += f"  - {label}{expectation}: {details}\n"

    history_section = ""
    if history:
        history_section = "\n\nPrevious attempts (do NOT repeat — try structurally different approaches):\n"
        for h in history:
            history_section += (
                f"  Iteration {h.get('number', '?')}: {h.get('verdict', '?')} — {h.get('change_summary', '')}\n"
            )

    diversification_section = ""
    if diversification_note:
        diversification_section = f"\n\nSearch diversification instruction:\n{diversification_note}\n"

    protected_sections = extract_protected(current_content)
    protected_notice = ""
    if protected_sections:
        protected_notice = f"""

CRITICAL SAFETY RULE: The file contains {len(protected_sections)} protected section(s) marked with
<!-- DO NOT OPTIMIZE --> and <!-- END DO NOT OPTIMIZE --> markers.
You MUST preserve these sections EXACTLY as they are — character for character.
Do not add, remove, or modify anything between these markers.
This is non-negotiable: protected sections contain safety gates that must not be
removed even if removing them would improve test scores."""

    current_description = extract_description(current_content)
    current_body = extract_body(current_content)

    if optimization_scope == "description-only":
        prompt = f"""You are optimizing an agent/skill file to improve its trigger performance.

Target file: {target_path}
Optimization goal: {goal}

Current content of the file:
<current_content>
{current_content}
</current_content>
Current description:
<current_description>
{current_description}
</current_description>
{failure_section}{history_section}{diversification_section}{protected_notice}

SAFETY RULES:
1. Optimize ONLY the YAML frontmatter `description` field.
   Do not modify any other part of the file. The optimizer evaluates description-trigger
   quality only, so changing routing blocks, body text, or headings is out of scope.

2. Keep the description faithful to the file's actual purpose. Improve routing precision
   by making the description clearer and more triggerable, not by changing the behavior
   or scope of the skill.

3. Keep the skill name, routing, tools, instructions, and all protected sections unchanged.

4. Focus on making the description better at achieving the stated goal. Common
   improvements include:
   - Including natural user phrasings that should trigger this skill
   - Making the first sentence more concrete and specific
   - Removing vague wording that overlaps with unrelated skills
   - Adding concise usage examples when they help routing

5. Treat failed eval tasks as primary routing evidence:
   - If a task SHOULD have triggered but did not, strongly prefer copying the exact
     user phrasing or a very close paraphrase into the description.
   - If a task should NOT have triggered, add clarifying language that separates this
     skill from that request without expanding scope.
   - Optimize for the smallest description change that would make the failed tasks
     more likely to score correctly on the next run.

Please respond with ONLY the improved description text inside <description> tags,
without YAML quoting or frontmatter delimiters, and a brief summary inside <summary> tags.
Do not return the full file.

<description>
[improved description only]
</description>

<summary>
[1-2 sentence description of the change]
</summary>

<deletion_justification>
[why any removed section was replaced safely, or leave blank]
</deletion_justification>"""
        text, raw_result_text, tokens_used = _run_claude_code(prompt, model)

        description_match = re.search(r"<description>(.*?)</description>", text, re.DOTALL)
        if description_match:
            new_payload = description_match.group(1).strip()
        else:
            variant_match = re.search(r"<variant>(.*?)</variant>", text, re.DOTALL)
            if not variant_match:
                print("Error: No <description> or <variant> tags in response", file=sys.stderr)
                sys.exit(1)
            legacy_variant = variant_match.group(1).strip()
            new_payload = extract_description(legacy_variant)

        variant = replace_description(current_content, new_payload)
    elif optimization_scope == "body-only":
        prompt = f"""You are optimizing an agent/skill file to improve its behavioral quality.

Target file: {target_path}
Optimization goal: {goal}

Current content of the file:
<current_content>
{current_content}
</current_content>
Current body:
<current_body>
{current_body}
</current_body>
{failure_section}{history_section}{diversification_section}{protected_notice}

SAFETY RULES:
1. Optimize ONLY the markdown body after the YAML frontmatter.
   Do not modify the frontmatter, skill name, description, routing, tools, or version.
2. Keep the skill faithful to its current purpose. Improve how it behaves, not what broad domain it covers.
3. Preserve headings and protected sections unless you have a clear reason to improve the body structure safely.
4. Prefer the smallest body change that addresses the failed tasks and improves behavioral quality.

Please respond with ONLY the improved body text inside <body> tags and a brief summary inside <summary> tags.
Do not return the full file.

<body>
[improved markdown body only]
</body>

<summary>
[1-2 sentence description of the change]
</summary>

<deletion_justification>
[why any removed section was replaced safely, or leave blank]
</deletion_justification>"""
        text, raw_result_text, tokens_used = _run_claude_code(prompt, model)
        body_match = re.search(r"<body>(.*?)</body>", text, re.DOTALL)
        if body_match:
            new_payload = body_match.group(1).strip("\n")
        else:
            variant_match = re.search(r"<variant>(.*?)</variant>", text, re.DOTALL)
            if not variant_match:
                print("Error: No <body> or <variant> tags in response", file=sys.stderr)
                sys.exit(1)
            legacy_variant = variant_match.group(1).strip()
            new_payload = extract_body(legacy_variant)

        variant = replace_body(current_content, new_payload)
    else:
        raise ValueError(f"Unsupported optimization_scope: {optimization_scope}")

    # Parse summary
    summary_match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else "No summary provided"

    deletion_match = re.search(r"<deletion_justification>(.*?)</deletion_justification>", text, re.DOTALL)
    deletion_justification = deletion_match.group(1).strip() if deletion_match else ""

    # Restore protected sections (safety net); should be a no-op when only the
    # description changes, but keep it as belt-and-suspenders protection.
    variant = restore_protected(current_content, variant)

    # Description-only optimization should never delete sections.
    deletions = detect_deletions(current_content, variant)

    return {
        "variant": variant,
        "summary": summary,
        "deletion_justification": deletion_justification,
        "reasoning": raw_result_text,
        "tokens_used": tokens_used,
        "deletions": deletions,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate agent/skill variant using Claude")
    parser.add_argument("--target", required=True, help="Path to target file (for context)")
    parser.add_argument("--goal", required=True, help="Optimization goal")
    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--current-content", help="Current file content")
    content_group.add_argument("--current-content-file", help="Path to a file containing the current content")
    parser.add_argument("--failures", default="[]", help="JSON list of failed tasks")
    parser.add_argument("--history", default="[]", help="JSON list of previous iterations")
    parser.add_argument("--diversification-note", default=None, help="Optional search diversification hint")
    parser.add_argument("--model", default=None, help="Optional Claude Code model override")
    parser.add_argument(
        "--optimization-scope",
        choices=["description-only", "body-only"],
        default="description-only",
        help="Which part of the file to mutate",
    )
    args = parser.parse_args()

    try:
        failures = json.loads(args.failures)
    except json.JSONDecodeError as e:
        print(f"Error: --failures is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        history = json.loads(args.history)
    except json.JSONDecodeError as e:
        print(f"Error: --history is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    current_content = (
        Path(args.current_content_file).read_text(encoding="utf-8")
        if args.current_content_file
        else args.current_content
    )

    result = generate_variant(
        target_path=args.target,
        goal=args.goal,
        current_content=current_content,
        failures=failures,
        model=args.model,
        optimization_scope=args.optimization_scope,
        history=history if history else None,
        diversification_note=args.diversification_note,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
