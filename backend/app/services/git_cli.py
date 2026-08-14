"""Native Git CLI Subprocess Manager.

Manages bare git repository clones (`storage/repos/{owner}/{repo}.git`) and
zero-copy git worktree checkouts for high-performance diff extraction and file scanning.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Git ref safety — rejects shell metacharacters and path traversal sequences
# ---------------------------------------------------------------------------

# Allowlist: letters, digits, and characters with defined meaning in git refs.
# Anything not in this set (e.g. $ ; | ` & > < !) is rejected before any
# subprocess call.
_SAFE_GIT_REF = re.compile(r"^[A-Za-z0-9_.~^/@{}\-]+$")

# The SHA of git's canonical empty tree — used as base when diffing a root commit.
_EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _validate_git_ref(ref: str, context: str = "git ref") -> str:
    """Return *ref* unchanged if it is safe; raise ValueError otherwise."""
    if not ref:
        raise ValueError(f"Invalid {context}: empty ref")
    # Reject path-traversal sequences like ../../ but allow single .. in range refs
    # (those are joined *outside* this function, so individual refs should not contain ..)
    if ".." in ref:
        raise ValueError(f"Invalid {context}: contains '..': {ref!r}")
    if not _SAFE_GIT_REF.match(ref):
        raise ValueError(
            f"Invalid {context} — contains disallowed characters: {ref!r}. "
            "Only alphanumeric characters and _.~^/@{}- are permitted."
        )
    return ref



@dataclass
class FileDiff:
    filename: str
    status: str  # 'added', 'modified', 'deleted', 'renamed'
    previous_filename: str | None = None


@dataclass
class GitDiffResult:
    base_ref: str
    head_ref: str
    files: list[FileDiff] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)


class GitCLIManager:
    def __init__(self, base_storage_dir: Path | None = None) -> None:
        if base_storage_dir is None:
            base_storage_dir = Path(__file__).parent.parent.parent / "storage"
        self.storage_dir = base_storage_dir.resolve()
        self.repos_dir = self.storage_dir / "repos"
        self.worktrees_dir = self.storage_dir / "worktrees"
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    async def _run_git(self, cwd: Path | None, args: list[str], env: dict[str, str] | None = None) -> str:
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        full_env["GIT_TERMINAL_PROMPT"] = "0"

        def _exec():
            return subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                env=full_env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        res = await asyncio.to_thread(_exec)

        if res.returncode != 0:
            err_msg = res.stderr.strip()
            raise HTTPException(
                status_code=400,
                detail=f"Git command failed (exit code {res.returncode}): git {' '.join(args)}\nError: {err_msg}",
            )
        return res.stdout.strip()

    def _get_clone_url_with_token(self, clone_url: str, token: str | None) -> str:
        if not token or not token.strip():
            return clone_url
        clean_token = token.strip()
        for prefix in ("bearer ", "token "):
            if clean_token.lower().startswith(prefix):
                clean_token = clean_token[len(prefix):].strip()
                break
        if not clean_token:
            return clone_url

        parsed = urllib.parse.urlparse(clone_url)
        if parsed.scheme in ("https", "http"):
            host = parsed.netloc.split("@")[-1]
            new_netloc = f"x-access-token:{clean_token}@{host}"
            return urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))
        return clone_url

    @staticmethod
    def _force_remove_dir(target_dir: Path) -> None:
        """Forcefully removes directory tree by clearing read-only attributes on Windows.

        Retries up to 3 times with a short delay to handle Windows file locking
        (e.g., .git/objects/pack files held by background processes).
        """
        if not target_dir.exists():
            return

        def _handle_readonly(func: any, path: str, exc: any) -> None:
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:  # noqa: BLE001
                pass

        import time

        for attempt in range(3):
            try:
                shutil.rmtree(target_dir, onerror=_handle_readonly)
            except Exception:  # noqa: BLE001
                shutil.rmtree(target_dir, ignore_errors=True)

            if not target_dir.exists():
                return  # Successfully removed

            if attempt < 2:
                logger.debug("Directory still exists after removal attempt %d, retrying in 0.5s...", attempt + 1)
                time.sleep(0.5)

        # Final check — log a warning if we couldn't fully remove it
        if target_dir.exists():
            logger.warning("Could not fully remove directory after 3 attempts: %s", target_dir)

    @staticmethod
    def _is_local_dir(clone_url: str) -> bool:
        if not clone_url:
            return False
        try:
            p = Path(clone_url.strip()).resolve()
            return p.exists() and p.is_dir()
        except Exception:
            return False

    async def ensure_bare_repo(self, owner: str, repo: str, clone_url: str, token: str | None = None) -> Path:
        """Clones bare repo if not present, otherwise fetches latest changes with automatic recovery."""
        if self._is_local_dir(clone_url):
            local_path = Path(clone_url.strip()).resolve()
            if not (local_path / ".git").exists():
                return local_path
            authed_url = str(local_path)
        else:
            authed_url = self._get_clone_url_with_token(clone_url, token)

        bare_repo_dir = self.repos_dir / owner / f"{repo}.git"

        if bare_repo_dir.exists():
            try:
                # Update remote URL and fetch latest branches
                await self._run_git(bare_repo_dir, ["remote", "set-url", "origin", authed_url])
                await self._run_git(bare_repo_dir, ["fetch", "origin"])
                return bare_repo_dir
            except Exception as exc:
                logger.warning("Git fetch failed (%s). Removing stale bare repo and re-cloning...", exc)
                self._force_remove_dir(bare_repo_dir)

        # Clone fresh bare repository
        bare_repo_dir.parent.mkdir(parents=True, exist_ok=True)
        if bare_repo_dir.exists():
            self._force_remove_dir(bare_repo_dir)

        # Verify directory is actually gone before attempting clone
        if bare_repo_dir.exists():
            raise RuntimeError(
                f"Cannot clone: failed to remove stale directory '{bare_repo_dir}'. "
                f"A background process may be locking files. Please close any git tools and retry."
            )

        await self._run_git(None, ["clone", "--bare", authed_url, str(bare_repo_dir)])
        return bare_repo_dir

    async def checkout_worktree(self, owner: str, repo: str, commit_sha: str, clone_url: str, token: str | None = None) -> Path:
        """Creates a zero-copy git worktree checkout for a specific commit SHA or branch."""
        if self._is_local_dir(clone_url):
            local_path = Path(clone_url.strip()).resolve()
            if not (local_path / ".git").exists():
                return local_path

        bare_repo_dir = await self.ensure_bare_repo(owner, repo, clone_url, token)
        worktree_dir = self.worktrees_dir / owner / repo / commit_sha[:12]

        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        # Prune old worktree references first
        try:
            await self._run_git(bare_repo_dir, ["worktree", "prune"])
        except Exception:  # noqa: BLE001
            pass

        if not worktree_dir.exists():
            try:
                await self._run_git(bare_repo_dir, ["worktree", "add", "-f", str(worktree_dir), commit_sha])
            except Exception as exc:
                logger.warning("Worktree add failed (%s). Retrying with fresh bare repository...", exc)
                self._force_remove_dir(bare_repo_dir)
                bare_repo_dir = await self.ensure_bare_repo(owner, repo, clone_url, token)
                await self._run_git(bare_repo_dir, ["worktree", "add", "-f", str(worktree_dir), commit_sha])

        return worktree_dir

    async def _resolve_base_ref(self, bare_repo_dir: Path, base_ref: str, head_ref: str) -> str:
        """Resolve base_ref to a concrete SHA, falling back to the empty-tree SHA
        when base_ref points to a root commit that has no parent.

        This handles the common ``sha~1`` pattern for initial commits and
        shallow clones where the parent is not present in the local object store.
        """
        try:
            # Attempt to resolve to a real SHA — will fail if ref is unreachable
            return await self._run_git(bare_repo_dir, ["rev-parse", "--verify", base_ref])
        except Exception:  # noqa: BLE001
            pass

        # If base_ref looks like `<sha>~N`, check whether head_ref itself is a
        # root commit (i.e. has no parents).  If so, use the empty-tree SHA so
        # the diff covers all files that were introduced in that first commit.
        try:
            parent_count_out = await self._run_git(
                bare_repo_dir, ["rev-list", "--count", "--parents", head_ref, "--", "--max-count=1"]
            )
            # rev-list --parents prints: "<sha> [<parent-sha> ...]"
            # A root commit line has no parent SHA after the commit SHA.
            parts = parent_count_out.strip().split()
            if len(parts) == 1:
                # Root commit — no parent exists, diff against empty tree
                logger.info(
                    "Base ref %r is unreachable (root commit %s). Diffing against empty tree.",
                    base_ref,
                    head_ref,
                )
                return _EMPTY_TREE_SHA
        except Exception:  # noqa: BLE001
            pass

        # Last resort: raise a clear, human-readable error
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot resolve base ref {base_ref!r}. "
                "For the first commit in a repository, leave base_ref empty or pass the empty-tree "
                f"SHA ({_EMPTY_TREE_SHA}). "
                "For subsequent commits, pass a valid branch name, tag, or commit SHA."
            ),
        )

    async def get_commit_diff(
        self, owner: str, repo: str, base_ref: str, head_ref: str, clone_url: str, token: str | None = None
    ) -> GitDiffResult:
        """Computes exact file diff between base_ref and head_ref using git diff --name-status.

        Handles root commits gracefully: when *base_ref* (e.g. ``sha~1``) cannot be
        resolved because the commit has no parent, the diff is computed against git's
        canonical empty-tree SHA so all files in that commit are reported as *added*.
        """
        if self._is_local_dir(clone_url):
            local_path = Path(clone_url.strip()).resolve()
            if not (local_path / ".git").exists():
                file_diffs: list[FileDiff] = []
                changed_files: list[str] = []
                ignored_dirs = {".git", "node_modules", ".next", "__pycache__", ".venv", "dist", "build"}
                for p in local_path.rglob("*"):
                    if p.is_file() and not any(part in ignored_dirs for part in p.parts):
                        rel = p.relative_to(local_path).as_posix()
                        file_diffs.append(FileDiff(filename=rel, status="added"))
                        changed_files.append(rel)
                return GitDiffResult(base_ref="empty", head_ref="HEAD", files=file_diffs, changed_files=changed_files)

        bare_repo_dir = await self.ensure_bare_repo(owner, repo, clone_url, token)

        resolved_base = await self._resolve_base_ref(bare_repo_dir, base_ref, head_ref)
        raw_diff = await self._run_git(bare_repo_dir, ["diff", "--name-status", f"{resolved_base}..{head_ref}"])

        file_diffs: list[FileDiff] = []
        changed_files: list[str] = []

        for line in raw_diff.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            status_code = parts[0][0]  # A, M, D, R, C

            status = "modified"
            if status_code == "A":
                status = "added"
            elif status_code == "D":
                status = "deleted"
            elif status_code == "R":
                status = "renamed"

            filename = parts[-1]
            prev_filename = parts[1] if status == "renamed" and len(parts) > 2 else None

            file_diffs.append(FileDiff(filename=filename, status=status, previous_filename=prev_filename))
            changed_files.append(filename)

        return GitDiffResult(base_ref=resolved_base, head_ref=head_ref, files=file_diffs, changed_files=changed_files)

    async def cleanup_worktree(self, owner: str, repo: str, commit_sha: str) -> None:
        """Removes a worktree directory."""
        bare_repo_dir = self.repos_dir / owner / f"{repo}.git"
        worktree_dir = self.worktrees_dir / owner / repo / commit_sha[:12]

        if worktree_dir.exists() and worktree_dir.is_relative_to(self.worktrees_dir):
            if bare_repo_dir.exists():
                try:
                    await self._run_git(bare_repo_dir, ["worktree", "remove", "-f", str(worktree_dir)])
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Worktree cleanup notice: %s", exc)
            if worktree_dir.exists():
                shutil.rmtree(worktree_dir, ignore_errors=True)

    async def get_unified_diff(
        self,
        owner: str,
        repo: str,
        base_ref: str,
        head_ref: str,
        clone_url: str,
        token: str | None = None,
    ) -> str:
        """Return the raw ``git diff --unified=0`` output between two refs.

        Both *base_ref* and *head_ref* are validated against the safe-ref
        allowlist before being passed to the subprocess.  The resulting diff
        text can be fed directly into
        :func:`app.analysis.diff_parser.parse_unified_diff` to obtain
        per-file line-range maps.

        Args:
            owner:     Repository owner.
            repo:      Repository name.
            base_ref:  Starting git ref (e.g. ``"HEAD~1"`` or a commit SHA).
            head_ref:  Ending git ref (e.g. ``"HEAD"`` or a commit SHA).
            clone_url: HTTPS clone URL used to ensure the bare repo is up to date.
            token:     Optional authentication token.

        Returns:
            Raw unified diff text.  Returns an empty string if validation fails
            or the refs produce no diff.

        Raises:
            ValueError:    If either ref fails the allowlist check.
            HTTPException: If the underlying git command exits non-zero.
        """
        _validate_git_ref(base_ref, "base_ref")
        _validate_git_ref(head_ref, "head_ref")

        bare_repo_dir = await self.ensure_bare_repo(owner, repo, clone_url, token)
        resolved_base = await self._resolve_base_ref(bare_repo_dir, base_ref, head_ref)
        return await self._run_git(
            bare_repo_dir,
            ["diff", "--unified=0", f"{resolved_base}..{head_ref}"],
        )

