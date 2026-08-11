#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart hook: Sync agents repo to ~/.claude

Runs when Claude Code starts in the agents repo.
Syncs agents, skills, hooks, commands, retro, and scripts to ~/.claude/.
Uses additive file-by-file sync (never rmtree) so interrupted syncs
don't leave ~/.claude/hooks/ empty. Stale files are cleaned up for
repo-owned components; additive-only components (commands, retro)
preserve files from other sources.
Retro files are merged at the entry level (### headings) rather than
overwritten, so knowledge accumulated from other repos is preserved.
L1.md is regenerated from merged L2 files at the destination.
Settings.json hooks use repo as source-of-truth (replace, not merge)
to prevent phantom hook errors when switching branches.
Unchanged files are skipped via content comparison.
"""

import errno
import filecmp
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

try:
    import fcntl
except ImportError:
    fcntl = None

sys.path.insert(0, str(Path(__file__).parent / "lib"))
try:
    from hook_utils import hook_error
except ImportError:

    def hook_error(hook_name: str, exc: BaseException) -> None:
        print(f"[{hook_name}] HOOK-ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)


def _try_lock_fd(lock_fd: int) -> bool:
    if fcntl is not None:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            return False

    try:
        import msvcrt

        os.write(lock_fd, b"\0")
        os.lseek(lock_fd, 0, os.SEEK_SET)
        msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
        return True
    except (ImportError, OSError):
        return False


def _unlock_fd(lock_fd: int | None) -> None:
    if lock_fd is None:
        return
    try:
        if fcntl is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        else:
            import msvcrt

            os.lseek(lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
    except (ImportError, OSError):
        pass
    try:
        os.close(lock_fd)
    except OSError:
        pass


def _tolerant_mkdir(path: Path) -> None:
    """mkdir -p that handles broken symlinks in the path.

    Path.mkdir(parents=True, exist_ok=True) raises FileExistsError when any
    component of *path* is a broken symlink (the name exists in the directory
    entry but points nowhere, so exist_ok cannot help). Fix: walk the path
    from root, unlink any broken symlink, then mkdir.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        # Walk from the root to find and fix broken symlinks
        parts = path.resolve().parts if not path.is_absolute() else path.parts
        current = Path(parts[0])
        for part in parts[1:]:
            current = current / part
            if current.is_symlink() and not current.exists():
                current.unlink()
        # Retry after cleanup
        path.mkdir(parents=True, exist_ok=True)


def _atomic_json_write(path: Path, data: dict) -> None:
    """Write JSON atomically via temp file + replace.

    os.replace (not os.rename) so the swap overwrites an existing target
    atomically on Windows too — os.rename raises WinError 183 when the target
    file already exists. See adr/windows-locking-deploy-warning.md.
    """
    tmp_path = path.with_suffix(".json.tmp")
    try:
        # Remove only the known temp entry, then create a new file exclusively.
        # O_EXCL prevents a raced symlink from redirecting the write.
        tmp_path.unlink(missing_ok=True)
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            stream = os.fdopen(fd, "w", encoding="utf-8")
        except Exception:
            os.close(fd)
            raise
        with stream as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _manifest_rel_path(value: object) -> Path | None:
    """Return a canonical relative manifest path, or None when unsafe."""
    if not isinstance(value, str) or not value or "\\" in value:
        return None

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        not posix_path.parts
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in posix_path.parts
        or value != posix_path.as_posix()
    ):
        return None
    return Path(*posix_path.parts)


