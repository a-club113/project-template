""" Entry point that orchestrates fetching a diff, reviewing it, and posting the result. """
from pr_review.comment_poster import post_comment
from pr_review.config import load_config
from pr_review.diff_fetcher import fetch_pr_diff
from pr_review.gemini_reviewer import generate_review


def main() -> None:
    """ Run the full PR review workflow: fetch diff, review it, and post the comment. """
    config = load_config()
    diff_text = fetch_pr_diff(config.github_repository, config.pr_number, config.github_token)

    if not diff_text.strip():
        post_comment(
            config.github_repository,
            config.pr_number,
            config.github_token,
            '差分が検出できませんでした。'
        )

        return

    truncated_diff = diff_text[: config.max_diff_chars]
    review_text = generate_review(truncated_diff, config.gemini_api_key)

    comment_body = f'## 🤖 自動コードレビュー (Gemini)\n\n{review_text}'
    post_comment(config.github_repository, config.pr_number, config.github_token, comment_body)

if __name__ == '__main__':
    main()
