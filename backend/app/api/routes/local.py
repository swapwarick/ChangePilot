"""Local Directory and Repository Scanner Routes.

Allows scanning local folders and local Git repositories directly from disk
without needing GitHub credentials or remote network access.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class LocalBranchInfo(BaseModel):
    name: str
    is_current: bool = False


class LocalCommitInfo(BaseModel):
    sha: str
    short_sha: str
    message: str
    author: str
    date: str


class LocalRepoInfoResponse(BaseModel):
    valid: bool
    path: str
    name: str
    is_git: bool
    default_branch: str = "main"
    branches: list[LocalBranchInfo] = []
    commits: list[LocalCommitInfo] = []
    file_count: int = 0
    error: str | None = None


def _run_git_local(cwd: Path, args: list[str]) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"git {' '.join(args)} failed")
    return res.stdout.strip()


@router.get("/info", response_model=LocalRepoInfoResponse)
async def get_local_repo_info(path: str = Query(..., description="Absolute local directory path")) -> LocalRepoInfoResponse:
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Path parameter is required.")

    target = Path(path.strip()).resolve()
    if not target.exists():
        return LocalRepoInfoResponse(
            valid=False,
            path=str(target),
            name=target.name,
            is_git=False,
            error=f"Directory does not exist: {target}",
        )

    if not target.is_dir():
        return LocalRepoInfoResponse(
            valid=False,
            path=str(target),
            name=target.name,
            is_git=False,
            error=f"Path is not a directory: {target}",
        )

    is_git = (target / ".git").exists()
    branches: list[LocalBranchInfo] = []
    commits: list[LocalCommitInfo] = []
    default_branch = "main"

    if is_git:
        # Get branches
        try:
            raw_branches = _run_git_local(target, ["branch", "--list"])
            for line in raw_branches.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                is_curr = line_str.startswith("* ")
                b_name = line_str.lstrip("* ").strip()
                branches.append(LocalBranchInfo(name=b_name, is_current=is_curr))
                if is_curr:
                    default_branch = b_name
        except Exception as exc:
            logger.warning("Failed to list local branches for %s: %s", target, exc)

        # Get commits
        try:
            raw_log = _run_git_local(target, ["log", "-n", "15", "--pretty=format:%H|%h|%s|%an|%cr"])
            for line in raw_log.splitlines():
                parts = line.split("|")
                if len(parts) >= 5:
                    commits.append(
                        LocalCommitInfo(
                            sha=parts[0],
                            short_sha=parts[1],
                            message=parts[2],
                            author=parts[3],
                            date=parts[4],
                        )
                    )
        except Exception as exc:
            logger.warning("Failed to list local commits for %s: %s", target, exc)

    # Count source files
    file_count = 0
    ignored_dirs = {".git", "node_modules", ".next", "__pycache__", ".venv", "dist", "build"}
    for p in target.rglob("*"):
        if p.is_file() and not any(part in ignored_dirs for part in p.parts):
            file_count += 1

    return LocalRepoInfoResponse(
        valid=True,
        path=str(target),
        name=target.name,
        is_git=is_git,
        default_branch=default_branch,
        branches=branches,
        commits=commits,
        file_count=file_count,
    )


@router.get("/workspace")
async def get_current_workspace_path() -> dict[str, str]:
    """Returns the current backend project workspace directory path."""
    project_root = Path(__file__).parent.parent.parent.parent.resolve()
    return {"path": str(project_root)}


class DirectoryEntry(BaseModel):
    name: str
    path: str
    is_git: bool = False
    has_children: bool = True


class BrowseResponse(BaseModel):
    current_path: str
    parent_path: str | None
    entries: list[DirectoryEntry]


HIDDEN_PREFIXES = {".", "$"}
SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", ".git", "dist", "build", ".next", ".cache", ".tox"}
MAX_ENTRIES = 200


SYSTEM_IGNORE = {
    "system volume information", "$recycle.bin", "$winreagent",
    "documents and settings", "recovery", "config.msi", "$getcurrent"
}


def _get_windows_drives() -> list[DirectoryEntry]:
    """Get available Windows drive letters using ctypes (instant, no disk I/O)."""
    import ctypes
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
    drives: list[DirectoryEntry] = []
    for i in range(26):
        if bitmask & (1 << i):
            letter = chr(65 + i)
            drives.append(DirectoryEntry(name=f"{letter}:\\", path=f"{letter}:\\"))
    return drives


def _list_directory(path: str) -> BrowseResponse:
    """List subdirectories using fast os.scandir without following symlinks/junctions."""
    clean_path = path.strip()
    if sys.platform == "win32" and len(clean_path) == 2 and clean_path[1] == ":":
        clean_path += "\\"
    target = Path(clean_path).resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Not a valid directory: {path}")

    raw_directories: list[os.DirEntry] = []
    try:
        with os.scandir(str(target)) as scanner:
            for entry in scanner:
                try:
                    name_lower = entry.name.lower()
                    if name_lower in SYSTEM_IGNORE or name_lower in SKIP_DIRS:
                        continue
                    if entry.name and entry.name[0] in HIDDEN_PREFIXES:
                        continue
                    # follow_symlinks=False prevents hanging on Windows junctions / symlinks
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    raw_directories.append(entry)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError) as exc:
        raise ValueError(f"Cannot read directory: {exc}")

    # Sort directory entries safely by name
    raw_directories.sort(key=lambda e: e.name.lower())

    entries: list[DirectoryEntry] = []
    for entry in raw_directories[:MAX_ENTRIES]:
        child_path = Path(entry.path)
        is_git = False
        try:
            git_dir = child_path / ".git"
            is_git = git_dir.is_dir()
        except (PermissionError, OSError):
            is_git = False

        entries.append(DirectoryEntry(
            name=entry.name,
            path=str(child_path),
            is_git=is_git,
        ))

    parent = str(target.parent) if target.parent != target else ("" if sys.platform == "win32" else None)
    return BrowseResponse(current_path=str(target), parent_path=parent, entries=entries)


def _search_directories(query: str, root: str | None) -> list[DirectoryEntry]:
    """Search for directories matching query up to 3 levels deep (runs in thread pool)."""
    results: list[DirectoryEntry] = []
    if root and root.strip():
        clean_root = root.strip()
        if sys.platform == "win32" and len(clean_root) == 2 and clean_root[1] == ":":
            clean_root += "\\"
        search_root = Path(clean_root).resolve()
    else:
        search_root = Path.home()
    query_lower = query.lower().strip()
    if not query_lower:
        return []

    try:
        base_depth = len(search_root.parts)
        for root_dir, dirs, _ in os.walk(str(search_root), topdown=True, followlinks=False):
            current_path = Path(root_dir)
            current_depth = len(current_path.parts) - base_depth
            if current_depth >= 3:
                dirs.clear()
                continue

            dirs[:] = [
                d for d in dirs
                if d.lower() not in SKIP_DIRS
                and d.lower() not in SYSTEM_IGNORE
                and (not d or d[0] not in HIDDEN_PREFIXES)
            ]

            for d in dirs:
                if len(results) >= 20:
                    dirs.clear()
                    break
                if query_lower in d.lower():
                    dir_path = current_path / d
                    try:
                        is_git = (dir_path / ".git").is_dir()
                    except (PermissionError, OSError):
                        is_git = False
                    results.append(DirectoryEntry(
                        name=d,
                        path=str(dir_path),
                        is_git=is_git,
                    ))
    except Exception as exc:
        logger.warning("Search failed: %s", exc)

    return results


@router.get("/browse", response_model=BrowseResponse)
async def browse_directory(path: str | None = Query(None, description="Directory to browse")) -> BrowseResponse:
    """List subdirectories of the given path for the folder browser UI."""
    import asyncio
    import sys

    if not path:
        if sys.platform == "win32":
            return BrowseResponse(current_path="", parent_path=None, entries=_get_windows_drives())
        path = "/"

    try:
        return await asyncio.to_thread(_list_directory, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/search", response_model=list[DirectoryEntry])
async def search_directories(
    query: str = Query(..., description="Folder name to search for"),
    root: str | None = Query(None, description="Root path to search under"),
) -> list[DirectoryEntry]:
    """Search for directories matching the query under a given root path."""
    import asyncio
    return await asyncio.to_thread(_search_directories, query, root)

