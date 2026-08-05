"""Abstract Git Provider Interface.

Defines the contract for interacting with remote Git providers
(GitHub, GitLab, Bitbucket, Azure DevOps) via async REST APIs.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class GitRepositoryInfo(BaseModel):
    id: str
    name: str
    full_name: str
    owner: str
    private: bool
    html_url: str
    clone_url: str
    default_branch: str = "main"
    description: str | None = None
    language: str | None = None
    updated_at: str | None = None


class GitBranchInfo(BaseModel):
    name: str
    commit_sha: str
    is_default: bool = False


class GitCommitInfo(BaseModel):
    sha: str
    short_sha: str
    message: str
    author_name: str
    author_email: str
    committed_date: str


class GitPullRequestInfo(BaseModel):
    id: int
    title: str
    number: int
    state: str
    head_ref: str
    base_ref: str
    user: str
    html_url: str
    created_at: str


class GitProvider(ABC):
    """Base abstract interface for Git platform adapters."""

    @abstractmethod
    async def get_user_profile(self, token: str) -> dict:
        """Validate token and return current user profile."""
        raise NotImplementedError

    @abstractmethod
    async def list_repositories(self, token: str, query: str | None = None) -> list[GitRepositoryInfo]:
        """List repositories accessible to the user token."""
        raise NotImplementedError

    @abstractmethod
    async def list_branches(self, token: str, owner: str, repo: str) -> list[GitBranchInfo]:
        """List branches for a given repository."""
        raise NotImplementedError

    @abstractmethod
    async def list_commits(self, token: str, owner: str, repo: str, branch: str = "main", limit: int = 30) -> list[GitCommitInfo]:
        """List recent commits on a branch."""
        raise NotImplementedError

    @abstractmethod
    async def list_pull_requests(self, token: str, owner: str, repo: str) -> list[GitPullRequestInfo]:
        """List active pull requests for a repository."""
        raise NotImplementedError

    @abstractmethod
    async def compare_commits(self, token: str, owner: str, repo: str, base_ref: str, head_ref: str) -> dict:
        """Compare diff between base and head refs."""
        raise NotImplementedError
