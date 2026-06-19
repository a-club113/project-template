"""
    Discord notification script for GitHub Actions CI/CD pipeline results.

    Sends formatted embed notifications to a Discord webhook with test results, coverage information, and deployment status.
"""
import os
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime
from typing import Final, Literal, Optional

from _discord_common import get_logger, send_embed
from discord_webhook import DiscordEmbed

logger = get_logger(__name__)

STATUS_CONFIG: Final[dict[str, dict[str, str]]] = {
    'success': {
        'color': '57f287',
        'emoji': '✅'
    },
    'failure': {
        'color': 'ed4245',
        'emoji': '❌'
    },
    'cancelled': {
        'color': 'faa61a',
        'emoji': '⚠️'
    },
    'skipped': {
        'color': '95a5a6',
        'emoji': '⏭️'
    }
}

def _parse_commit_timestamp(raw: Optional[str]) -> Optional[str]:
    """
        Validates and returns the commit timestamp string for Discord embeds.

        Args:
            raw (Optional[str]): Raw timestamp string from GitHub context.

        Returns:
            Optional[str]: The original ISO 8601 string if valid, or None if parsing fails.
    """
    if not raw:
        return None

    try:
        datetime.fromisoformat(raw)

        return raw
    except ValueError:
        return None

def _format_code_size(raw: Optional[str]) -> Optional[str]:
    """
        Formats a raw byte count string into a human-readable size string.

        Args:
            raw (Optional[str]): Raw byte count string from Lambda API.

        Returns:
            Optional[str]: Formatted string like '1.23 MB' or '456 KB', or None if invalid.
    """
    if not raw:
        return None

    try:
        size = int(raw)

        if size >= 1024 * 1024:
            return f'{size / (1024 * 1024):.2f} MB'
        elif size >= 1024:
            return f'{size / 1024:.1f} KB'
        else:
            return f'{size} B'
    except ValueError:
        return None

def _build_test_embed(
    status: Literal['success', 'failure', 'cancelled'],
    branch: str,
    commit_sha: str,
    commit_message: str,
    commit_timestamp: Optional[str],
    run_url: str,
    actor: str,
    passed: Optional[str],
    failed: Optional[str],
    coverage: Optional[str],
    duration: Optional[str]
) -> DiscordEmbed:
    """
        Builds a Discord embed for test results.

        Args:
            status (Literal['success', 'failure', 'cancelled']): Job status.
            branch                                        (str): Git branch name.
            commit_sha                                    (str): Commit SHA.
            commit_message                                (str): Commit message.
            commit_timestamp                              (str): Commit timestamp (ISO 8601).
            run_url                                       (str): GitHub Actions run URL.
            actor                                         (str): GitHub actor who triggered the run.
            passed                              (Optional[str]): Number of passed tests.
            failed                              (Optional[str]): Number of failed tests.
            coverage                            (Optional[str]): Coverage percentage string (e.g. '92%').
            duration                            (Optional[str]): Test duration in seconds.

        Returns:
            DiscordEmbed: Configured embed instance.
    """
    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG['failure'])
    title = f'{cfg["emoji"]} Test {"Passed" if status == "success" else "Failed"}'
    short_sha = commit_sha[:7] if commit_sha else 'unknown'
    short_msg = (commit_message[:72] + '...') if len(commit_message) > 72 else commit_message
    utc_ts = _parse_commit_timestamp(commit_timestamp)

    embed = DiscordEmbed(title=title, url=run_url, color=cfg['color'])

    if utc_ts:
        embed.set_timestamp(utc_ts)

    embed.add_embed_field(name='🌿 Branch', value=f'`{branch}`', inline=True)
    embed.add_embed_field(name='👤 Actor', value=actor, inline=True)
    embed.add_embed_field(
        name='📝 Commit',
        value=f'[`{short_sha}`]({run_url})\n{short_msg}',
        inline=False
    )

    test_parts = []
    if passed:
        test_parts.append(f'✅ {passed} passed')
    if failed:
        test_parts.append(f'❌ {failed} failed')
    if test_parts:
        embed.add_embed_field(name='🧪 Test Results', value=' / '.join(test_parts), inline=True)

    if coverage:
        try:
            cov_num = round(float(coverage), 1)
            cov_emoji = '🟢' if cov_num >= 85 else ('🟡' if cov_num >= 70 else '🔴')
            embed.add_embed_field(name=f'{cov_emoji} Coverage', value=f'{cov_num} %', inline=True)
        except ValueError:
            pass

    if duration:
        embed.add_embed_field(name='⏱️ Duration', value=f'{duration} s', inline=True)

    embed.set_footer(text='GitHub Actions • twitter-discord-bot-lambda')

    return embed

