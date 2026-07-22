""" Posts a review comment onto a pull request via the GitHub API. """
from requests import post


def post_comment(repo: str, pr_number: int, github_token: str, body: str) -> None:
    """
        Post a comment on the given pull request's conversation tab.

        Args:
            repo         (str): Repository in 'owner/name' format.
            pr_number    (int): Pull request number.
            github_token (str): Token used to authenticate against the GitHub API.
            body         (str): Markdown-formatted comment body to post.
    """
    url = f'https://api.github.com/repos/{repo}/issues/{pr_number}/comments'
    headers = {
        'Authorization': f'Bearer {github_token}',
        'Accept': 'application/vnd.github+json'
    }

    response = post(url, headers=headers, json={'body': body}, timeout=30)
    response.raise_for_status()
