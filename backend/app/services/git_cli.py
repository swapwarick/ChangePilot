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


def _validate_git_ref(ref: str, context: str = "git ref") -> str:
    """Return *ref* unchanged if it is safe; raise ValueError otherwise."""
    if not ref or ".." in ref:
        raise ValueError(f"Invalid {context}: empty or contains '..': {ref!r}")
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

    async def ensure_bare_repo(self, owner: str, repo: str, clone_url: str, token: str | None = None) -> Path:
        """Clones bare repo if not present, otherwise fetches latest changes with automatic recovery."""
        bare_repo_dir = self.repos_dir / owner / f"{repo}.git"
        authed_url = self._get_clone_url_with_token(clone_url, token)

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

    async def get_commit_diff(
        self, owner: str, repo: str, base_ref: str, head_ref: str, clone_url: str, token: str | None = None
    ) -> GitDiffResult:
        """Computes exact file diff between base_ref and head_ref using git diff --name-status."""
        bare_repo_dir = await self.ensure_bare_repo(owner, repo, clone_url, token)
        raw_diff = await self._run_git(bare_repo_dir, ["diff", "--name-status", f"{base_ref}..{head_ref}"])

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

        return GitDiffResult(base_ref=base_ref, head_ref=head_ref, files=file_diffs, changed_files=changed_files)

    async def cleanup_worktree(self, owner: str, repo: str, commit_sha: str) -> None:
        """Removes a worktree directory."""
        bare_repo_dir = self.repos_dir / owner / f"{repo}.git"
        worktree_dir = self.worktrees_dir / owner / repo / commit_sha[:12]

        if worktree_dir.exists():
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
        return await self._run_git(
            bare_repo_dir,
            ["diff", "--unified=0", f"{base_ref}..{head_ref}"],
        )