def _build_deploy_embed(
    status: Literal['success', 'failure', 'cancelled'],
    branch: str,
    commit_sha: str,
    commit_message: str,
    commit_timestamp: Optional[str],
    run_url: str,
    actor: str,
    function_name: str,
    deploy_skipped: bool,
    code_size_before: Optional[str] = None,
    code_size_after: Optional[str] = None
) -> DiscordEmbed:
    """
        Builds a Discord embed for deployment results.

        Args:
            status (Literal['success', 'failure', 'cancelled']): Job status.
            branch                                        (str): Git branch name.
            commit_sha                                    (str): Commit SHA.
            commit_message                                (str): Commit message.
            commit_timestamp                              (str): Commit timestamp (ISO 8601).
            run_url                                       (str): GitHub Actions run URL.
            actor                                         (str): GitHub actor.
            function_name                                 (str): AWS Lambda function name.
            deploy_skipped                               (bool): Whether deploy was skipped (no deployable changes).
            code_size_before                    (Optional[str]): Lambda code size in bytes before deploy.
            code_size_after                     (Optional[str]): Lambda code size in bytes after deploy.

        Returns:
            DiscordEmbed: Configured embed instance.
    """
    if deploy_skipped:
        cfg = STATUS_CONFIG['skipped']
        title = '⏭️ Deploy Skipped'
    else:
        cfg = STATUS_CONFIG.get(status, STATUS_CONFIG['failure'])
        title = f'{cfg["emoji"]} Deploy {"Succeeded" if status == "success" else "Failed"}'

    short_sha = commit_sha[:7] if commit_sha else 'unknown'
    short_msg = (commit_message[:72] + '...') if len(commit_message) > 72 else commit_message
    utc_ts = _parse_commit_timestamp(commit_timestamp)

    embed = DiscordEmbed(title=title, url=run_url, color=cfg['color'])

    if utc_ts:
        embed.set_timestamp(utc_ts)

    embed.add_embed_field(name='🌿 Branch', value=f'`{branch}`', inline=True)
    embed.add_embed_field(name='👤 Actor', value=actor, inline=True)
    embed.add_embed_field(
        name='📝 Commit',
        value=f'[`{short_sha}`]({run_url})\n{short_msg}',
        inline=False,
    )

    if deploy_skipped:
        embed.add_embed_field(
            name='ℹ️ Skip Reason',
            value='No changes in `src/`、`pyproject.toml`、`uv.lock`',
            inline=False
        )
    else:
        embed.add_embed_field(name='🚀 Lambda Function', value=f'`{function_name}`', inline=True)
        embed.add_embed_field(name='📦 Deploy Target', value='AWS Lambda (ap-northeast-1)', inline=True)

        size_before = _format_code_size(code_size_before)
        size_after = _format_code_size(code_size_after)

        if size_before and size_after:
            try:
                diff_bytes = int(code_size_after) - int(code_size_before)  # type: ignore[arg-type]
                sign = '+' if diff_bytes >= 0 else ''
                diff_kb = diff_bytes / 1024
                diff_str = f'{sign}{diff_kb:.1f} KB'
                size_value = f'{size_before} → {size_after} (`{diff_str}`)'
            except (ValueError, TypeError):
                size_value = f'{size_before} → {size_after}'

            embed.add_embed_field(name='📊 Code Size', value=size_value, inline=False)
        elif size_after:
            embed.add_embed_field(name='📊 Code Size', value=size_after, inline=True)

    embed.set_footer(text='GitHub Actions • twitter-discord-bot-lambda')

    return embed

