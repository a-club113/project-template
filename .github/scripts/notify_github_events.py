"""
    Discord notification script for GitHub repository events.

    Reads the GitHub event JSON passed via environment variables,
    builds a Discord embed per event type, and sends it via webhook.

    Environment variables required:
        - GITHUB_EVENT_NAME  : Name of the triggered GitHub event.
        - GITHUB_EVENT_PATH  : Path to the JSON file containing event payload (set automatically by Actions).
        - GITHUB_TOKEN       : GitHub token for API access (set automatically by Actions).
        - GITHUB_REPOSITORY  : Repository name in owner/repo format (set automatically by Actions).
        - GITHUB_REF         : Full ref string e.g. refs/heads/main (set automatically by Actions).
        - GITHUB_SHA         : Commit SHA of the current push (set automatically by Actions).
        - DISCORD_WEBHOOK_URL: Discord webhook URL to post notifications to.
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from json import load
from typing import Any, Final, Optional

from _discord_common import get_logger, send_embed, truncate
from discord_webhook import DiscordEmbed
from github import Auth, Github
from github.Repository import Repository

logger = get_logger(__name__)

JST = timezone(timedelta(hours=9))

# Embed colors
COLOR_PUSH: Final[str] = '5865f2'
COLOR_MERGE: Final[str] = '5865f2'
COLOR_PR_OPENED: Final[str] = '00ff00'
COLOR_PR_MERGED: Final[str] = '9c27b0'
COLOR_PR_CLOSED: Final[str] = 'ff0000'
COLOR_ISSUE_OPENED: Final[str] = 'ffa500'
COLOR_ISSUE_CLOSED: Final[str] = '808080'
COLOR_ISSUE_COMMENT: Final[str] = '1e88e5'
COLOR_ERROR: Final[str] = 'ff0000'

EMBED_FIELD_LIMIT: Final[int] = 1000

def _to_jst(iso_str: str) -> str:
    """
        Converts an ISO 8601 timestamp string to JST HH:MM:SS.

        Args:
            iso_str (str): ISO 8601 timestamp string.

        Returns:
            str: Time formatted as HH:MM:SS in JST.
    """
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))

    return dt.astimezone(JST).strftime('%H:%M:%S')

def _get_commit_files(repo: Repository, commit_sha: str) -> tuple[str, str]:
    """
        Retrieves changed files and diff stats for a commit via GitHub API.

        Args:
            repo (Repository): PyGithub repository object.
            commit_sha  (str): Full commit SHA.

        Returns:
            tuple[str, str]: A tuple containing:
                - str: files_list
                - str: total_changes
    """
    commit = repo.get_commit(commit_sha)
    files_list = '\n'.join(
        f'- {f.filename} (+{f.additions} / -{f.deletions})' for f in commit.files
    )
    total_changes = f'+{commit.stats.additions} / -{commit.stats.deletions}'

    return files_list, total_changes

def _get_pr_files(repo: Repository, pr_number: int) -> tuple[str, str]:
    """
        Retrieves changed files and diff stats for a pull request via GitHub API.

        Args:
            repo (Repository): PyGithub repository object.
            pr_number   (int): Pull request number.

        Returns:
            tuple[str, str]: A tuple containing:
                - str: files_list
                - str: total_changes
    """
    pr = repo.get_pull(pr_number)
    files = pr.get_files()
    files_list = '\n'.join(
        f'- {f.filename} (+{f.additions} / -{f.deletions})' for f in files
    )
    total_changes = f'+{pr.additions} / -{pr.deletions}'

    return files_list, total_changes

def _handle_push(event: dict[str, Any], repo: Repository) -> DiscordEmbed:
    """
        Builds a Discord embed for push events.

        Args:
            event (dict[str, Any]): GitHub event payload.
            repo      (Repository): PyGithub repository object.

        Returns:
            DiscordEmbed: Configured embed.
    """
    commit_sha: str = event['after']
    commit_sha_short = os.environ.get('GITHUB_SHA', commit_sha)[:7]
    branch_name = os.environ.get('GITHUB_REF', '').replace('refs/heads/', '')
    head_commit = event['head_commit']
    commit_msg = head_commit['message']
    committer = head_commit['committer']['name']
    current_time_jst = _to_jst(head_commit['timestamp'])
    files_changed, total_changes = _get_commit_files(repo, commit_sha)

    merge_match = re.match(r'Merge pull request #(\d+) from (\S+)', commit_msg)

    if merge_match:
        source_branch = merge_match.group(2)
        title = f'🔀 New Merge Commit ({source_branch} → {branch_name}) at {current_time_jst}'
        color = COLOR_MERGE
    else:
        title = f'📦 New Commit on {branch_name} at {current_time_jst}'
        color = COLOR_PUSH

    diff_url = f'https://github.com/{repo.full_name}/commit/{commit_sha}'
    embed = DiscordEmbed(title=title, color=color, url=diff_url)
    embed.add_embed_field(name='👤 Committer', value=committer, inline=True)
    embed.add_embed_field(name='🔑 Commit Hash', value=f'`{commit_sha_short}`', inline=True)
    embed.add_embed_field(name='📝 Message', value=commit_msg, inline=False)
    embed.add_embed_field(name='📊 Total Changes', value=total_changes, inline=True)
    embed.add_embed_field(name='📁 Changed Files', value=truncate(files_changed), inline=False)
    embed.add_embed_field(name='🔗 Diff URL', value=f'[差分を表示する]({diff_url})', inline=False)

    return embed

def _handle_pull_request(event: dict[str, Any], repo: Repository) -> Optional[DiscordEmbed]:
    """
        Builds a Discord embed for pull_request events (opened / closed).

        Args:
            event (dict[str, Any]): GitHub event payload.
            repo      (Repository): PyGithub repository object.

        Returns:
            Optional[DiscordEmbed]: Configured embed, or None if the action is not handled.
    """
    action = event['action']
    pr = event['pull_request']
    current_time_jst = _to_jst(pr['created_at'])

    if action == 'opened':
        files_list, total_changes = _get_pr_files(repo, pr['number'])

        embed = DiscordEmbed(
            title=f'🟢 New Pull Request (No. {pr["number"]}) at {current_time_jst}',
            color=COLOR_PR_OPENED,
            url=pr['html_url']
        )
        embed.add_embed_field(name='📌 Title', value=pr['title'], inline=False)
        embed.add_embed_field(name='👤 Author', value=pr['user']['login'], inline=True)
        embed.add_embed_field(name='📊 Total Changes', value=total_changes, inline=True)
        embed.add_embed_field(name='📁 Changed Files', value=truncate(files_list), inline=False)
        embed.add_embed_field(
            name='🔗 Actions',
            value=(
                f'[マージして閉じる]({pr["html_url"]}/merge)'
                f' | [確認する]({pr["html_url"]})'
                f' | [マージせずに閉じる]({pr["html_url"]}/close)'
            ),
            inline=False
        )

        return embed

    if action == 'closed':
        merged: bool = pr.get('merged', False)
        status_label = f'✅ No. {pr["number"]} Merged' if merged else f'❌ No. {pr["number"]} Closed without merging'
        color = COLOR_PR_MERGED if merged else COLOR_PR_CLOSED

        embed = DiscordEmbed(
            title=f'Pull Request {status_label} at {current_time_jst}',
            color=color,
            url=pr['html_url']
        )
        embed.add_embed_field(name='📌 Title', value=pr['title'], inline=False)
        embed.add_embed_field(name='👤 Author', value=pr['user']['login'], inline=True)
        embed.add_embed_field(
            name='🔗 Diff URL',
            value=f'[差分を表示する]({pr["html_url"]}/files)',
            inline=False
        )

        return embed

    logger.info(f'Unhandled pull_request action: {action!r}. Skipping.')

    return None

def _handle_issues(event: dict[str, Any], repo: Repository) -> Optional[DiscordEmbed]:
    """
        Builds a Discord embed for issues events (opened / closed).

        Args:
            event (dict[str, Any]): GitHub event payload.
            repo      (Repository): PyGithub repository object.

        Returns:
            Optional[DiscordEmbed]: Configured embed, or None if the action is not handled.
    """
    action = event['action']
    issue = event['issue']
    current_time_jst = _to_jst(issue['created_at'])

    if action == 'opened':
        embed = DiscordEmbed(
            title=f'🟠 New Issue Opened at {current_time_jst} (Issue No. {issue["number"]})',
            color=COLOR_ISSUE_OPENED,
            url=issue['html_url']
        )
        embed.add_embed_field(name='📌 Title', value=issue['title'], inline=False)
        embed.add_embed_field(name='👤 Author', value=issue['user']['login'], inline=True)

        return embed

    if action == 'closed':
        embed = DiscordEmbed(
            title=f'🔘 Issue Closed at {current_time_jst} (Issue No. {issue["number"]})',
            color=COLOR_ISSUE_CLOSED,
            url=issue['html_url']
        )
        embed.add_embed_field(name='📌 Title', value=issue['title'], inline=False)
        embed.add_embed_field(name='🔒 Closed by', value=issue['user']['login'], inline=True)
        embed.add_embed_field(
            name='🔗 Issue URL',
            value=f'[Issueを表示する](https://github.com/{repo.full_name}/issues/{issue["number"]})',
            inline=False
        )

        return embed

    logger.info(f'Unhandled issues action: {action!r}. Skipping.')

    return None

def _handle_issue_comment(event: dict[str, Any]) -> Optional[DiscordEmbed]:
    """
        Builds a Discord embed for issue_comment events (created only).

        Args:
            event (dict[str, Any]): GitHub event payload.

        Returns:
            Optional[DiscordEmbed]: Configured embed, or None if the action is not handled.
    """
    action = event['action']

    if action != 'created':
        logger.info(f'Unhandled issue_comment action: {action!r}. Skipping.')

        return None

    issue = event['issue']
    comment = event['comment']
    current_time_jst = _to_jst(comment['created_at'])

    embed = DiscordEmbed(
        title=f'💬 New Comment on Issue at {current_time_jst} (Issue No. {issue["number"]})',
        color=COLOR_ISSUE_COMMENT,
        url=comment['html_url']
    )
    embed.add_embed_field(name='📌 Issue Title', value=issue['title'], inline=False)
    embed.add_embed_field(name='👤 Comment by', value=comment['user']['login'], inline=True)
    embed.add_embed_field(name='💬 Comment', value=truncate(comment['body']), inline=False)

    return embed

def main() -> None:
    """
        Entry point. Reads GitHub context from environment variables,
        builds the appropriate Discord embed, and sends the notification.
    """
    event_name = os.environ['GITHUB_EVENT_NAME']
    webhook_url = os.environ['DISCORD_WEBHOOK_URL']
    github_token = os.environ['GITHUB_TOKEN']
    repo_name = os.environ['GITHUB_REPOSITORY']

    event_path = os.environ['GITHUB_EVENT_PATH']

    with open(event_path, encoding='utf-8') as f:
        event: dict[str, Any] = load(f)

    g = Github(auth=Auth.Token(github_token))
    repo = g.get_repo(repo_name)
    embed: Optional[DiscordEmbed] = None

    match event_name:
        case 'push':
            embed = _handle_push(event=event, repo=repo)
        case 'pull_request':
            embed = _handle_pull_request(event=event, repo=repo)
        case 'issues':
            embed = _handle_issues(event=event, repo=repo)
        case 'issue_comment':
            embed = _handle_issue_comment(event=event)
        case _:
            logger.info(f'Unhandled event: {event_name!r}. Skipping.')
            sys.exit(0)

    if embed is None:
        sys.exit(0)

    try:
        send_embed(webhook_url, embed)
        logger.info(f'Notification sent successfully (event={event_name})')
    except Exception as e:
        logger.error(f'Failed to send notification: {e}')

        now_jst = datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')
        error_embed = DiscordEmbed(
            title=f'⚠️ Error sending notification at {now_jst}',
            description=str(e),
            color=COLOR_ERROR
        )

        try:
            send_embed(webhook_url, error_embed)
        except Exception as send_err:
            logger.error(f'Failed to send error notification: {send_err}')

        sys.exit(1)

if __name__ == '__main__':
    main()