def _read_sync_manifest(path: Path, destinations: set[str]) -> dict[str, set[Path]]:
    """Load valid owned paths for approved destinations; bad state owns nothing."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}

    owned: dict[str, set[Path]] = {}
    for destination in destinations:
        values = raw.get(destination)
        if not isinstance(values, list):
            continue
        paths = {_manifest_rel_path(value) for value in values}
        owned[destination] = {relative for relative in paths if relative is not None}
    return owned


_DIR_FD_CALLS = (os.open, os.mkdir, os.stat, os.unlink, os.rmdir, os.rename)
_SECURE_DIR_FD_AVAILABLE = (
    os.name == "posix"
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and all(call in os.supports_dir_fd for call in _DIR_FD_CALLS)
    and os.stat in os.supports_follow_symlinks
    and os.utime in os.supports_fd
    and hasattr(os, "fchmod")
)


def _secure_dir_fd_available() -> bool:
    """Return whether this platform can pin no-follow directory traversal."""
    return _SECURE_DIR_FD_AVAILABLE


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _close_fds(fds: list[int]) -> None:
    for fd in reversed(fds):
        try:
            os.close(fd)
        except OSError as e:
            print(f"[sync] WARNING: failed to close directory descriptor: {e}", file=sys.stderr)


class _PinnedDestination:
    """Open directory chain for one destination-relative file."""

    def __init__(self, root: Path, relative: Path, directory_fds: list[int]):
        self.root = root
        self.relative = relative
        self._directory_fds = directory_fds

    @property
    def parent_fd(self) -> int:
        return self._directory_fds[-1]

    @property
    def filename(self) -> str:
        return self.relative.name

    def close(self) -> None:
        fds, self._directory_fds = self._directory_fds, []
        _close_fds(fds)

    def __enter__(self) -> "_PinnedDestination":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def _directory_entry_matches(self, index: int) -> bool:
        try:
            named = os.stat(
                self.relative.parts[index - 1],
                dir_fd=self._directory_fds[index - 1],
                follow_symlinks=False,
            )
            opened = os.fstat(self._directory_fds[index])
        except OSError:
            return False
        return stat.S_ISDIR(named.st_mode) and _same_identity(named, opened)

    def chain_is_current(self) -> bool:
        try:
            named_root = os.stat(self.root, follow_symlinks=False)
            opened_root = os.fstat(self._directory_fds[0])
        except OSError:
            return False
        if not stat.S_ISDIR(named_root.st_mode) or not _same_identity(named_root, opened_root):
            return False
        return all(self._directory_entry_matches(index) for index in range(1, len(self._directory_fds)))

    def file_entry_matches(self, opened: os.stat_result) -> bool:
        try:
            named = os.stat(self.filename, dir_fd=self.parent_fd, follow_symlinks=False)
        except OSError:
            return False
        return stat.S_ISREG(named.st_mode) and _same_identity(named, opened)

    def file_is_current(self, opened: os.stat_result | None) -> bool:
        return opened is not None and self.chain_is_current() and self.file_entry_matches(opened)

    def prune_empty_parents(self) -> None:
        """Remove only pinned empty ancestors, deepest first."""
        for index in range(len(self._directory_fds) - 1, 0, -1):
            if not self._directory_entry_matches(index):
                return
            name = self.relative.parts[index - 1]
            try:
                os.rmdir(name, dir_fd=self._directory_fds[index - 1])
            except FileNotFoundError:
                return
            except OSError as e:
                if e.errno in {errno.ENOTEMPTY, errno.EEXIST, errno.ENOTDIR}:
                    return
                raise


def _open_pinned_destination(root: Path, relative: Path, *, create_parents: bool) -> _PinnedDestination | None:
    """Open a no-follow directory chain and retain every descriptor."""
    if not _secure_dir_fd_available():
        raise OSError(errno.ENOTSUP, "secure descriptor-relative operations unavailable")
    validated = _manifest_rel_path(relative.as_posix())
    if validated != relative:
        return None

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    directory_fds: list[int] = []
    try:
        directory_fds.append(os.open(root, flags))
        for part in relative.parts[:-1]:
            try:
                child_fd = os.open(part, flags, dir_fd=directory_fds[-1])
            except FileNotFoundError:
                if not create_parents:
                    _close_fds(directory_fds)
                    return None
                try:
                    os.mkdir(part, dir_fd=directory_fds[-1])
                except FileExistsError:
                    pass
                child_fd = os.open(part, flags, dir_fd=directory_fds[-1])
            directory_fds.append(child_fd)
    except OSError as e:
        _close_fds(directory_fds)
        if e.errno in {errno.ENOENT, errno.ENOTDIR, errno.ELOOP}:
            return None
        raise
    return _PinnedDestination(root, relative, directory_fds)


def _read_all(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while chunk := os.read(fd, 1024 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def _read_destination_bytes(
    destination: _PinnedDestination, *, allow_symlink_replace: bool = False
) -> tuple[bytes | None, os.stat_result | None]:
    try:
        named = os.stat(destination.filename, dir_fd=destination.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None, None
    if stat.S_ISLNK(named.st_mode) and allow_symlink_replace:
        return None, None
    if not stat.S_ISREG(named.st_mode):
        raise OSError(errno.ELOOP if stat.S_ISLNK(named.st_mode) else errno.EISDIR, "unsafe file destination")

    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(destination.filename, flags, dir_fd=destination.parent_fd)
    try:
        opened = os.fstat(fd)
        if not _same_identity(named, opened):
            raise OSError(getattr(errno, "ESTALE", errno.EIO), "destination changed before open")
        content = _read_all(fd)
        if not destination.chain_is_current() or not destination.file_entry_matches(opened):
            raise OSError(getattr(errno, "ESTALE", errno.EIO), "destination changed while reading")
        return content, opened
    finally:
        os.close(fd)


def _create_pinned_temp(destination: _PinnedDestination, mode: int) -> tuple[str, int]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    for _ in range(8):
        name = f".sync-{secrets.token_hex(16)}.tmp"
        try:
            return name, os.open(name, flags, mode, dir_fd=destination.parent_fd)
        except FileExistsError:
            continue
    raise OSError(errno.EEXIST, "could not allocate secure destination temp file")


def _write_all(fd: int, content: bytes) -> None:
    view = memoryview(content)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError(errno.EIO, "short destination write")
        view = view[written:]


def _replace_pinned_bytes(
    destination: _PinnedDestination,
    content: bytes,
    *,
    mode: int,
    timestamps_ns: tuple[int, int] | None = None,
) -> None:
    temp_name, temp_fd = _create_pinned_temp(destination, mode)
    renamed = False
    try:
        _write_all(temp_fd, content)
        os.fchmod(temp_fd, mode)
        if timestamps_ns is not None:
            os.utime(temp_fd, ns=timestamps_ns)
        os.fsync(temp_fd)
        if not destination.chain_is_current():
            raise OSError(getattr(errno, "ESTALE", errno.EIO), "destination parent changed during write")
        opened = os.fstat(temp_fd)
        os.rename(
            temp_name,
            destination.filename,
            src_dir_fd=destination.parent_fd,
            dst_dir_fd=destination.parent_fd,
        )
        renamed = True
        if not destination.chain_is_current() or not destination.file_entry_matches(opened):
            raise OSError(getattr(errno, "ESTALE", errno.EIO), "destination changed during replace")
    finally:
        try:
            os.close(temp_fd)
        except OSError as e:
            print(f"[sync] WARNING: failed to close destination temp file: {e}", file=sys.stderr)
        if not renamed:
            try:
                os.unlink(temp_name, dir_fd=destination.parent_fd)
            except FileNotFoundError:
                pass
            except OSError as e:
                print(f"[sync] WARNING: failed to remove destination temp file: {e}", file=sys.stderr)


def _copy_file_contents(source: Path) -> tuple[bytes, os.stat_result]:
    source_stat = source.stat()
    with open(source, "rb") as stream:
        return stream.read(), source_stat


def _copy_file_pinned(source: Path, destination: _PinnedDestination) -> None:
    existing, existing_stat = _read_destination_bytes(destination)
    content, source_stat = _copy_file_contents(source)
    if existing == content:
        if not destination.file_is_current(existing_stat):
            raise OSError(getattr(errno, "ESTALE", errno.EIO), "destination changed during compare")
        return
    _replace_pinned_bytes(
        destination,
        content,
        mode=stat.S_IMODE(source_stat.st_mode),
        timestamps_ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
    )


def _write_bytes_pinned(
    root: Path,
    relative: Path,
    content: bytes,
    *,
    mode: int,
    allow_symlink_replace: bool = False,
) -> bool:
    destination = _open_pinned_destination(root, relative, create_parents=True)
    if destination is None:
        return False
    with destination:
        existing, existing_stat = _read_destination_bytes(destination, allow_symlink_replace=allow_symlink_replace)
        if existing == content:
            if not destination.file_is_current(existing_stat):
                raise OSError(getattr(errno, "ESTALE", errno.EIO), "destination changed during compare")
            return True
        _replace_pinned_bytes(destination, content, mode=mode)
        return True


def _unlink_file_pinned(destination: _PinnedDestination) -> bool:
    try:
        named = os.stat(destination.filename, dir_fd=destination.parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(named.st_mode) or not destination.chain_is_current():
        return False
    os.unlink(destination.filename, dir_fd=destination.parent_fd)
    destination.prune_empty_parents()
    return True


def _parse_retro_entries(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse a retro markdown file into header (everything before first ###) and entries.

    Returns (header_text, [(entry_name, entry_block), ...]).
    Each entry_block includes the ### line and all content until the next ### or EOF.
    """
    # Split on ### headings while keeping the delimiter
    parts = re.split(r"(?=^### )", text, flags=re.MULTILINE)

    header = parts[0] if parts else ""
    entries = []
    for part in parts[1:] if len(parts) > 1 else []:
        # Extract the entry name from the ### line
        match = re.match(r"### (.+?)(?:\n|$)", part)
        if match:
            name = match.group(1).strip()
            entries.append((name, part))

    return header, entries


def _merge_retro_text(src_text: str, dst_text: str) -> str:
    src_header, src_entries = _parse_retro_entries(src_text)
    _, dst_entries = _parse_retro_entries(dst_text)

    # Build merged entry list: src entries first, then dst-only entries
    src_names = {name for name, _ in src_entries}
    merged_entries = list(src_entries)
    for name, block in dst_entries:
        if name not in src_names:
            merged_entries.append((name, block))

    # Reassemble: use src header (repo is authoritative for metadata)
    result = src_header
    for _, block in merged_entries:
        result += block

    # Ensure single trailing newline
    return result.rstrip("\n") + "\n"


def merge_retro_file(src_path: Path, dst_path: Path) -> None:
    """Merge a retro markdown file: union of ### entries from both src and dst.

    Entries are identified by their ### heading name. If both files have an
    entry with the same name, the source (repo) version wins. Entries that
    exist only in the destination are preserved.
    """
    src_text = src_path.read_text()
    if not dst_path.exists():
        dst_path.write_text(src_text)
        return
    dst_path.write_text(_merge_retro_text(src_text, dst_path.read_text()))


def _merge_retro_file_pinned(source: Path, destination: _PinnedDestination) -> None:
    existing, existing_stat = _read_destination_bytes(destination)
    source_text = source.read_text()
    result = source_text if existing is None else _merge_retro_text(source_text, existing.decode())
    content = result.encode()
    if existing == content:
        if not destination.file_is_current(existing_stat):
            raise OSError(getattr(errno, "ESTALE", errno.EIO), "destination changed during merge")
        return
    mode = stat.S_IMODE(existing_stat.st_mode) if existing_stat is not None else stat.S_IMODE(source.stat().st_mode)
    _replace_pinned_bytes(destination, content, mode=mode)


