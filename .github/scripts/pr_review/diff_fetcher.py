""" Fetches the unified diff of a pull request from the GitHub API. """
from requests import get


def fetch_pr_diff(repo: str, pr_number: int, github_token: str) -> str:
    """Fetch the diff text of a pull request.

    Args:
        repo: Repository in 'owner/name' format.
        pr_number: Pull request number.
        github_token: Token used to authenticate against the GitHub API.

    Returns:
        str: The unified diff content of the pull request.
    """
    url = f'https://api.github.com/repos/{repo}/pulls/{pr_number}'
    headers = {
        'Authorization': f'Bearer {github_token}',
        'Accept': 'application/vnd.github.v3.diff',
    }
    response = get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.text
