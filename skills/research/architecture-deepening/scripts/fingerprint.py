"""Canonical identity operations owned by architecture-deepening."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import quote, unquote

BURDEN_KINDS = (
    "leaked-dependency",
    "repeated-configuration",
    "duplicated-coordination",
    "source-knowledge",
    "temporal-ordering",
    "error-leak",
)
SAFE_PATH = re.compile(
    r"^(?!.*(?:^|/)\.{1,2}(?:/|$))[A-Za-z0-9_.][A-Za-z0-9._-]*"
    r"(?:/[A-Za-z0-9_.][A-Za-z0-9._-]*)*$"
)


def _module_path(value: str) -> str:
    if not isinstance(value, str) or not value or not value.isascii() or not value.isprintable():
        raise ValueError("module must be a printable ASCII repository-relative path")
    if not SAFE_PATH.fullmatch(value):
        raise ValueError("module must be a safe repository-relative path")
    return value


def canonical_fingerprint(module: str, symbol: str, burden_kind: str) -> str:
    """Return a stable v1 architecture fingerprint."""
    clean_module = _module_path(module.strip())
    clean_symbol = symbol.strip()
    if not clean_symbol:
        raise ValueError("symbol must be non-empty; use '<module>' for a module boundary")
    if not clean_symbol.isascii() or not clean_symbol.isprintable():
        raise ValueError("symbol must use printable ASCII")
    if burden_kind not in BURDEN_KINDS:
        raise ValueError(f"burden kind must be one of: {', '.join(BURDEN_KINDS)}")
    module_part = quote(str(PurePosixPath(clean_module)), safe="/._-")
    symbol_part = quote(clean_symbol, safe="._-<>")
    return f"arch:v1:{module_part}::{symbol_part}::{burden_kind}"


def parse_fingerprint(fingerprint: str) -> tuple[str, str, str]:
    """Decode and round-trip one canonical v1 architecture fingerprint."""
    parts = fingerprint.split("::")
    if len(parts) != 3 or not parts[0].startswith("arch:v1:"):
        raise ValueError("fingerprint is not a canonical architecture identity")
    module, symbol, burden_kind = parts[0][len("arch:v1:") :], parts[1], parts[2]
    try:
        decoded_module = unquote(module)
        decoded_symbol = unquote(symbol)
        rebuilt = canonical_fingerprint(decoded_module, decoded_symbol, burden_kind)
    except ValueError as exc:
        raise ValueError("fingerprint is not a canonical architecture identity") from exc
    if rebuilt != fingerprint:
        raise ValueError("fingerprint is not a canonical architecture identity")
    return decoded_module, decoded_symbol, burden_kind


def is_canonical_fingerprint(fingerprint: str) -> bool:
    """Return whether a fingerprint round-trips through the v1 canonicalizer."""
    try:
        parse_fingerprint(fingerprint)
    except ValueError:
        return False
    return True