def _render_l1_at_dst(dst_retro: Path) -> str | None:
    """Render L1.md content from merged destination L2 files."""
    l2_dir = dst_retro / "L2"
    if not l2_dir.is_dir():
        return None

    l2_files = sorted(l2_dir.glob("*.md"))
    if not l2_files:
        return None

    topic_groups: dict[str, list[str]] = {}

    for l2_file in l2_files:
        try:
            content = l2_file.read_text()
        except OSError:
            continue

        tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)", content)
        if tags_match:
            raw_tags = [t.strip() for t in tags_match.group(1).split(",")]
            heading_tags = [t for t in raw_tags if t not in ("go", "python", "typescript")][:3]
            if not heading_tags:
                heading_tags = raw_tags[:2]
            tag_key = " / ".join(t.replace("-", " ").title() for t in heading_tags) + " Patterns"
        else:
            tag_key = l2_file.stem.replace("-", " ").title() + " Patterns"

        sections = re.findall(r"###\s+(.+?)(?:\n\n|\n)(.+?)(?:\n\n|\n---|$)", content, re.DOTALL)
        learnings = []
        for heading, body in sections:
            first_line = body.strip().split("\n")[0][:100]
            learnings.append(f"{heading.strip()}: {first_line}")

        if not learnings:
            h2_sections = re.findall(r"##\s+(.+)", content)
            learnings = [h.strip() for h in h2_sections if not h.startswith("#")]

        if learnings:
            if tag_key not in topic_groups:
                topic_groups[tag_key] = []
            topic_groups[tag_key].extend(learnings)

    lines = ["# Accumulated Knowledge (L1 Summary)", ""]
    line_budget = 20
    lines_used = 2

    for group_name, learnings in topic_groups.items():
        if lines_used >= line_budget:
            break
        lines.append(f"## {group_name}")
        lines_used += 1
        for learning in learnings:
            if lines_used >= line_budget:
                break
            lines.append(f"- {learning}")
            lines_used += 1
        lines.append("")
        lines_used += 1

    return "\n".join(lines) + "\n"


def regenerate_l1_at_dst(dst_retro: Path) -> None:
    """Regenerate L1.md at the destination from merged L2 files.

    Mirrors the logic in feature-state.py _regenerate_l1() but runs
    at sync time against ~/.claude/retro/.
    """
    content = _render_l1_at_dst(dst_retro)
    if content is not None:
        (dst_retro / "L1.md").write_text(content)


def _regenerate_l1_at_dst_pinned(dst_retro: Path) -> None:
    destination = _open_pinned_destination(dst_retro, Path("L1.md"), create_parents=True)
    if destination is None:
        raise OSError("unsafe L1 destination path")
    with destination:
        existing, existing_stat = _read_destination_bytes(destination)
        rendered = _render_l1_at_dst(dst_retro)
        if rendered is None:
            return
        content = rendered.encode()
        if existing == content:
            if not destination.file_is_current(existing_stat):
                raise OSError(getattr(errno, "ESTALE", errno.EIO), "L1 destination changed during render")
            return
        mode = stat.S_IMODE(existing_stat.st_mode) if existing_stat is not None else 0o644
        _replace_pinned_bytes(destination, content, mode=mode)


# NOTE: Hook sync uses repo-as-source-of-truth (replace, not merge) to prevent
# phantom hook errors when switching branches. User hooks added manually or from
# other repos will be overwritten. Non-hook keys are preserved. See ADR-104.
def sync_settings(repo_settings: dict, global_settings: dict) -> dict:
    """Sync repo settings as source-of-truth for hooks and attribution.

    The repo's hook list is authoritative: hooks that no longer exist in the
    repo settings are removed from global settings.  This prevents phantom
    hook errors when switching branches (hook registered from branch A,
    file cleaned up on branch B, but settings still reference it).

    Attribution is enforced: if the repo settings define attribution,
    it is synced. If neither repo nor global settings define attribution,
    empty attribution is set to disable Claude Code's default attribution
    (per CLAUDE.md: no "Generated with Claude Code" or "Co-Authored-By").

    Non-hook keys in global settings are preserved.
    """
    result = global_settings.copy()

    # Repo hooks are the authoritative set — replace entirely
    repo_hooks = repo_settings.get("hooks", {})
    result["hooks"] = repo_hooks

    # Ensure attribution is disabled (CLAUDE.md requirement).
    # Repo setting wins if present; otherwise ensure empty attribution exists.
    if "attribution" in repo_settings:
        result["attribution"] = repo_settings["attribution"]
    elif "attribution" not in result:
        result["attribution"] = {"commit": "", "pr": ""}

    return result


def _backup_settings_json(settings_path: Path, keep: int = 3) -> None:
    """Write a timestamped backup of settings.json before overwriting.

    Matches the CLAUDE.md backup pattern: timestamped file, capped at N,
    skipped when content is identical to the most recent backup.
    """
    import datetime

    if not settings_path.exists():
        return

    user_claude = settings_path.parent
    existing_backups = sorted(user_claude.glob("settings.json.backup.*"))

    # Skip backup when content is identical to the most recent backup
    if existing_backups:
        try:
            if filecmp.cmp(settings_path, existing_backups[-1], shallow=False):
                return
        except OSError:
            pass

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = user_claude / f"settings.json.backup.{timestamp}"
    try:
        shutil.copy2(settings_path, backup_path)
    except OSError:
        pass

    # Cap at keep most recent backups
    all_backups = sorted(user_claude.glob("settings.json.backup.*"))
    if len(all_backups) > keep:
        for old_backup in all_backups[:-keep]:
            try:
                old_backup.unlink()
            except OSError:
                pass


def _read_install_mode(user_claude: Path) -> str:
    """Read the install mode from the install manifest.

    Returns "symlink" or "copy" (default).
    """
    manifest_path = user_claude / ".install-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest.get("mode", "copy")
    except (json.JSONDecodeError, OSError):
        return "copy"


def _canonical_repo_root(user_claude: Path) -> Path | None:
    """Read the canonical toolkit path from the install manifest.

    Returns the toolkit_path as a Path if it exists and is a directory,
    otherwise None.  This provides a stable repo root for _resolves_inside
    even when CWD is a worktree that bypassed detection.
    """
    manifest_path = user_claude / ".install-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        toolkit_path = manifest.get("toolkit_path", "")
        if toolkit_path:
            p = Path(toolkit_path)
            if p.is_dir():
                return p
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _resolves_inside(path: Path, root: "Path | list[Path]") -> bool:
    """True when *path* resolves to *root* or a descendant of *root*.

    Safety guard: prevents destructive operations (rmtree, unlink) from
    reaching repo files through symlinks.  When ~/.claude/skills/
    contains a symlink pointing into the repo, code that traverses the
    symlink sees regular files whose realpath is inside the repo.
    Deleting those deletes tracked source files.

    *root* may be a single Path or a list of Paths.  When a list is
    given, True is returned if the resolved path falls inside ANY root.
    This lets callers protect both the CWD-based repo_root AND the
    canonical toolkit_path from the install manifest -- vital when sync
    runs from a worktree that bypassed detection.
    """
    roots = [root] if isinstance(root, Path) else root
    try:
        resolved = str(path.resolve())
    except OSError:
        # Cannot resolve the candidate path: fail closed (treat as inside).
        return True
    for r in roots:
        try:
            root_str = str(r.resolve())
        except OSError:
            # Cannot resolve this root: fail closed rather than let a
            # deletion proceed unverified against it.
            return True
        if resolved == root_str or resolved.startswith(root_str + os.sep):
            return True
    return False


