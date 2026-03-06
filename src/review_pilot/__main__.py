"""Entry point — port of src/index.ts. Runs as `python -m review_pilot`."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from github import Github

from .agents.convention_miner import mine_conventions_from_merged_pr
from .agents.diff_router import route_diff
from .agents.orchestrator import run_orchestrator
from .context_resolver import build_review_context
from .diff_parser import parse_pr_files
from .policy.load_policy import load_policy
from .reviewer import build_review_output, post_review

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _get_input(name: str, required: bool = False, default: str = "") -> str:
    env_name = f"INPUT_{name.upper().replace('-', '_')}"
    value = os.environ.get(env_name, default)
    if required and not value:
        logger.error("Input '%s' is required but was not provided.", name)
        sys.exit(1)
    return value


def _set_output(name: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")


def run() -> None:
    try:
        api_key = _get_input("anthropic-api-key", required=True)
        model = _get_input("model", default="claude-sonnet-4-5-20250929")
        config_path = _get_input("config-path", default=".review-pilot.yml")
        learned_rules_path = _get_input("learned-rules-path", default=".review-pilot-learned.json")
        policy_path = _get_input("policy-path", default="reviewer_policy.json")
        input_mode = _get_input("mode")
        mode = "enforce" if input_mode == "enforce" else "warn" if input_mode == "warn" else None
        max_inline_comments_str = _get_input("max-inline-comments", default="3")

        token = _get_input("github-token") or os.environ.get("GITHUB_TOKEN", "")
        if not token:
            logger.error("GitHub token is required. Set GITHUB_TOKEN or pass github-token input.")
            sys.exit(1)

        event_path = os.environ.get("GITHUB_EVENT_PATH", "")
        if not event_path or not os.path.exists(event_path):
            logger.error("GITHUB_EVENT_PATH not set or file missing")
            sys.exit(1)

        with open(event_path) as f:
            event_payload: dict[str, Any] = json.load(f)

        event_name = os.environ.get("GITHUB_EVENT_NAME", "")
        action = event_payload.get("action", "")

        gh = Github(token)
        repo_full_name = os.environ.get("GITHUB_REPOSITORY", "")
        repo = gh.get_repo(repo_full_name)

        pr_data = event_payload.get("pull_request")
        if not pr_data:
            logger.error("No pull request found in event payload")
            sys.exit(1)

        pull_number = pr_data["number"]
        pr = repo.get_pull(pull_number)

        # Convention mining on merged PRs
        if event_name == "pull_request" and action == "closed":
            if pr_data.get("merged"):
                logger.info("PR merged — running convention miner")
                mine_conventions_from_merged_pr(
                    repo,
                    pr,
                    api_key=api_key,
                    model=model,
                    learned_rules_path=learned_rules_path,
                )
            else:
                logger.info("PR closed without merge; skipping convention miner")
            return

        # Only review on opened/synchronize/reopened
        if event_name != "pull_request" or action not in ("opened", "synchronize", "reopened"):
            logger.info("Unsupported event: %s.%s, skipping", event_name, action)
            return

        head_sha = pr_data["head"]["sha"]
        logger.info("Reviewing PR #%d (%s)", pull_number, head_sha)

        policy_bundle = load_policy(
            config_path=config_path,
            learned_rules_path=learned_rules_path,
            policy_path=policy_path,
            mode=mode,  # type: ignore[arg-type]
        )

        pr_files = pr.get_files()
        files_data = [
            {
                "filename": f.filename,
                "status": f.status,
                "patch": f.patch,
            }
            for f in pr_files
        ]
        changed_files = parse_pr_files(files_data, policy_bundle.ignore)
        if not changed_files:
            logger.info("No reviewable files changed, skipping")
            return

        review_context = build_review_context(
            repo,
            owner=repo_full_name.split("/")[0],
            repo_name=repo_full_name.split("/")[1],
            pull_number=pull_number,
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            head_branch=pr_data.get("head", {}).get("ref", ""),
            head_sha=head_sha,
            changed_files=changed_files,
            context_budget=policy_bundle.settings.context_budget,
        )

        routing = route_diff(changed_files, policy_bundle)

        result = run_orchestrator(
            routing=routing,
            policy=policy_bundle,
            changed_file_contents=review_context.changed_files,
        )

        try:
            max_inline_comments = int(max_inline_comments_str)
        except ValueError:
            max_inline_comments = policy_bundle.enforcement.max_comments

        review = build_review_output(
            result,
            changed_files,
            max_inline_comments,
            opts={
                "mode": policy_bundle.enforcement.mode,
                "block_on": policy_bundle.enforcement.block_on,
            },
        )

        post_review(pr, review_context.repo_metadata, review)

        critical_count = sum(1 for f in result.findings if f.severity == "critical")
        warning_count = sum(1 for f in result.findings if f.severity == "warning")

        _set_output("findings-count", str(len(result.findings)))
        _set_output("critical-count", str(critical_count))
        _set_output("warning-count", str(warning_count))
        _set_output("review-event", review.event)
        _set_output("policy-version", "1")
        _set_output("tokens-used", str(result.token_usage.input_tokens + result.token_usage.output_tokens))

    except Exception as err:
        logger.error("Review Pilot failed: %s", err)
        sys.exit(1)


if __name__ == "__main__":
    run()