def notify_test(args: Namespace) -> None:
    """
        Sends a test result notification to Discord.

        Args:
            args (Namespace): Parsed CLI arguments.
    """
    webhook_url = args.webhook_url or os.environ.get('DISCORD_WEBHOOK_URL', '')

    if not webhook_url:
        print('ERROR: DISCORD_WEBHOOK_URL is not set.', file=sys.stderr)
        sys.exit(1)

    embed = _build_test_embed(
        status=args.status,
        branch=args.branch,
        commit_sha=args.commit_sha,
        commit_message=args.commit_message,
        commit_timestamp=args.commit_timestamp,
        run_url=args.run_url,
        actor=args.actor,
        passed=args.passed or None,
        failed=args.failed or None,
        coverage=args.coverage or None,
        duration=args.duration or None
    )

    send_embed(webhook_url=webhook_url, embed=embed)

    logger.info(f'Test notification sent successfully (status={args.status})')

def notify_deploy(args: Namespace) -> None:
    """
        Sends a deployment result notification to Discord.

        Args:
            args (Namespace): Parsed CLI arguments.
    """
    webhook_url = args.webhook_url or os.environ.get('DISCORD_WEBHOOK_URL', '')

    if not webhook_url:
        logger.error('DISCORD_WEBHOOK_URL is not set.')

        sys.exit(1)

    embed = _build_deploy_embed(
        status=args.status,
        branch=args.branch,
        commit_sha=args.commit_sha,
        commit_message=args.commit_message,
        commit_timestamp=args.commit_timestamp,
        run_url=args.run_url,
        actor=args.actor,
        function_name=args.function_name,
        deploy_skipped=args.deploy_skipped,
        code_size_before=args.code_size_before or None,
        code_size_after=args.code_size_after or None
    )

    send_embed(webhook_url=webhook_url, embed=embed)

    logger.info(f'Deploy notification sent successfully (status={args.status}, skipped={args.deploy_skipped})')

def main() -> None:
    """ Entry point for the Discord notification script. """
    def add_common_args(p: ArgumentParser) -> None:
        """
            Adds common arguments shared between subcommands.

            Args:
                p (ArgumentParser): Subparser to add arguments to.
        """
        p.add_argument('--webhook-url', default='')
        p.add_argument('--status', required=True, choices=['success', 'failure', 'cancelled', 'skipped'])
        p.add_argument('--branch', required=True)
        p.add_argument('--commit-sha', required=True, dest='commit_sha')
        p.add_argument('--commit-message', required=True, dest='commit_message')
        p.add_argument('--commit-timestamp', required=True, dest='commit_timestamp')
        p.add_argument('--run-url', required=True, dest='run_url')
        p.add_argument('--actor', required=True)

    parser = ArgumentParser(description='Send CI/CD results to Discord')
    subparsers = parser.add_subparsers(dest='command', required=True)

    test_parser = subparsers.add_parser('test')
    add_common_args(test_parser)
    test_parser.add_argument('--passed', default='')
    test_parser.add_argument('--failed', default='')
    test_parser.add_argument('--coverage', default='')
    test_parser.add_argument('--duration', default='')
    test_parser.set_defaults(func=notify_test)

    deploy_parser = subparsers.add_parser('deploy')
    add_common_args(deploy_parser)
    deploy_parser.add_argument('--function-name', required=True, dest='function_name')
    deploy_parser.add_argument('--deploy-skipped', action='store_true', dest='deploy_skipped')
    deploy_parser.add_argument('--code-size-before', default='', dest='code_size_before')
    deploy_parser.add_argument('--code-size-after', default='', dest='code_size_after')
    deploy_parser.set_defaults(func=notify_deploy)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