def _is_ephemeral_path(path: Path) -> bool:
    """Check if a path is ephemeral (will be cleaned up automatically).

    Currently checks for /tmp/ prefixed paths. Resolves symlinks first
    to prevent bypass via symlinked paths.
    """
    return str(path.resolve()).startswith("/tmp/")


def _update_manifest_toolkit_path(user_claude: Path, repo_root: Path) -> None:
    """Update the toolkit_path in the install manifest when the repo has moved.

    This happens when the repo is re-cloned to a different directory (e.g.,
    renamed from claude-code-toolkit to vexjoy-agent). The manifest records
    the old path, which breaks symlink validation. Update it to the current
    repo root so future runs and install-doctor can find the source.

    Safety: never record an ephemeral path (/tmp/) as the toolkit location.
    """
    manifest_path = user_claude / ".install-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    # Never point the manifest at an ephemeral path
    if _is_ephemeral_path(repo_root):
        return

    current_path = str(repo_root)
    recorded_path = manifest.get("toolkit_path", "")
    if recorded_path != current_path:
        # A repo "move" means the old path is gone. When the recorded path
        # still exists as a directory, this run is indistinguishable from an
        # undetected worktree -- rewriting the manifest would collapse the
        # multi-root deletion guard onto the worktree path. Keep the record.
        if recorded_path and Path(recorded_path).is_dir():
            print(
                "[sync] manifest toolkit_path kept: recorded path",
                recorded_path,
                "is still present; current run is at",
                current_path,
                "(worktree or copy?)",
                file=sys.stderr,
            )
            return
        manifest["toolkit_path"] = current_path
        _atomic_json_write(manifest_path, manifest)


def _ensure_symlink(src: Path, dst: Path, repo_root: "Path | list[Path] | None" = None) -> bool:
    """Ensure dst is a symlink pointing to src.

    If dst is already the correct symlink, returns True (no change needed).
    If dst is a broken symlink, stale symlink, or regular directory, removes
    it and creates the correct symlink. Returns True on success.

    Safety guards:
    - Refuses to create symlinks pointing into /tmp/ (ephemeral targets).
    - When *repo_root* is provided, refuses to rmtree/unlink any path that
      resolves inside the repo working tree.  This prevents data loss when
      a parent symlink (e.g. ~/.claude/skills -> repo/skills/) causes dst
      to resolve into the repo even though dst itself is not a symlink.
    """
    # Never create a symlink to an ephemeral path
    if _is_ephemeral_path(src):
        print(
            f"[sync] BLOCKED: refusing to symlink {dst} -> {src} (ephemeral /tmp/ target)",
            file=sys.stderr,
        )
        return False

    if dst.is_symlink():
        try:
            current_target = dst.resolve()
            if current_target == src.resolve():
                return True  # Already correct
        except OSError:
            pass
        # Wrong target or unreadable — remove and recreate
        dst.unlink()

    elif dst.is_dir():
        # Regular directory from a previous copy-mode install or broken sync.
        # Remove it so we can replace with a symlink.
        # SAFETY: if dst resolves inside the repo (parent symlink traversal),
        # rmtree would destroy tracked source files.  Skip + loud stderr.
        if repo_root is not None and _resolves_inside(dst, repo_root):
            print(
                f"[sync] BLOCKED: refusing to rmtree {dst} (resolves inside repo {repo_root})",
                file=sys.stderr,
            )
            return False
        shutil.rmtree(dst)

    elif dst.exists():
        if repo_root is not None and _resolves_inside(dst, repo_root):
            print(
                f"[sync] BLOCKED: refusing to unlink {dst} (resolves inside repo {repo_root})",
                file=sys.stderr,
            )
            return False
        dst.unlink()

    try:
        dst.symlink_to(src)
    except FileExistsError:
        # Race: another process created the symlink between our check and
        # symlink_to. If it points to the right target, that's fine.
        if dst.is_symlink():
            try:
                if dst.resolve() == src.resolve():
                    return True
            except OSError:
                pass
            # Wrong target — remove and retry once
            dst.unlink(missing_ok=True)
            dst.symlink_to(src)
        else:
            # Regular file/dir appeared — remove and retry once
            if repo_root is not None and _resolves_inside(dst, repo_root):
                print(
                    f"[sync] BLOCKED: refusing to remove {dst} in race recovery (resolves inside repo {repo_root})",
                    file=sys.stderr,
                )
                return False
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink(missing_ok=True)
            dst.symlink_to(src)
    return True


def _merged_runtime_index(tracked: Path, local: Path) -> dict | None:
    """Merge the tracked skills index with the gitignored local override.

    Tracked items load first; local items fill gaps per-name (setdefault,
    add-only). A stale INDEX.local.json can never hide a tracked skill and
    never overrides tracked entry content — the same merge semantics as
    _load_index_items in scripts/routing-manifest.py, pre-route.py, and
    index-router.py (PR #778). Top-level metadata comes from the tracked
    file; local supplies it only when the tracked file is missing/invalid.

    Returns None when neither file yields a JSON object.
    """
    docs = []
    for path in (tracked, local):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if isinstance(raw, dict):
            docs.append(raw)
    if not docs:
        return None
    merged = dict(docs[0])
    skills: dict = {}
    for doc in docs:
        loaded = doc.get("skills", {})
        if isinstance(loaded, dict):
            for name, data in loaded.items():
                skills.setdefault(name, data)
    merged["skills"] = skills
    return merged


def _sync_runtime_skill_index(src: Path, dst: Path, *, secure_destination: bool = False) -> bool:
    """Write ~/.claude/skills/INDEX.json as a real merged file.

    The runtime index the harness reads — and may rewrite in place — must be
    a regular file, never a symlink into the repo:
    - A symlink to the tracked INDEX.json leaks in-place harness writes into
      the repo's public index (the recurring private-skill leak).
    - A symlink to the gitignored INDEX.local.json lets a stale local file
      hide newly added tracked skills (replace semantics, PR #778 bug class).
    A materialized tracked-first merge gives both invariants: every tracked
    entry is present, and writes land in ~/.claude only.

    Returns True when the runtime index exists after the call.
    """
    merged = _merged_runtime_index(src / "INDEX.json", src / "INDEX.local.json")
    if merged is None:
        return False
    runtime = dst / "INDEX.json"
    if secure_destination:
        content = (json.dumps(merged, indent=2) + "\n").encode()
        return _write_bytes_pinned(
            dst,
            Path("INDEX.json"),
            content,
            mode=0o600,
            allow_symlink_replace=True,
        )
    # Skip the write when content already matches. Only compare a real file:
    # reading through a symlink would compare repo content and leave the
    # leaking symlink in place.
    if runtime.is_file() and not runtime.is_symlink():
        try:
            if json.loads(runtime.read_text(encoding="utf-8")) == merged:
                return True
        except (json.JSONDecodeError, OSError):
            pass
    # _atomic_json_write swaps via os.replace, which replaces a pre-fix
    # symlink's directory entry — the repo file it pointed at is untouched.
    _atomic_json_write(runtime, merged)
    return True


def _has_promoted_to(skill_dir: Path, skills_root: "Path | None" = None) -> bool:
    """True when SKILL.md has promoted_to: and the target skill exists.

    Skills with promoted_to: are folded into a parent skill and should not
    appear as separate entries in ~/.claude/skills/ or mirror runtimes.
    Returns False when the target skill does not exist yet (forward-looking
    promotion tag), keeping the source skill deployed until its replacement
    is live.

    Uses a lightweight regex scan of the frontmatter block (between --- delimiters)
    to avoid pulling in a YAML parser dependency.
    """
    skill_md = skill_dir / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    # Frontmatter is between the first two --- lines
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    frontmatter = text[3:end]
    m = re.search(r"^promoted_to\s*:\s*(.+)$", frontmatter, re.MULTILINE)
    if not m:
        return False
    # Validate the target skill exists in the repo
    if skills_root is not None:
        target_name = m.group(1).strip()
        # Search category subdirectories for the target skill
        for category in skills_root.iterdir():
            if category.is_dir() and (category / target_name / "SKILL.md").exists():
                return True
        # Target not found — keep deploying the source skill
        return False
    return True


