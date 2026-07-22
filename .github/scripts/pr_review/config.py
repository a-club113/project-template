""" Configuration loader for the PR review script. """
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewConfig:
    """ Holds all configuration values required to run a PR review. """
    gemini_api_key: str
    github_token: str
    github_repository: str
    pr_number: int
    max_diff_chars: int = 60000

def load_config() -> ReviewConfig:
    """
        Load configuration from environment variables.

        Returns:
            ReviewConfig: Populated configuration object.

        Raises:
            RuntimeError: If a required environment variable is missing.
    """
    def _require(name: str) -> str:
        value = os.environ.get(name)

        if not value:
            raise RuntimeError(f'[{name}]: Missing required environment variable')

        return value

    return ReviewConfig(
        gemini_api_key=_require('GEMINI_API_KEY'),
        github_token=_require('GITHUB_TOKEN'),
        github_repository=_require('GITHUB_REPOSITORY'),
        pr_number=int(_require('PR_NUMBER'))
    )
