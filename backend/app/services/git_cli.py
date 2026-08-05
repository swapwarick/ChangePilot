"""Native Git CLI Subprocess Manager.

Manages bare git repository clones (`storage/repos/{owner}/{repo}.git`) and
zero-copy git worktree checkouts for high-performance diff extraction and file scanning.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)


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

        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise HTTPException(
                status_code=400,
                detail=f"Git command failed (exit code {process.returncode}): git {' '.join(args)}\nError: {err_msg}",
            )
        return stdout.decode("utf-8", errors="replace").strip()

    def _get_clone_url_with_token(self, clone_url: str, token: str | None) -> str:
        if not token:
            return clone_url
        clean_token = token.strip().removeprefix("token ").removeprefix("Bearer ")
        if clone_url.startswith("https://"):
            return clone_url.replace("https://", f"https://x-access-token:{clean_token}@")
        return clone_url

    async def ensure_bare_repo(self, owner: str, repo: str, clone_url: str, token: str | None = None) -> Path:
        """Clones bare repo if not present, otherwise fetches latest changes."""
        bare_repo_dir = self.repos_dir / owner / f"{repo}.git"
        authed_url = self._get_clone_url_with_token(clone_url, token)

        if not bare_repo_dir.exists():
            bare_repo_dir.parent.mkdir(parents=True, exist_ok=True)
            await self._run_git(None, ["clone", "--bare", authed_url, str(bare_repo_dir)])
        else:
            # Update remote URL and fetch all branches/tags
            await self._run_git(bare_repo_dir, ["remote", "set-url", "origin", authed_url])
            await self._run_git(bare_repo_dir, ["fetch", "--all", "--prune"])

        return bare_repo_dir

    async def checkout_worktree(self, owner: str, repo: str, commit_sha: str, clone_url: str, token: str | None = None) -> Path:
        """Creates a zero-copy git worktree checkout for a specific commit SHA or branch."""
        bare_repo_dir = await self.ensure_bare_repo(owner, repo, clone_url, token)
        worktree_dir = self.worktrees_dir / owner / repo / commit_sha[:12]

        if worktree_dir.exists():
            return worktree_dir

        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        # Prune old worktree references first
        await self._run_git(bare_repo_dir, ["worktree", "prune"])
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