def _is_support_dir(item: Path) -> bool:
    """Return whether a root skills directory contains support material.

    Public utility directories may have nested data instead of root Markdown.
    Other support directories are detected by shape so local overlays do not
    need to be named in this repository.
    """
    if item.name in {"shared-patterns", "workflow", "kb"}:
        return True
    if item.name.startswith(".") or (item / "SKILL.md").exists():
        return False
    children = list(item.iterdir())
    has_md = any(child.is_file() and child.suffix == ".md" for child in children)
    has_skill_subdir = any(child.is_dir() and (child / "SKILL.md").exists() for child in children)
    return has_md and not has_skill_subdir


def _sync_skills_flat_symlinks(src: Path, dst: Path, repo_root: "Path | list[Path] | None" = None) -> None:
    """Create flat per-skill symlinks from nested category structure.

    The repo organizes skills into category folders:
        skills/meta/do/SKILL.md
        skills/process/planning/SKILL.md

    But Claude Code only discovers flat ~/.claude/skills/*/SKILL.md.
    This function creates individual symlinks to flatten the structure:
        ~/.claude/skills/do → repo/skills/meta/do
        ~/.claude/skills/planning → repo/skills/process/planning

    Root-level items (INDEX.json and support directories) are symlinked
    directly.

    Runtime-index policy: ~/.claude/skills/INDEX.json is materialized as a
    real merged file (tracked first, local fills gaps per-name), never a
    symlink. See _sync_runtime_skill_index for the two invariants this keeps.

    *repo_root* enables the repo-path safety guard in _ensure_symlink.
    """
    # If dst is a single symlink to the repo (old-style), replace with a real dir
    if dst.is_symlink():
        dst.unlink()

    _tolerant_mkdir(dst)

    # Track what we create so we can clean stale entries
    expected_names: set[str] = set()

    # Materialize the runtime index as a real merged file (never a symlink).
    if _sync_runtime_skill_index(src, dst):
        expected_names.add("INDEX.json")

    # Symlink root-level files (INDEX.local.json, README.md). INDEX.json is
    # excluded: it was materialized above.
    for item in src.iterdir():
        if item.is_file() and item.name != "INDEX.json":
            expected_names.add(item.name)
            target = dst / item.name
            if target.is_symlink() or target.exists():
                if target.is_symlink() and target.resolve() == item.resolve():
                    continue
                target.unlink()
            try:
                target.symlink_to(item)
            except FileExistsError:
                # Race: concurrent process created it between unlink and symlink_to
                pass

    # Symlink root-level support directories. These hold reference or utility
    # files, not independently routed skills.
    support_dirs: set[str] = set()
    for item in src.iterdir():
        if item.is_dir() and _is_support_dir(item):
            support_dirs.add(item.name)
            expected_names.add(item.name)
            _ensure_symlink(item, dst / item.name, repo_root=repo_root)

    # Create per-skill symlinks from nested category folders.
    # Each category folder (meta/, process/, etc.) contains skill subdirectories.
    for category_dir in sorted(src.iterdir()):
        if not category_dir.is_dir():
            continue
        if category_dir.name in support_dirs:
            continue  # Already handled above
        if category_dir.name.startswith("."):
            continue

        # Check if this is a category folder (contains subdirectories with SKILL.md)
        # vs a flat skill (contains SKILL.md directly — shouldn't exist but handle it)
        if (category_dir / "SKILL.md").exists():
            # Flat skill at root level (legacy or special case)
            expected_names.add(category_dir.name)
            _ensure_symlink(category_dir, dst / category_dir.name, repo_root=repo_root)
        else:
            # Category folder: create symlinks for each skill inside
            for skill_dir in sorted(category_dir.iterdir()):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    if _has_promoted_to(skill_dir, skills_root=src):
                        continue  # Folded into parent; skip deployment
                    expected_names.add(skill_dir.name)
                    _ensure_symlink(skill_dir, dst / skill_dir.name, repo_root=repo_root)
                elif skill_dir.is_dir() and (skill_dir / "profile.json").exists():
                    # Voice profile directories (data-only, no SKILL.md)
                    expected_names.add(skill_dir.name)
                    _ensure_symlink(skill_dir, dst / skill_dir.name, repo_root=repo_root)

    # Clean stale entries: remove symlinks no longer in expected_names, with
    # two preservation rules when repo_root is known:
    #   (a) Preserve if the target resolves INSIDE a known root — it belongs to
    #       a repo (e.g. canonical main repo when syncing from a worktree).
    #   (b) Preserve if the target is live and resolves OUTSIDE all known roots
    #       — it is a foreign symlink (e.g. ~/.agents/skills/foo) that we must
    #       not touch.
    # When repo_root is None we cannot apply either guard, so anything not in
    # expected_names is removed (original behaviour).
    for item in dst.iterdir():
        if item.name not in expected_names and item.is_symlink():
            if repo_root is not None:
                if _resolves_inside(item, repo_root):
                    continue  # (a) inside a known repo root — preserve
                if item.exists():
                    continue  # (b) live and outside all roots — foreign, preserve
            item.unlink()


def _is_git_worktree(path: Path) -> bool:
    """Detect if path is inside a git worktree (not the main working tree).

    Git worktrees have a .git *file* (not directory) that points to the main
    repo's .git/worktrees/<name>/ directory. Submodules also have a .git file
    but point to .git/modules/<name>/ — we distinguish by checking for
    "worktrees/" in the gitdir path. The git rev-parse check handles both
    cases correctly as a fallback.

    This prevents the sync hook from re-pointing ~/.claude/ symlinks at
    ephemeral worktree paths (e.g. /tmp/...-worktree-...) that get cleaned up,
    which breaks every hook until manual reinstall.

    Safe default: when .git is a file (worktree/submodule marker) but neither
    the file content nor git rev-parse can determine the type, assume worktree
    and refuse sync.  A false positive (blocking a submodule) is harmless; a
    false negative (allowing a worktree) causes data loss.
    """
    # Fast check: reject ephemeral paths (e.g. /tmp/)
    if _is_ephemeral_path(path):
        return True

    # .git file (not directory) is a worktree OR submodule marker.
    # Distinguish by reading the file: worktrees point to .git/worktrees/<name>,
    # submodules point to .git/modules/<name>. Only reject worktrees.
    dot_git = path / ".git"
    dot_git_is_file = dot_git.is_file()
    if dot_git_is_file:
        try:
            content = dot_git.read_text().strip()
            # Format: "gitdir: <path>"
            if "worktrees/" in content:
                return True
            # Submodule (.git/modules/) — not a worktree, allow sync
            return False
        except OSError:
            # Can't read .git file — fall through to git rev-parse check
            pass

    # Belt-and-suspenders: ask git directly
    try:
        git_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(path),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        git_common = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(path),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        # In worktrees, --git-dir returns .git/worktrees/<name> while
        # --git-common-dir returns the main repo's .git/. They differ.
        if os.path.realpath(git_dir) != os.path.realpath(git_common):
            return True
    except (subprocess.CalledProcessError, OSError):
        pass

    # Safe default: if .git is a file (worktree/submodule marker) but we
    # could not determine its type, assume worktree and refuse sync.
    # False positive (blocking a submodule) is harmless; false negative
    # (allowing a worktree) causes symlink re-pointing and potential data loss.
    if dot_git_is_file:
        print(
            f"[sync] WARNING: .git file at {path} unreadable and git rev-parse "
            f"failed; assuming worktree (safe default)",
            file=sys.stderr,
        )
        return True

    return False


