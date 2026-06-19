"""
    Shared utilities for Discord webhook notification scripts.

    Provides common constants, text helpers, and the webhook sender used by both `notify_discord.py` and `notify_github_events.py`.
"""
from logging import INFO, Logger, basicConfig, getLogger
from typing import Final

from discord_webhook import DiscordEmbed, DiscordWebhook

GITHUB_AVATAR_URL: Final[str] = 'https://avatars.githubusercontent.com/u/9919?s=200&v=4'
GITHUB_USERNAME: Final[str] = 'GitHub Event Notification'
LOG_FORMAT: Final[str] = '%(levelname)s\t%(message)s'
EMBED_FIELD_LIMIT: Final[int] = 1000

def get_logger(name: str) -> Logger:
    """
        Configures the root logger and returns a named logger.

        Calls `basicConfig` once to set the shared log format and level.
        Each script should call this with `__name__` to obtain its logger.

        Args:
            name (str): Logger name, typically `__name__` of the calling module.

        Returns:
            Logger: Configured logger instance.
    """
    basicConfig(level=INFO, format=LOG_FORMAT)

    return getLogger(name)

def truncate(text: str, limit: int = EMBED_FIELD_LIMIT) -> str:
    """
        Truncates text to the specified character limit.

        Args:
            text  (str): Input text.
            limit (int): Maximum character count.

        Returns:
            str: Truncated text with ellipsis if needed.
    """
    if len(text) < limit:
        return text

    return text[:limit] + '\n...'

def send_embed(webhook_url: str, embed: DiscordEmbed) -> None:
    """
        Sends a Discord embed via webhook with automatic rate-limit retry.

        Args:
            webhook_url    (str): Discord webhook URL.
            embed (DiscordEmbed): Embed object to send.

        Raises:
            RuntimeError: If the webhook request fails.
    """
    webhook = DiscordWebhook(
        url=webhook_url,
        username=GITHUB_USERNAME,
        avatar_url=GITHUB_AVATAR_URL,
        rate_limit_retry=True
    )
    webhook.add_embed(embed=embed)

    res = webhook.execute()

    if not res.ok:
        raise RuntimeError(f'Discord webhook failed: HTTP {res.status_code} {res.text}')
