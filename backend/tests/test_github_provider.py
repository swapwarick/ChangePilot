from app.providers.git.github import GitHubGitProvider
from app.services.git_cli import GitCLIManager


def test_github_provider_headers():
    provider = GitHubGitProvider()

    # Test fine-grained PAT (github_pat_...)
    headers = provider._headers("github_pat_11AAAAAAA_xxxxxx")
    assert headers["Authorization"] == "Bearer github_pat_11AAAAAAA_xxxxxx"

    # Test classic PAT (ghp_...)
    headers = provider._headers("ghp_1234567890abcdef")
    assert headers["Authorization"] == "Bearer ghp_1234567890abcdef"

    # Test token with Bearer prefix
    headers = provider._headers("Bearer github_pat_11AAAAAAA_xxxxxx")
    assert headers["Authorization"] == "Bearer github_pat_11AAAAAAA_xxxxxx"

    # Test token with token prefix (legacy or user input)
    headers = provider._headers("token ghp_1234567890abcdef")
    assert headers["Authorization"] == "Bearer ghp_1234567890abcdef"

    # Test whitespace trimming
    headers = provider._headers("   bearer  github_pat_11AAAAAAA_xxxxxx   ")
    assert headers["Authorization"] == "Bearer github_pat_11AAAAAAA_xxxxxx"


def test_git_cli_clone_url_with_token():
    cli = GitCLIManager()

    # Test standard clone URL with fine-grained PAT
    url = cli._get_clone_url_with_token("https://github.com/owner/repo.git", "github_pat_11AAAAAAA_xxxxxx")
    assert url == "https://x-access-token:github_pat_11AAAAAAA_xxxxxx@github.com/owner/repo.git"

    # Test token with Bearer prefix
    url = cli._get_clone_url_with_token("https://github.com/owner/repo.git", "Bearer ghp_1234567890abcdef")
    assert url == "https://x-access-token:ghp_1234567890abcdef@github.com/owner/repo.git"

    # Test token with token prefix
    url = cli._get_clone_url_with_token("https://github.com/owner/repo.git", "token ghp_1234567890abcdef")
    assert url == "https://x-access-token:ghp_1234567890abcdef@github.com/owner/repo.git"

    # Test empty or None token
    url_none = cli._get_clone_url_with_token("https://github.com/owner/repo.git", None)
    assert url_none == "https://github.com/owner/repo.git"
    url_empty = cli._get_clone_url_with_token("https://github.com/owner/repo.git", "   ")
    assert url_empty == "https://github.com/owner/repo.git"