def main():
    # Only run when in the agents repo
    cwd = Path.cwd()

    # Check if CWD is the agents repo (has skills/, agents/, and hooks/ dirs)
    is_agents_repo = (cwd / "skills").is_dir() and (cwd / "agents").is_dir() and (cwd / "hooks").is_dir()
    if not is_agents_repo:
        return

    # CRITICAL: Never sync from a git worktree. Worktrees are ephemeral copies
    # (often in /tmp/) that get deleted after the agent finishes. Syncing from
    # one re-points ~/.claude/ symlinks at paths that will vanish, breaking
    # every hook until manual reinstall. See: repeated hooks breakage incidents.
    if _is_git_worktree(cwd):
        print("[sync] Skipping: running inside a git worktree (ephemeral path)", file=sys.stderr)
        return

    # Paths - use CWD as repo root (not script location, since script may be in ~/.claude/hooks/)
    repo_root = cwd
    user_claude = Path.home() / ".claude"

    # Inter-process lock: concurrent SessionStarts both run this hook
    # (once: true is per-session, not per-host). Non-blocking flock:
    # if another process holds it, skip — its sync makes ours redundant.
    lock_path = user_claude / ".sync.lock"
    lock_fd = None
    try:
        lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        if not _try_lock_fd(lock_fd):
            raise OSError("sync lock already held")
    except OSError:
        # Lock held by another process — skip sync
        if lock_fd is not None:
            _unlock_fd(lock_fd)
        print("[sync] Skipping: another sync is in progress", file=sys.stderr)
        return

    try:
        _main_inner(repo_root, user_claude)
    finally:
        # Release lock
        try:
            _unlock_fd(lock_fd)
        except OSError:
            pass


