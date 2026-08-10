"""GitHub REST API GitProvider Adapter.

Interacts directly with GitHub API v3 using httpx without PyGithub dependency.
Supports both Personal Access Tokens and OAuth access tokens.
"""

from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.providers.git.base import (
    GitBranchInfo,
    GitCommitInfo,
    GitProvider,
    GitPullRequestInfo,
    GitRepositoryInfo,
)


class GitHubGitProvider(GitProvider):
    """GitHub API Adapter implementing GitProvider interface."""

    BASE_URL = "https://api.github.com"

    def _headers(self, token: str) -> dict[str, str]:
        clean_token = token.strip()
        for prefix in ("bearer ", "token "):
            if clean_token.lower().startswith(prefix):
                clean_token = clean_token[len(prefix):].strip()
                break
        return {
            "Authorization": f"Bearer {clean_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ChangePilot-Impact-Analyzer",
        }

    async def get_user_profile(self, token: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{self.BASE_URL}/user", headers=self._headers(token))
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"GitHub Auth Error: {resp.text}")
            data = resp.json()
            return {
                "id": str(data.get("id")),
                "login": data.get("login"),
                "name": data.get("name") or data.get("login"),
                "avatar_url": data.get("avatar_url"),
                "email": data.get("email"),
            }

    async def list_repositories(self, token: str, query: str | None = None) -> list[GitRepositoryInfo]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            url = f"{self.BASE_URL}/user/repos?per_page=100&sort=updated"
            resp = await client.get(url, headers=self._headers(token))
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to list GitHub repositories: {resp.text}")
            
            repos = resp.json()
            results = []
            for item in repos:
                name = item.get("name", "")
                full_name = item.get("full_name", "")
                if query and query.lower() not in name.lower() and query.lower() not in full_name.lower():
                    continue
                results.append(
                    GitRepositoryInfo(
                        id=str(item.get("id")),
                        name=name,
                        full_name=full_name,
                        owner=item.get("owner", {}).get("login", ""),
                        private=item.get("private", False),
                        html_url=item.get("html_url", ""),
                        clone_url=item.get("clone_url", ""),
                        default_branch=item.get("default_branch", "main"),
                        description=item.get("description"),
                        language=item.get("language"),
                        updated_at=item.get("updated_at"),
                    )
                )
            return results

    async def list_branches(self, token: str, owner: str, repo: str) -> list[GitBranchInfo]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/branches?per_page=100"
            resp = await client.get(url, headers=self._headers(token))
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to list branches: {resp.text}")
            
            branches = resp.json()
            return [
                GitBranchInfo(
                    name=b.get("name"),
                    commit_sha=b.get("commit", {}).get("sha", ""),
                )
                for b in branches
            ]

    async def list_commits(
        self, token: str, owner: str, repo: str, branch: str = "main", limit: int = 30
    ) -> list[GitCommitInfo]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits?sha={branch}&per_page={limit}"
            resp = await client.get(url, headers=self._headers(token))
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to list commits: {resp.text}")
            
            commits = resp.json()
            return [
                GitCommitInfo(
                    sha=c.get("sha"),
                    short_sha=c.get("sha", "")[:7],
                    message=c.get("commit", {}).get("message", "").split("\n")[0],
                    author_name=c.get("commit", {}).get("author", {}).get("name", "Unknown"),
                    author_email=c.get("commit", {}).get("author", {}).get("email", ""),
                    committed_date=c.get("commit", {}).get("author", {}).get("date", ""),
                )
                for c in commits
            ]

    async def list_pull_requests(self, token: str, owner: str, repo: str) -> list[GitPullRequestInfo]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls?state=all&per_page=30"
            resp = await client.get(url, headers=self._headers(token))
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to list pull requests: {resp.text}")
            
            prs = resp.json()
            return [
                GitPullRequestInfo(
                    id=pr.get("id"),
                    title=pr.get("title"),
                    number=pr.get("number"),
                    state=pr.get("state"),
                    head_ref=pr.get("head", {}).get("ref"),
                    base_ref=pr.get("base", {}).get("ref"),
                    user=pr.get("user", {}).get("login", ""),
                    html_url=pr.get("html_url", ""),
                    created_at=pr.get("created_at", ""),
                )
                for pr in prs
            ]

    async def compare_commits(self, token: str, owner: str, repo: str, base_ref: str, head_ref: str) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/compare/{base_ref}...{head_ref}"
            resp = await client.get(url, headers=self._headers(token))
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to compare commits: {resp.text}")
            
            data = resp.json()
            files = [
                {
                    "filename": f.get("filename"),
                    "status": f.get("status"),  # added, modified, removed, renamed
                    "additions": f.get("additions"),
                    "deletions": f.get("deletions"),
                    "changes": f.get("changes"),
                    "previous_filename": f.get("previous_filename"),
                }
                for f in data.get("files", [])
            ]
            return {
                "status": data.get("status"),
                "ahead_by": data.get("ahead_by"),
                "behind_by": data.get("behind_by"),
                "total_commits": data.get("total_commits"),
                "files": files,
            }
