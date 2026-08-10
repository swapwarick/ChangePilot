"""Unified diff parser and git-ref validator for change analysis.

Parses ``git diff --unified=0`` output into a mapping of file paths to
changed line ranges, then correlates those ranges with AST symbol positions
to identify which specific functions and classes were modified.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Git ref safety
# ---------------------------------------------------------------------------

# Allowlist pattern: letters, digits, and safe git ref characters only.
# Rejects shell metacharacters, path traversal sequences, and injection attempts.
_SAFE_GIT_REF = re.compile(r"^[A-Za-z0-9_.~^/@{}\-]+$")

# Default subprocess timeout for git commands (seconds, can be overridden via env).
import os
_GIT_TIMEOUT = int(os.environ.get("CHANGEPILOT_GIT_TIMEOUT", "30"))


def is_safe_git_ref(ref: str) -> bool:
    """Return True if *ref* contains only safe git ref characters.

    Rejects empty strings, shell metacharacters (``$``, `` ` ``, ``|``, etc.),
    path traversal sequences (``..``), and any ref that does not match the
    allowlist pattern.
    """
    if not ref or ".." in ref:
        return False
    return bool(_SAFE_GIT_REF.match(ref))


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ChangedLineRange:
    """A single contiguous range of added/changed lines in a file."""
    start: int  # 1-indexed, inclusive
    end: int    # 1-indexed, inclusive


@dataclass
class FileLineDiff:
    """All changed line ranges for a single file in a diff."""
    file_path: str
    ranges: list[ChangedLineRange] = field(default_factory=list)

    def contains_line(self, line: int) -> bool:
        """Return True if *line* falls within any changed range."""
        return any(r.start <= line <= r.end for r in self.ranges)


@dataclass
class AffectedSymbol:
    """A function or class whose definition overlaps a changed line range."""
    name: str
    kind: str        # 'function' | 'class'
    file_path: str
    start_line: int
    end_line: int


# ---------------------------------------------------------------------------
# Core diff parsing
# ---------------------------------------------------------------------------

def parse_unified_diff(diff_text: str) -> dict[str, FileLineDiff]:
    """Parse unified diff text into a mapping of file path → :class:`FileLineDiff`.

    Handles the ``@@ -old,count +new,count @@`` hunk header format produced by
    ``git diff --unified=0``.  Pure-deletion hunks (count = 0) are recorded at
    the boundary line so downstream callers can still identify the neighbourhood.

    Args:
        diff_text: Raw text output of ``git diff --unified=0``.

    Returns:
        Mapping of relative file path → :class:`FileLineDiff` containing all
        added/modified line ranges for that file.
    """
    result: dict[str, FileLineDiff] = {}
    current_file: str | None = None

    # "+++ b/path/to/file"
    file_pattern = re.compile(r"^\+\+\+ b/(.+)$")
    # "@@ ... +start,count @@" or "@@ ... +start @@"
    hunk_pattern = re.compile(r"^@@ .+? \+(\d+)(?:,(\d+))? @@")

    for line in diff_text.splitlines():
        file_match = file_pattern.match(line)
        if file_match:
            current_file = file_match.group(1).strip()
            if current_file not in result:
                result[current_file] = FileLineDiff(file_path=current_file)
            continue

        hunk_match = hunk_pattern.match(line)
        if hunk_match and current_file is not None:
            start = int(hunk_match.group(1))
            count = int(hunk_match.group(2)) if hunk_match.group(2) is not None else 1
            # Pure deletion hunk: count == 0 means no lines added, but
            # record the boundary position for neighbourhood context.
            end = start if count == 0 else start + count - 1
            result[current_file].ranges.append(ChangedLineRange(start=start, end=end))

    return result


def fetch_unified_diff(repo_root: str, base_ref: str = "HEAD~1") -> dict[str, FileLineDiff]:
    """Run ``git diff --unified=0`` and return parsed line ranges per file.

    Args:
        repo_root: Absolute path to the git repository root.
        base_ref:  Git ref to diff against.  Validated before use.

    Returns:
        Mapping of relative file path → :class:`FileLineDiff`.
        Returns an empty dict when the ref is unsafe, git is unavailable,
        or the command exits non-zero.
    """
    if not is_safe_git_ref(base_ref):
        logger.warning("Unsafe git ref rejected: %r", base_ref)
        return {}

    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", base_ref, "--"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_root,
            timeout=_GIT_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning(
                "git diff exited %d: %s",
                result.returncode,
                result.stderr[:300],
            )
            return {}
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git diff subprocess error: %s", exc)
        return {}

    return parse_unified_diff(result.stdout)


# ---------------------------------------------------------------------------
# Symbol correlation — maps line ranges to AST symbols
# ---------------------------------------------------------------------------

def find_affected_symbols(
    file_line_diffs: dict[str, FileLineDiff],
    parsed_files: list,  # list[ParsedFileAST]
) -> list[AffectedSymbol]:
    """Identify which functions and classes overlap changed line ranges.

    Cross-references the line ranges in *file_line_diffs* with the symbol
    position information stored in ``ParsedFileAST`` objects.  A symbol is
    considered *affected* when at least one of its body lines falls inside a
    changed range.

    Note:
        Tree-sitter nodes expose ``start_point`` and ``end_point`` tuples
        (row, col) indexed from 0, so ``start_point[0] + 1`` converts to the
        1-indexed line numbers used in unified diffs.

    Args:
        file_line_diffs: Output of :func:`parse_unified_diff`.
        parsed_files:    List of ``ParsedFileAST`` instances from the AST parser.

    Returns:
        Deduplicated list of :class:`AffectedSymbol` instances ordered by
        file path then symbol start line.
    """
    affected: list[AffectedSymbol] = []
    seen: set[tuple[str, str]] = set()

    for pf in parsed_files:
        diff = file_line_diffs.get(pf.file_path)
        if diff is None:
            continue

        # Function symbols
        for fn in getattr(pf, "function_symbols", []):
            start = getattr(fn, "start_line", 0)
            end = getattr(fn, "end_line", start)
            if start and any(diff.contains_line(ln) for ln in range(start, end + 1)):
                key = (pf.file_path, fn.name)
                if key not in seen:
                    seen.add(key)
                    affected.append(
                        AffectedSymbol(
                            name=fn.name,
                            kind="function",
                            file_path=pf.file_path,
                            start_line=start,
                            end_line=end,
                        )
                    )

        # Class symbols
        for cls in getattr(pf, "class_symbols", []):
            start = getattr(cls, "start_line", 0)
            end = getattr(cls, "end_line", start)
            if start and any(diff.contains_line(ln) for ln in range(start, end + 1)):
                key = (pf.file_path, cls.name)
                if key not in seen:
                    seen.add(key)
                    affected.append(
                        AffectedSymbol(
                            name=cls.name,
                            kind="class",
                            file_path=pf.file_path,
                            start_line=start,
                            end_line=end,
                        )
                    )

    affected.sort(key=lambda s: (s.file_path, s.start_line))
    return affected