def _main_inner(repo_root: Path, user_claude: Path) -> None:
    """Core sync logic, called under flock."""
    # Detect install mode from manifest. In symlink mode, components that
    # support it get directory-level symlinks instead of file-by-file copies.
    install_mode = _read_install_mode(user_claude)

    # Read the canonical toolkit_path BEFORE any manifest rewrite. Ordering
    # matters: if an undetected worktree updated the manifest first, the
    # canonical root would collapse onto the worktree path and the multi-root
    # deletion guard below would protect nothing but the worktree.
    canonical = _canonical_repo_root(user_claude)
    if canonical is None:
        print(
            "[sync] WARNING: no canonical toolkit_path in install manifest; "
            "deletion guard reduced to single-root protection",
            file=sys.stderr,
        )

    # Update the manifest's toolkit_path if the repo has moved (e.g., renamed
    # from claude-code-toolkit to vexjoy-agent and re-cloned). Refuses the
    # rewrite while the recorded path still exists (undetected worktree).
    _update_manifest_toolkit_path(user_claude, repo_root)

    # Build the protected-roots list: repo_root (CWD) plus the canonical
    # toolkit_path from the manifest.  If sync somehow runs from a worktree
    # that bypassed _is_git_worktree, repo_root is the worktree path but the
    # manifest still records the MAIN repo.  Deletions must be blocked for
    # both.  When both resolve to the same directory, the list collapses to
    # a single entry.
    if canonical and canonical.resolve() != repo_root.resolve():
        protected_roots: Path | list[Path] = [repo_root, canonical]
    else:
        protected_roots = repo_root

    # Components to sync (directories)
    components = [
        ("agents", "agents"),
        ("skills", "skills"),
        ("hooks", "hooks"),
        ("commands", "commands"),  # Still needed for slash menu discovery
        ("retro", "retro"),  # Knowledge store for retro-knowledge-injector hook
        ("scripts", "scripts"),  # Deterministic CLI tools (learning-db.py, classify-repo.py, etc.)
    ]

    # Components that only ADD files (never remove stale ones from dst).
    # Commands can come from skills auto-generation or other sources;
    # retro entries accumulate from multiple repos.
    additive_only = {"commands", "retro"}

    # Components that need entry-level merge (not file-level overwrite).
    # Retro L2 files use ### headings as entries; merging preserves
    # knowledge accumulated from other repos in ~/.claude/retro/.
    merge_components = {"retro"}

    # Components eligible for symlink mode. Merge components (retro) and
    # additive components (commands) must always use file-by-file sync because
    # they aggregate content from multiple sources.
    symlinkable_components = {"agents", "skills", "hooks", "scripts"}

    synced = []
    errors = []

    # Copy-mode cleanup uses an ownership record. A first run seeds the record
    # without claiming or deleting pre-existing foreign files.
    owned_destinations = {dst for src, dst in components if src not in additive_only}
    sync_manifest_path = user_claude / ".sync-manifest.json"
    prior_owned = _read_sync_manifest(sync_manifest_path, owned_destinations) if install_mode == "copy" else {}
    dst_source_paths: dict[str, set[Path]] = {name: set() for name in owned_destinations}
    dst_owned_paths: dict[str, set[Path]] = {name: set() for name in owned_destinations}
    failed_destinations: set[str] = set()
    secure_dir_fd = _secure_dir_fd_available()
    if install_mode == "copy" and not secure_dir_fd:
        failed_destinations.update(owned_destinations)

    for src_name, dst_name in components:
        src = repo_root / src_name
        dst = user_claude / dst_name
        tracks_ownership = install_mode == "copy" and src_name not in additive_only

        if not src.exists():
            if tracks_ownership:
                failed_destinations.add(dst_name)
            continue

        src_relative_paths: set[Path] = set()
        successfully_owned_paths: set[Path] = set()
        try:
            # Symlink mode: create a directory-level symlink for eligible components.
            # This preserves the symlinks created by install.sh --symlink instead of
            # destroying them and replacing with file copies.
            if install_mode == "symlink" and src_name in symlinkable_components:
                # Skills use per-skill symlinks because the repo organizes skills
                # into category folders (skills/meta/do/, skills/process/planning/)
                # but Claude Code only discovers flat ~/.claude/skills/*/SKILL.md.
                # Create individual symlinks to flatten the nested structure.
                if src_name == "skills":
                    _sync_skills_flat_symlinks(src, dst, repo_root=protected_roots)
                    count = sum(1 for d in dst.iterdir() if d.is_dir() and not d.name.startswith("."))
                    synced.append(f"{dst_name}(symlink, {count} skills)")
                else:
                    _ensure_symlink(src, dst, repo_root=protected_roots)
                    synced.append(f"{dst_name}(symlink)")
                continue

            if not secure_dir_fd:
                raise OSError(errno.ENOTSUP, "secure descriptor-relative operations unavailable")

            # Copy mode: resolve any existing symlinks to a real directory before
            # file-by-file sync. This handles the transition from symlink to copy mode.
            if dst.is_symlink():
                dst.unlink()

            _tolerant_mkdir(dst)

            # Additive sync: copy individual files, never nuke the directory.
            # This is safe even if interrupted — each file copy is independent.
            # Files with identical content are skipped to reduce I/O.
            count = 0
            merge_count = 0
            use_merge = src_name in merge_components
            for item in src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src)
                    src_relative_paths.add(rel)
                    destination: _PinnedDestination | None = None
                    try:
                        if use_merge and item.name == "L1.md":
                            count += 1
                            continue  # Skip L1 — regenerated below
                        destination = _open_pinned_destination(dst, rel, create_parents=True)
                        if destination is None:
                            raise OSError("unsafe destination path")
                        with destination:
                            if use_merge and item.suffix == ".md":
                                _merge_retro_file_pinned(item, destination)
                                merge_count += 1
                            else:
                                _copy_file_pinned(item, destination)
                        count += 1
                        if tracks_ownership:
                            successfully_owned_paths.add(rel)
                    except Exception as file_err:
                        if destination is not None and rel in prior_owned.get(dst_name, set()):
                            successfully_owned_paths.add(rel)
                        print(
                            f"[sync] ERROR: {dst_name}/{rel}: {file_err}",
                            file=sys.stderr,
                        )

            # Runtime skill index: overwrite the plain tracked copy with the
            # tracked+local merge (same invariants as symlink mode). Record
            # its path so deferred stale cleanup spares it even when the repo
            # has only INDEX.local.json.
            if src_name == "skills" and _sync_runtime_skill_index(src, dst, secure_destination=True):
                src_relative_paths.add(Path("INDEX.json"))
                if tracks_ownership:
                    successfully_owned_paths.add(Path("INDEX.json"))

            # For merge components, regenerate L1 from merged L2 files
            if use_merge and merge_count > 0:
                _regenerate_l1_at_dst_pinned(dst)
                synced.append(f"{dst_name}({count}, {merge_count} merged)")
            else:
                synced.append(f"{dst_name}({count})")
        except Exception as e:
            errors.append(f"{dst_name}: {e}")
            if tracks_ownership:
                failed_destinations.add(dst_name)
        finally:
            if tracks_ownership:
                dst_source_paths[dst_name].update(src_relative_paths)
                dst_owned_paths[dst_name].update(successfully_owned_paths)

    # Deferred stale cleanup considers only paths this sync recorded after a
    # successful install. Invalid, missing, or unsafe state never grants ownership.
    if install_mode == "copy":
        next_owned: dict[str, set[Path]] = {}
        for dst_name in sorted(owned_destinations):
            installed_paths = dst_owned_paths[dst_name]
            if dst_name in failed_destinations:
                next_owned[dst_name] = prior_owned.get(dst_name, set()) | installed_paths
                continue

            next_owned[dst_name] = set(installed_paths)
            stale_paths = prior_owned.get(dst_name, set()) - dst_source_paths[dst_name]
            dst = user_claude / dst_name
            for rel in sorted(stale_paths):
                stale_file = dst / rel
                if _resolves_inside(stale_file, protected_roots):
                    print(
                        f"[sync] BLOCKED: stale-cleanup refusing to unlink {dst_name}/{rel} (resolves inside repo)",
                        file=sys.stderr,
                    )
                    continue
                try:
                    destination = _open_pinned_destination(dst, rel, create_parents=False)
                    if destination is None:
                        continue
                    with destination:
                        _unlink_file_pinned(destination)
                except OSError as e:
                    next_owned[dst_name].add(rel)
                    errors.append(f"stale-cleanup-{dst_name}/{rel}: {e}")

        manifest_data = {name: sorted(path.as_posix() for path in paths) for name, paths in sorted(next_owned.items())}
        try:
            _atomic_json_write(sync_manifest_path, manifest_data)
        except OSError as e:
            errors.append(f"sync-manifest: {e}")

    # Sync settings.json — repo hooks replace global hooks
    repo_settings_path = repo_root / ".claude" / "settings.json"
    global_settings_path = user_claude / "settings.json"

    if repo_settings_path.exists():
        try:
            with open(repo_settings_path) as f:
                repo_settings = json.load(f)

            global_settings = {}
            if global_settings_path.exists():
                try:
                    content = global_settings_path.read_text().strip()
                    if content:  # Only parse if not empty
                        global_settings = json.loads(content)
                except json.JSONDecodeError:
                    pass  # Invalid JSON, start fresh

            merged = sync_settings(repo_settings, global_settings)

            _backup_settings_json(global_settings_path)
            _atomic_json_write(Path(global_settings_path), merged)
            # Harden permissions after write (ADR-122)
            try:
                os.chmod(global_settings_path, 0o600)
            except OSError:
                pass

            hook_count = sum(len(v) for v in merged.get("hooks", {}).values())
            synced.append(f"settings({hook_count} hook events)")

            # Validate: every hook command's .py file must exist in ~/.claude/hooks/.
            # When a branch adds a hook + settings entry, then the branch is merged
            # and a new session starts on main, settings.json may reference a hook
            # file that hasn't been synced yet (stale settings from prior branch
            # session). Detect and warn about missing files.
            hooks_dir = user_claude / "hooks"
            missing_hooks = []
            for _evt, hook_list in merged.get("hooks", {}).items():
                for entry in hook_list:
                    for hook_item in entry.get("hooks", [entry]):
                        cmd = hook_item.get("command", "")
                        # Extract .py file path from command string
                        if ".claude/hooks/" in cmd:
                            # Handle both "$HOME/.claude/hooks/X.py" and quoted variants
                            py_file = cmd.split(".claude/hooks/")[-1].strip().strip('"').strip("'")
                            hook_path = hooks_dir / py_file
                            if py_file and not hook_path.exists():
                                missing_hooks.append(py_file)
            if missing_hooks:
                print(
                    f"[sync] WARNING: {len(missing_hooks)} hook(s) registered in settings.json "
                    f"but missing from ~/.claude/hooks/: {', '.join(missing_hooks)}",  # security-review: ignore — false positive: "from" in a stderr warning, no SQL
                    file=sys.stderr,
                )
                # Attempt emergency copy from repo hooks/ for any missing files.
                # First, ensure hooks_dir is a usable directory — it may be a
                # broken symlink (target repo was renamed/moved) which causes
                # mkdir(exist_ok=True) to raise FileExistsError.
                if hooks_dir.is_symlink() and not hooks_dir.exists():
                    hooks_dir.unlink()  # Remove broken symlink
                    print("[sync] Removed broken hooks symlink", file=sys.stderr)
                _tolerant_mkdir(hooks_dir)
                for py_file in missing_hooks:
                    repo_hook = repo_root / "hooks" / py_file
                    if repo_hook.exists():
                        target = hooks_dir / py_file
                        _tolerant_mkdir(target.parent)
                        shutil.copy2(repo_hook, target)
                        print(f"[sync] Emergency copy: hooks/{py_file} -> {target}", file=sys.stderr)
        except Exception as e:
            errors.append(f"settings.json: {e}")

    # Merge .mcp.json (MCP server config)
    repo_mcp_path = repo_root / ".mcp.json"
    global_mcp_path = user_claude.parent / ".mcp.json"  # ~/.mcp.json (not inside .claude/)

    if repo_mcp_path.exists():
        try:
            with open(repo_mcp_path) as f:
                repo_mcp = json.load(f)

            global_mcp = {}
            if global_mcp_path.exists():
                try:
                    content = global_mcp_path.read_text().strip()
                    if content:
                        global_mcp = json.loads(content)
                except json.JSONDecodeError:
                    pass  # Invalid JSON, start fresh

            # Merge: add repo MCP servers without overwriting existing ones
            repo_servers = repo_mcp.get("mcpServers", {})
            global_servers = global_mcp.get("mcpServers", {})
            merged_servers = {**global_servers}  # Start with existing
            for name, config in repo_servers.items():
                if name not in merged_servers:
                    merged_servers[name] = config

            global_mcp["mcpServers"] = merged_servers

            _atomic_json_write(Path(global_mcp_path), global_mcp)
            # Harden permissions after write (ADR-122)
            try:
                os.chmod(global_mcp_path, 0o600)
            except OSError:
                pass

            new_servers = [n for n in repo_servers if n not in global_servers]
            if new_servers:
                synced.append(f"mcp(+{', '.join(new_servers)})")
            else:
                synced.append(f"mcp({len(merged_servers)} servers)")
        except Exception as e:
            errors.append(f".mcp.json: {e}")

    # Sync private skills: ~/private-skills/{category}/{name}/ -> ~/.claude/skills/{deploy-name}/
    # Private skills live in a sibling directory to the repo (~/private-skills),
    # organized the same way as skills/ — nested category/skill/SKILL.md.
    # Voice category skills deploy as voice-{name}; other categories deploy as {name}.
    # Voice data profiles (profile.json + samples, no SKILL.md) are also deployed
    # because create-voice and voice-writer read them at runtime by path.
    private_skills_dir = repo_root.parent / "private-skills"
    if private_skills_dir.is_dir():
        private_count = 0
        skills_base = user_claude / "skills"
        for category_dir in sorted(private_skills_dir.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith("."):
                continue
            category = category_dir.name
            for skill_dir in sorted(category_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                # Voice category: deploy all dirs (skills + data profiles)
                # Other categories: require SKILL.md
                if category != "voice" and not (skill_dir / "SKILL.md").exists():
                    continue
                # Determine deployed name: voice category gets voice- prefix
                if category == "voice":
                    deploy_name = f"voice-{skill_dir.name}"
                else:
                    deploy_name = skill_dir.name
                skill_dst = skills_base / deploy_name
                try:
                    if install_mode == "symlink":
                        _ensure_symlink(skill_dir, skill_dst)
                    else:
                        _tolerant_mkdir(skill_dst)
                        for item in skill_dir.rglob("*"):
                            if item.is_file():
                                rel = item.relative_to(skill_dir)
                                target = skill_dst / rel
                                _tolerant_mkdir(target.parent)
                                if target.exists() and filecmp.cmp(item, target, shallow=False):
                                    continue
                                shutil.copy2(item, target)
                    private_count += 1
                except Exception as e:
                    errors.append(f"private-{deploy_name}: {e}")
        if private_count > 0:
            synced.append(f"private-skills({private_count})")

    # Sync skills and agents to ~/.codex/ for OpenAI Codex CLI.
    # Codex natively supports skills; agents are mirrored as reference
    # material so Codex sessions can Read the same domain expertise that
    # Claude Code sessions dispatch via subagent_type.
    codex_skills_dst = Path.home() / ".codex" / "skills"
    codex_count = 0
    repo_skills = repo_root / "skills"
    if repo_skills.is_dir():
        try:
            _tolerant_mkdir(codex_skills_dst)
            # Copy skills flat (same as ~/.claude/skills deployment).
            # The repo uses nested category folders but Codex needs flat.
            for child in sorted(repo_skills.iterdir()):
                if child.is_file():
                    # Root files: INDEX.json, README.md, etc.
                    target = codex_skills_dst / child.name
                    if target.exists() and filecmp.cmp(child, target, shallow=False):
                        continue
                    shutil.copy2(child, target)
                    codex_count += 1
                elif child.is_dir() and _is_support_dir(child):
                    # Utility dirs: copy directly
                    for item in child.rglob("*"):
                        if item.is_file():
                            rel = item.relative_to(repo_skills)
                            target = codex_skills_dst / rel
                            _tolerant_mkdir(target.parent)
                            if target.exists() and filecmp.cmp(item, target, shallow=False):
                                continue
                            shutil.copy2(item, target)
                            codex_count += 1
                elif child.is_dir() and not child.name.startswith("."):
                    # Category folder: copy each skill inside as a flat entry
                    for skill_dir in sorted(child.iterdir()):
                        if not skill_dir.is_dir():
                            continue
                        if _has_promoted_to(skill_dir, skills_root=repo_skills):
                            continue  # Folded into parent; skip mirror
                        for item in skill_dir.rglob("*"):
                            if item.is_file():
                                # Flatten: category/skill-name/SKILL.md → ~/.codex/skills/skill-name/SKILL.md
                                rel = item.relative_to(skill_dir)
                                target = codex_skills_dst / skill_dir.name / rel
                                _tolerant_mkdir(target.parent)
                                if target.exists() and filecmp.cmp(item, target, shallow=False):
                                    continue
                                shutil.copy2(item, target)
                                codex_count += 1
        except Exception as e:
            errors.append(f"codex-skills: {e}")
    # Also sync private skills to Codex (same category pattern as ~/.claude/skills)
    if private_skills_dir.is_dir():
        for category_dir in sorted(private_skills_dir.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith("."):
                continue
            category = category_dir.name
            for skill_dir in sorted(category_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                if not (skill_dir / "SKILL.md").exists():
                    continue
                if category == "voice":
                    deploy_name = f"voice-{skill_dir.name}"
                else:
                    deploy_name = skill_dir.name
                codex_skill_dst = codex_skills_dst / deploy_name
                try:
                    _tolerant_mkdir(codex_skill_dst)
                    for item in skill_dir.rglob("*"):
                        if item.is_file():
                            rel = item.relative_to(skill_dir)
                            target = codex_skill_dst / rel
                            _tolerant_mkdir(target.parent)
                            if target.exists() and filecmp.cmp(item, target, shallow=False):
                                continue
                            shutil.copy2(item, target)
                            codex_count += 1
                except Exception as e:
                    errors.append(f"codex-private-{deploy_name}: {e}")
    # No stale cleanup for Codex — additive only. Users or Codex itself may
    # create skills in ~/.codex/skills/ that we don't own. We only copy ours in;
    # we never delete theirs.
    if codex_count > 0:
        synced.append(f".codex/skills({codex_count} updated)")
    elif codex_skills_dst.is_dir():
        total = sum(1 for _ in codex_skills_dst.rglob("*") if _.is_file())
        synced.append(f".codex/skills({total} current)")

    # Sync agents to ~/.codex/agents/ — parallel mirror to skills.
    # Agents carry domain expertise (Go, Python, K8s, TypeScript, etc.)
    # and their reference subdirectories. Codex can Read them even though
    # it has no native subagent_type dispatch.
    codex_agents_dst = Path.home() / ".codex" / "agents"
    codex_agent_sources = [("agents", repo_root / "agents")]
    private_agents_dir = repo_root / "private-agents"
    if private_agents_dir.is_dir():
        codex_agent_sources.append(("private-agents", private_agents_dir))
    codex_agent_count = 0
    for label, src in codex_agent_sources:
        if not src.is_dir():
            continue
        try:
            _tolerant_mkdir(codex_agents_dst)
            for item in src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(src)
                    target = codex_agents_dst / rel
                    _tolerant_mkdir(target.parent)
                    if target.exists() and filecmp.cmp(item, target, shallow=False):
                        continue
                    shutil.copy2(item, target)
                    codex_agent_count += 1
        except Exception as e:
            errors.append(f"codex-{label}: {e}")
    # No stale cleanup for Codex agents — additive only, same rationale as skills.
    if codex_agent_count > 0:
        synced.append(f".codex/agents({codex_agent_count} updated)")
    elif codex_agents_dst.is_dir():
        total = sum(1 for _ in codex_agents_dst.rglob("*") if _.is_file())
        synced.append(f".codex/agents({total} current)")

    # Output for hook feedback
    if synced:
        print(f"[sync] Updated ~/.claude: {', '.join(synced)}")
    if errors:
        print(f"[sync] Errors: {', '.join(errors)}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("sync-to-user-claude", e)
    finally:
        sys.exit(0)
