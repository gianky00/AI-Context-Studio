# -*- coding: utf-8 -*-
"""Helpers to keep generated files inside an intended directory."""

from __future__ import annotations

from pathlib import Path

_WINDOWS_RESERVED_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
)


def resolve_contained_file(base_dir: Path, filename: str) -> Path:
    """Join ``filename`` under ``base_dir`` without leaving that directory.

    Only a single path component is allowed (e.g. ``AI_ARCHITECTURE.md``).
    Absolute paths, ``..``, nested relative paths, drive prefixes,
    trailing spaces or dots, and Windows reserved device names (``NUL``,
    ``CON``, ``COM1``–``COM9``, ``LPT1``–``LPT9``, and so on) are rejected
    so a document name cannot write outside ``docs/`` or hit a device.

    Args:
        base_dir: Intended destination directory.
        filename: Output file name (basename only).

    Returns:
        Resolved path inside ``base_dir``.

    Raises:
        ValueError: If ``filename`` is empty, not a basename, a reserved
            Windows device name, ends with a space or ``.``, or would
            resolve outside ``base_dir``.
    """
    if not filename or not str(filename).strip():
        raise ValueError("empty filename")

    raw = str(filename).strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise ValueError("filename must be a single path component")
    if raw.endswith(("/", "\\")):
        raise ValueError("filename must be a file")
    if raw.endswith(".") or str(filename).endswith(" "):
        raise ValueError("filename must be a file")
    if ":" in raw:
        raise ValueError("absolute or drive-prefixed path not allowed")

    name = Path(raw)
    if name.is_absolute() or bool(name.anchor):
        raise ValueError("absolute path not allowed")

    parts = name.parts
    if len(parts) != 1 or parts[0] in (".", ".."):
        raise ValueError("filename must be a single path component")
    if Path(parts[0]).stem.upper() in _WINDOWS_RESERVED_STEMS:
        raise ValueError("reserved Windows device name")

    base = base_dir.resolve()
    candidate = (base / parts[0]).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("path escapes destination directory") from exc

    if candidate == base:
        raise ValueError("filename must be a file")

    return candidate


def is_path_inside(path: Path, root: Path) -> bool:
    """Return True if ``path`` resolves strictly inside or equal to ``root``."""
    try:
        resolved = path.resolve()
        base = root.resolve()
    except OSError:
        return False
    try:
        resolved.relative_to(base)
    except ValueError:
        return False
    return True
