#!/usr/bin/env python3
"""
Update routing tables in commands/do.md with generated entries.
Preserves manual entries and creates backups.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


class UpdateError(Exception):
    """Custom exception for update errors."""

    pass


def create_backup(target_file: Path, keep_count: int = 5) -> Path:
    """
    Create timestamped backup of target file and clean up old backups.

    Args:
        target_file: File to backup
        keep_count: Number of recent backups to keep (default: 5)

    Returns path to backup file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = target_file.parent
    backup_name = f".{target_file.name}.backup.{timestamp}"
    backup_path = backup_dir / backup_name

    # Copy file
    import shutil

    shutil.copy2(target_file, backup_path)

    # Clean up old backups (keep only most recent keep_count)
    backup_pattern = f".{target_file.name}.backup.*"
    backups = sorted(
        backup_dir.glob(backup_pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # Most recent first
    )

    # Remove old backups beyond keep_count
    for old_backup in backups[keep_count:]:
        try:
            old_backup.unlink()
        except OSError:
            # Ignore errors deleting old backups
            pass

    return backup_path


def is_auto_generated_row(row: str) -> bool:
    """Check if table row is auto-generated."""
    return "[AUTO-GENERATED]" in row


def parse_markdown_table(lines: List[str], start_idx: int) -> Tuple[List[str], int]:
    """
    Parse markdown table starting at start_idx.

    Returns (table_rows, end_idx)
    """
    table_rows = []
    idx = start_idx

    # Find table end (first line that doesn't start with |)
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("|"):
            break
        table_rows.append(line)
        idx += 1

    return table_rows, idx


def format_table_row(columns: List[str]) -> str:
    """Format list of columns as markdown table row."""
    # Ensure proper pipe formatting with type safety
    row = "| " + " | ".join(str(col) for col in columns) + " |"
    return row


def extract_manual_rows(table_rows: List[str]) -> List[str]:
    """Extract manual (non-auto-generated) rows from table."""
    manual_rows = []

    # Skip header (first 2 rows)
    for row in table_rows[2:]:
        if not is_auto_generated_row(row):
            manual_rows.append(row)

    return manual_rows


def generate_table_rows(entries: List[Dict[str, Any]], table_type: str) -> List[str]:
    """
    Generate table rows from routing entries.

    Returns list of markdown table row strings.
    """
    rows = []

    for entry in entries:
        if table_type == "Intent Detection Patterns":
            # | User Says | Route To | Complexity | [AUTO-GENERATED] |
            columns = [entry["user_says"], entry["route_to"], entry["complexity"], "[AUTO-GENERATED]"]

        elif table_type == "Domain-Specific Routing":
            # | Domain Mentioned | Agent | Typical Complexity | [AUTO-GENERATED] |
            columns = [entry["domain_mentioned"], entry["agent"], entry["typical_complexity"], "[AUTO-GENERATED]"]

        elif table_type == "Task Type Routing":
            # | Task Type | Route To Agent | Complexity | [AUTO-GENERATED] |
            columns = [entry["task_type"], entry["route_to"], entry["complexity"], "[AUTO-GENERATED]"]

        else:
            continue

        rows.append(format_table_row(columns))

    return rows


def update_table_in_content(
    content_lines: List[str], table_name: str, new_entries: List[Dict[str, Any]]
) -> Tuple[List[str], Dict[str, int]]:
    """
    Update a single routing table in content.

    Returns (updated_lines, stats)
    """
    # Find table header
    header_pattern = f"### {table_name}"
    table_start_idx = None

    for idx, line in enumerate(content_lines):
        if header_pattern in line:
            table_start_idx = idx
            break

    if table_start_idx is None:
        raise UpdateError(f"Table header not found: {header_pattern}")

    # Find table start (first line with |)
    table_data_start = None
    for idx in range(table_start_idx, min(table_start_idx + 10, len(content_lines))):
        if content_lines[idx].strip().startswith("|"):
            table_data_start = idx
            break

    if table_data_start is None:
        raise UpdateError(f"Table data not found after header: {header_pattern}")

    # Parse existing table
    existing_table, table_end_idx = parse_markdown_table(content_lines, table_data_start)

    # Extract manual rows (preserve them)
    manual_rows = extract_manual_rows(existing_table)

    # Generate new auto-generated rows
    auto_gen_rows = generate_table_rows(new_entries, table_name)

    # Combine: header (2 rows) + manual rows + auto-generated rows
    header_rows = existing_table[:2]  # Table header and separator
    new_table = header_rows + manual_rows + auto_gen_rows

    # Update content
    updated_lines = content_lines[:table_data_start] + new_table + content_lines[table_end_idx:]

    # Calculate stats
    stats = {
        "added": len(auto_gen_rows),
        "modified": 0,  # Simplified: all auto-gen treated as new
        "removed": 0,
        "manual_preserved": len(manual_rows),
    }

    return updated_lines, stats


def validate_markdown(content: str) -> Tuple[bool, List[str]]:
    """
    Validate markdown table syntax.

    Returns (is_valid, error_messages)
    """
    errors = []

    lines = content.split("\n")

    # Check for common table errors
    in_table = False
    table_col_count = None

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        if stripped.startswith("|"):
            in_table = True

            # Count pipes (columns)
            pipe_count = stripped.count("|")

            if table_col_count is None:
                table_col_count = pipe_count
            elif pipe_count != table_col_count:
                errors.append(
                    f"Line {line_num}: Inconsistent column count (expected {table_col_count}, got {pipe_count})"
                )

            # Check for trailing/leading spaces around pipes (skip separator rows)
            is_separator = re.match(r"^\|[-:| ]+\|$", stripped)
            if not is_separator:
                if not stripped.startswith("| "):
                    errors.append(f"Line {line_num}: Missing space after opening pipe")
                if not stripped.endswith(" |"):
                    errors.append(f"Line {line_num}: Missing space before closing pipe")

        elif in_table:
            # Exited table
            in_table = False
            table_col_count = None

    is_valid = len(errors) == 0
    return is_valid, errors


def generate_diff(original: str, updated: str) -> str:
    """Generate simple diff between original and updated content."""
    orig_lines = original.split("\n")
    updated_lines = updated.split("\n")

    diff_lines = []
    diff_lines.append("--- commands/do.md (original)")
    diff_lines.append("+++ commands/do.md (updated)")

    # Simple line-by-line diff
    for idx, (orig, upd) in enumerate(zip(orig_lines, updated_lines, strict=False), 1):
        if orig != upd:
            diff_lines.append(f"@@ Line {idx} @@")
            diff_lines.append(f"-{orig}")
            diff_lines.append(f"+{upd}")

    return "\n".join(diff_lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update routing tables in commands/do.md")
    parser.add_argument("--input", type=Path, required=True, help="Input JSON from generate_routes.py")
    parser.add_argument("--target", type=Path, required=True, help="Target commands/do.md file path")
    parser.add_argument("--backup", action="store_true", help="Create backup before updating (recommended)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying file")
    parser.add_argument("--auto-confirm", action="store_true", help="Skip interactive confirmation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output to stderr")

    args = parser.parse_args()

    try:
        # Load routing entries
        if not args.input.exists():
            raise UpdateError(f"Input file not found: {args.input}")

        with open(args.input, "r", encoding="utf-8") as f:
            routes_data = json.load(f)

        if routes_data.get("status") != "success":
            raise UpdateError(f"Input routing data has error status: {routes_data.get('status')}")

        routing_entries = routes_data["routing_entries"]

        # Validate target file exists
        if not args.target.exists():
            raise UpdateError(f"Target file not found: {args.target}")

        # Read target file
        with open(args.target, "r", encoding="utf-8") as f:
            original_content = f.read()

        content_lines = original_content.split("\n")

        # Create backup
        backup_path = None
        if args.backup and not args.dry_run:
            backup_path = create_backup(args.target)
            if args.verbose:
                print(f"Backup created: {backup_path}", file=sys.stderr)

        # Update each table
        all_stats = {}
        updated_lines = content_lines

        for table_name, entries in routing_entries.items():
            if not entries:
                continue  # Skip empty tables

            if args.verbose:
                print(f"Updating table: {table_name}", file=sys.stderr)

            try:
                updated_lines, stats = update_table_in_content(updated_lines, table_name, entries)
                all_stats[table_name] = stats

            except UpdateError as e:
                print(f"WARNING: Could not update {table_name}: {e}", file=sys.stderr)
                continue

        # Generate updated content
        updated_content = "\n".join(updated_lines)

        # Validate markdown
        is_valid, validation_errors = validate_markdown(updated_content)
        if not is_valid:
            raise UpdateError("Markdown validation failed:\n" + "\n".join(validation_errors))

        # Generate diff
        diff = generate_diff(original_content, updated_content)

        # Show diff
        if args.verbose or args.dry_run:
            print("\n=== DIFF ===", file=sys.stderr)
            print(diff, file=sys.stderr)
            print("\n=== END DIFF ===\n", file=sys.stderr)

        # Interactive confirmation
        if not args.auto_confirm and not args.dry_run:
            print("\nRouting table updates ready:", file=sys.stderr)
            for table_name, stats in all_stats.items():
                print(
                    f"  - {table_name}: {stats['added']} new entries, {stats['manual_preserved']} manual preserved",
                    file=sys.stderr,
                )

            response = input("\nApply these changes? [y/N]: ")
            if response.lower() not in ["y", "yes"]:
                print("Update cancelled by user", file=sys.stderr)
                sys.exit(0)

        # Write updated content
        if not args.dry_run:
            with open(args.target, "w", encoding="utf-8") as f:
                f.write(updated_content)

            if args.verbose:
                print(f"Updated: {args.target}", file=sys.stderr)

        # Build result
        result = {
            "status": "success",
            "backup_created": str(backup_path) if backup_path else None,
            "changes_applied": all_stats,
            "validation_passed": True,
            "dry_run": args.dry_run,
        }

        # Output result
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except UpdateError as e:
        # Attempt rollback if backup exists
        if backup_path and backup_path.exists():
            print("ERROR: Update failed, attempting rollback...", file=sys.stderr)
            import shutil

            shutil.copy2(backup_path, args.target)
            print("Rollback complete, restored from backup", file=sys.stderr)

        print(
            json.dumps({"status": "error", "error_type": "UpdateError", "message": str(e)}, indent=2), file=sys.stderr
        )
        sys.exit(1)

    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
