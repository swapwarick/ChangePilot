"""GitHub API Routes.

Exposes REST endpoints for authenticating GitHub user tokens, listing live GitHub repositories,
branches, commits, and pull requests.
"""

from fastapi import APIRouter, Header, HTTPException

from app.providers.git.github import GitHubGitProvider

router = APIRouter()
github_provider = GitHubGitProvider()


def _get_token(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.strip():
        raise HTTPException(status_code=401, detail="Missing Authorization header (Provide GitHub token)")
    return authorization.strip()


@router.get("/user")
async def get_github_user(authorization: str | None = Header(None)):
    token = _get_token(authorization)
    return await github_provider.get_user_profile(token)


@router.get("/repositories")
async def list_user_repositories(query: str | None = None, authorization: str | None = Header(None)):
    token = _get_token(authorization)
    return await github_provider.list_repositories(token, query=query)


@router.get("/repositories/{owner}/{repo}/branches")
async def list_repository_branches(owner: str, repo: str, authorization: str | None = Header(None)):
    token = _get_token(authorization)
    return await github_provider.list_branches(token, owner=owner, repo=repo)


@router.get("/repositories/{owner}/{repo}/commits")
async def list_repository_commits(
    owner: str, repo: str, branch: str = "main", limit: int = 30, authorization: str | None = Header(None)
):
    token = _get_token(authorization)
    return await github_provider.list_commits(token, owner=owner, repo=repo, branch=branch, limit=limit)


@router.get("/repositories/{owner}/{repo}/pulls")
async def list_repository_pull_requests(owner: str, repo: str, authorization: str | None = Header(None)):
    token = _get_token(authorization)
    return await github_provider.list_pull_requests(token, owner=owner, repo=repo)


@router.get("/repositories/{owner}/{repo}/compare")
async def compare_repository_commits(
    owner: str, repo: str, base: str, head: str, authorization: str | None = Header(None)
):
    token = _get_token(authorization)
    return await github_provider.compare_commits(token, owner=owner, repo=repo, base_ref=base, head_ref=head)
